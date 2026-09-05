"""老马盯盘智能体：对话式 agent + 多智能体博弈分析。

两种模式：
- single（默认）：单 agent 查数据直接答，适合快问快答。
- debate（多专家博弈，对标 FinGenius）：并行召集 4 位专家（舆情/技术/资金/风控）
  各自调用工具查真实数据 → 多空观点 → 主席合成「多空比分 + 共识/分歧 + 操作建议」。

复用站内已有 /api/* 接口作为工具（通过容器内部 127.0.0.1:8787 自调用，
转发用户 cookie，天然继承登录态与权限）。
NDJSON 流式输出：
  {"type":"status"} 进度 / {"type":"expert_done"} 某专家结论 /
  {"type":"answer"} 最终回答 / {"type":"error"} 异常。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

APP_INTERNAL_BASE = os.getenv("AGENT_INTERNAL_BASE", "http://127.0.0.1:8787")
MAX_TOOL_ROUNDS = 6
MAX_TOOL_RESULT_CHARS = 4500
LLM_TIMEOUT = 90
TOOL_TIMEOUT = 25

SYSTEM_PROMPT = (
    "你是「老马盯盘智能体」，嵌入在老马的 A 股盯盘助手中。"
    "你的职责：老马直接向你提问，你调用工具查询真实数据后给出有依据的回答和操作建议。\n"
    "规则：\n"
    "1. 涉及行情、持仓、异动、板块、推荐等事实问题时，必须先调用工具查数据，绝不凭空编造数字。\n"
    "2. 工具没查到或数据为空时，明确说明查不到，不要虚构。\n"
    "3. 回答用简体中文，口语一点，结论先行：先一句话给结论，再列关键数据（标注股票代码），最后给可执行的下一步动作（如\"盯住XX支撑位\"\"建议减仓一半\"）。\n"
    "4. A 股惯例：涨=红色=好事，跌=绿色。金额单位用元/万元/亿元。\n"
    "5. 你只做分析和建议，绝不自动下单；涉及买卖建议时提醒\"仅供参考，操作前自己再确认\"。\n"
    "6. 回答控制在 500 字以内，重点突出，可分点。"
)

# ===================== 多智能体：专家定义 =====================
EXPERTS = [
    {
        "key": "sentiment",
        "name": "舆情消息面",
        "emoji": "📰",
        "tools": ["morning_briefing", "abnormal_events", "ai_recommendations", "market_overview", "stock_search"],
        "system": (
            "你是 A股『舆情消息面』分析专家，只看消息、情绪、事件、热点维度。\n"
            "你拥有工具可查询：盘前简报、盘中异动、AI 推荐、大盘情绪、股票搜索。\n"
            "规则：必须用工具查真实数据，不编造；若数据为空明确说明。\n"
            "分析后，除正文外，结尾用严格一行结论标记：\n"
            "【结论】看多|看空|中性 【信心】0-100 的整数 【核心】不超过 25 字的一句话核心观点\n"
            "例：\n【结论】看多 【信心】72 【核心】降准落地+板块异动，情绪转暖"
        ),
    },
    {
        "key": "technical",
        "name": "技术面",
        "emoji": "📈",
        "tools": ["stock_quote", "stock_deep_analysis", "stock_search"],
        "system": (
            "你是 A股『技术面』分析专家，只看价格、K线、均线、量能、技术形态、指标维度。\n"
            "你拥有工具可查询：个股行情(K线/最新价/涨跌幅)、个股技术面+基本面深度分析、股票搜索。\n"
            "规则：必须用工具查真实数据，不编造；若数据为空明确说明。\n"
            "分析后，结尾用严格一行结论标记：\n"
            "【结论】看多|看空|中性 【信心】0-100 的整数 【核心】不超过 25 字的一句话核心观点"
        ),
    },
    {
        "key": "capital",
        "name": "资金面",
        "emoji": "💰",
        "tools": ["stock_fund_flow", "stock_quote", "market_movers", "market_sectors", "stock_search"],
        "system": (
            "你是 A股『资金面』分析专家，只看主力资金、净流入、大单、板块资金轮动、涨跌榜维度。\n"
            "你拥有工具可查询：个股资金流向、个股行情、涨跌幅榜、板块行情、股票搜索。\n"
            "规则：必须用工具查真实数据，不编造；若数据为空明确说明。\n"
            "分析后，结尾用严格一行结论标记：\n"
            "【结论】看多|看空|中性 【信心】0-100 的整数 【核心】不超过 25 字的一句话核心观点"
        ),
    },
    {
        "key": "risk",
        "name": "风控仓位",
        "emoji": "🛡️",
        "tools": ["portfolio_summary", "action_queue", "decision_fusion", "daily_review"],
        "system": (
            "你是 A股『风控与仓位』分析专家，只看持仓风险、仓位、系统操作建议、决策融合、复盘维度。\n"
            "你拥有工具可查询：老马持仓汇总、操作队列、多维度决策融合、每日复盘。\n"
            "规则：必须用工具查真实数据，不编造；若数据为空明确说明。\n"
            "分析后，结尾用严格一行结论标记：\n"
            "【结论】看多|看空|中性 【信心】0-100 的整数 【核心】不超过 25 字的一句话核心观点"
        ),
    },
]

SYNTHESIS_PROMPT = (
    "你是『多空辩论主席』，负责综合 4 位 A股专家（舆情/技术/资金/风控）的独立分析，"
    "形成最终结论。\n"
    "输入：用户原始问题 + 4 位专家的分析与各自结论（含【结论】【信心】【核心】标记）。\n"
    "你的输出要求（严格按以下顺序，用简体中文 markdown）：\n"
    "1. 第一行必须是比分标记：\n"
    "【多空比分】多方X:空方Y\n（X/Y 为 4 位专家中看多/看空的人数，中性可折半计，合计约等于 4）\n"
    "2. 一句话总结论（结论先行，口语化）。\n"
    "3. 各方核心观点（简述 4 位专家的核心，每点 1-2 句，标注专家名）。\n"
    "4. 共识与分歧（哪些达成一致、最大分歧在哪）。\n"
    "5. 关键数据支撑（引用专家查到的真实数字，标注代码/指数）。\n"
    "6. 操作建议（可执行、结论先行，如\"X 不破 Y 可持有，跌破减仓\"）。\n"
    "7. 风险提示（1-2 句，含\"仅供参考，决策权在你\"）。\n"
    "全程不编造数据；A 股惯例涨红跌绿；总字数控制在 700 字以内。"
)


def _tool(name: str, description: str, params: dict | None = None, required: list | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": params or {},
                "required": required or [],
            },
        },
    }


TOOLS_SPEC = [
    _tool("market_overview", "大盘总览：上证/深证/创业板指数、涨跌家数、市场情绪"),
    _tool("morning_briefing", "盘前简报：今日要点、重要事件"),
    _tool("portfolio_summary", "查询老马的持仓汇总：各持仓股、成本、盈亏、仓位"),
    _tool("watchlist", "查询自选股列表及各股最新行情"),
    _tool("market_movers", "今日涨跌幅榜、活跃股"),
    _tool("market_sectors", "今日板块行情：领涨领跌板块"),
    _tool("abnormal_events", "盘中异动监控事件：急涨急跌、放量等"),
    _tool("ai_recommendations", "系统 AI 推荐的股票列表及推荐理由"),
    _tool("action_queue", "今日交易操作队列：系统建议的买卖动作"),
    _tool("decision_fusion", "多维度决策融合结论"),
    _tool("daily_review", "每日复盘报告"),
    _tool(
        "stock_quote",
        "查个股行情（K线/最新价/涨跌幅），参数 code 为 6 位股票代码，如 600519",
        {"code": {"type": "string", "description": "6 位股票代码"}},
        ["code"],
    ),
    _tool(
        "stock_fund_flow",
        "查个股资金流向（主力净流入等），参数 code 为 6 位股票代码",
        {"code": {"type": "string", "description": "6 位股票代码"}},
        ["code"],
    ),
    _tool(
        "stock_deep_analysis",
        "查个股技术面+基本面深度分析，参数 code 为 6 位股票代码",
        {"code": {"type": "string", "description": "6 位股票代码"}},
        ["code"],
    ),
    _tool(
        "stock_search",
        "按名称或代码模糊搜索股票，返回代码和名称",
        {"keyword": {"type": "string", "description": "股票名称或代码关键词"}},
        ["keyword"],
    ),
]

TOOL_ROUTES: dict[str, Any] = {
    "market_overview": lambda a: ("GET", "/api/market/overview"),
    "morning_briefing": lambda a: ("GET", "/api/market/morning-briefing"),
    "portfolio_summary": lambda a: ("GET", "/api/portfolio/summary"),
    "watchlist": lambda a: ("GET", "/api/watchlist"),
    "market_movers": lambda a: ("GET", "/api/market/movers"),
    "market_sectors": lambda a: ("GET", "/api/market/sectors"),
    "abnormal_events": lambda a: ("GET", "/api/abnormal/events"),
    "ai_recommendations": lambda a: ("GET", "/api/recommendations/ai"),
    "action_queue": lambda a: ("GET", "/api/trading/action-queue"),
    "decision_fusion": lambda a: ("GET", "/api/decision/fusion"),
    "daily_review": lambda a: ("GET", "/api/review/daily"),
    "stock_quote": lambda a: ("GET", f"/api/stocks/{a.get('code', '')}/chart"),
    "stock_fund_flow": lambda a: ("GET", f"/api/stocks/{a.get('code', '')}/fund-flow"),
    "stock_deep_analysis": lambda a: ("GET", f"/api/stocks/{a.get('code', '')}/technical-fund-analysis"),
    "stock_search": lambda a: ("GET", "/api/stocks/search"),
}

TOOL_LABELS = {
    "market_overview": "大盘总览",
    "morning_briefing": "盘前简报",
    "portfolio_summary": "我的持仓",
    "watchlist": "自选股",
    "market_movers": "涨跌幅榜",
    "market_sectors": "板块行情",
    "abnormal_events": "异动监控",
    "ai_recommendations": "AI 推荐",
    "action_queue": "操作队列",
    "decision_fusion": "决策融合",
    "daily_review": "每日复盘",
    "stock_quote": "个股行情",
    "stock_fund_flow": "资金流向",
    "stock_deep_analysis": "个股深度分析",
    "stock_search": "搜索股票",
}

TOOL_SPEC_BY_NAME = {t["function"]["name"]: t for t in TOOLS_SPEC}


class AgentChatPayload(BaseModel):
    message: str
    history: list[dict] = []
    mode: str = "single"  # single | debate


def _truncate(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…(数据过长已截断)"


def _internal_call(method: str, path: str, args: dict, headers: dict) -> str:
    url = APP_INTERNAL_BASE + path
    if "search" in path:
        url = f"{url}?q={urllib.request.quote(str(args.get('keyword', '')))}"
    req = urllib.request.Request(url, method=method)
    for key in ("cookie", "authorization"):
        if headers.get(key):
            req.add_header(key, headers[key])
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TOOL_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return _truncate(body)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        return json.dumps({"error": f"http_{exc.code}", "detail": detail}, ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": "tool_failed", "detail": str(exc)[:200]}, ensure_ascii=False)


def _llm_chat(base_url: str, api_key: str, model: str, messages: list[dict], tools: list[dict] | None) -> dict:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2200,
    }
    if tools:
        payload["tools"] = tools
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_verdict(text: str) -> tuple[str, int, str]:
    """从专家结论标记行解析 看多/看空/信心/核心。"""
    verdict = "中性"
    confidence = 50
    core = ""
    m = re.search(r"【结论】\s*(看多|看空|中性|偏多|偏空)", text)
    if m:
        verdict = {"偏多": "看多", "偏空": "看空"}.get(m.group(1), m.group(1))
    m = re.search(r"【信心】\s*(\d{1,3})", text)
    if m:
        confidence = max(0, min(100, int(m.group(1))))
    m = re.search(r"【核心】\s*(.+)", text)
    if m:
        core = m.group(1).strip()
    return verdict, confidence, core


def _strip_footer(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not re.match(r"\s*【(结论|信心|核心)】", ln)]
    return "\n".join(lines).strip()


async def _run_single(
    system_prompt: str,
    tool_names: list[str] | None,
    user_content: str,
    headers: dict,
    base_url: str,
    api_key: str,
    model: str,
    max_rounds: int,
) -> str:
    messages: list[dict] = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]
    tools = [TOOL_SPEC_BY_NAME[n] for n in tool_names if n in TOOL_SPEC_BY_NAME] if tool_names else None
    for _ in range(max_rounds):
        result = await asyncio.to_thread(_llm_chat, base_url, api_key, model, messages, tools)
        choice = (result.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return (msg.get("content") or "").strip() or "（模型未返回内容，请重试）"
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
        for call in tool_calls:
            fn = (call.get("function") or {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            if name not in TOOL_ROUTES:
                tool_result = json.dumps({"error": "unknown_tool"}, ensure_ascii=False)
            else:
                method, path = TOOL_ROUTES[name](args)
                tool_result = await asyncio.to_thread(_internal_call, method, path, args, headers)
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": tool_result})
    messages.append({"role": "user", "content": "（请基于以上已查到的数据直接给出结论，不要再调用工具）"})
    result = await asyncio.to_thread(_llm_chat, base_url, api_key, model, messages, None)
    return ((result.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


async def _run_expert(expert: dict, user_content: str, headers: dict, base_url: str, api_key: str, model: str) -> dict:
    try:
        raw = await _run_single(expert["system"], expert["tools"], user_content, headers, base_url, api_key, model, 3)
        verdict, confidence, core = _parse_verdict(raw)
        opinion = _strip_footer(raw)
        return {
            "key": expert["key"],
            "name": expert["name"],
            "emoji": expert["emoji"],
            "verdict": verdict,
            "confidence": confidence,
            "core": core,
            "opinion": opinion,
            "ok": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "key": expert["key"],
            "name": expert["name"],
            "emoji": expert["emoji"],
            "verdict": "中性",
            "confidence": 0,
            "core": "分析失败",
            "opinion": f"该专家分析异常：{str(exc)[:120]}",
            "ok": False,
        }


def register_agent_routes(app, ai_service) -> None:
    @app.post("/api/stock-agent/chat")
    async def agent_chat(payload: AgentChatPayload, request: Request) -> StreamingResponse:
        message = (payload.message or "").strip()
        if not message:
            return StreamingResponse(
                iter([json.dumps({"type": "error", "text": "消息不能为空"}, ensure_ascii=False) + "\n"]),
                media_type="application/x-ndjson",
            )

        api_key = getattr(ai_service, "api_key", "") or os.getenv("AI_API_KEY", "")
        base_url = getattr(ai_service, "base_url", "") or os.getenv("AI_BASE_URL", "https://api.deepseek.com/v1")
        model = getattr(ai_service, "model", "") or os.getenv("AI_MODEL", "deepseek-chat")
        if not api_key:
            async def no_key():
                yield json.dumps({"type": "error", "text": "AI 未配置：请先在系统中配置 API Key"}, ensure_ascii=False) + "\n"
            return StreamingResponse(no_key(), media_type="application/x-ndjson")

        fwd_headers = {"cookie": request.headers.get("cookie", ""), "authorization": request.headers.get("authorization", "")}
        mode = payload.mode if payload.mode in ("single", "debate") else "single"

        async def stream():
            yield json.dumps({"type": "status", "text": "思考中…"}, ensure_ascii=False) + "\n"
            try:
                if mode != "debate":
                    # ===== 单 agent 快问快答 =====
                    history = payload.history[-8:]
                    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
                    for item in history:
                        role = item.get("role")
                        content = str(item.get("content", ""))[:2000]
                        if role in {"user", "assistant"} and content:
                            messages.append({"role": role, "content": content})
                    messages.append({"role": "user", "content": message})
                    for round_no in range(MAX_TOOL_ROUNDS):
                        result = await asyncio.to_thread(_llm_chat, base_url, api_key, model, messages, TOOLS_SPEC)
                        choice = (result.get("choices") or [{}])[0]
                        msg = choice.get("message") or {}
                        tool_calls = msg.get("tool_calls") or []
                        if not tool_calls:
                            answer = (msg.get("content") or "").strip() or "（模型未返回内容，请重试）"
                            yield json.dumps({"type": "answer", "text": answer}, ensure_ascii=False) + "\n"
                            return
                        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
                        for call in tool_calls:
                            fn = (call.get("function") or {})
                            name = fn.get("name", "")
                            try:
                                args = json.loads(fn.get("arguments") or "{}")
                            except Exception:
                                args = {}
                            label = TOOL_LABELS.get(name, name)
                            extra = f"（{args.get('code') or args.get('keyword') or ''}）" if args else ""
                            yield json.dumps({"type": "status", "text": f"正在查询 {label}{extra}…"}, ensure_ascii=False) + "\n"
                            if name not in TOOL_ROUTES:
                                tool_result = json.dumps({"error": "unknown_tool"}, ensure_ascii=False)
                            else:
                                method, path = TOOL_ROUTES[name](args)
                                tool_result = await asyncio.to_thread(_internal_call, method, path, args, fwd_headers)
                            messages.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": tool_result})
                    messages.append({"role": "user", "content": "（请基于以上已查到的数据直接给出结论，不要再调用工具）"})
                    result = await asyncio.to_thread(_llm_chat, base_url, api_key, model, messages, None)
                    choice = (result.get("choices") or [{}])[0]
                    answer = ((choice.get("message") or {}).get("content") or "").strip()
                    yield json.dumps({"type": "answer", "text": answer or "查询轮次已达上限，请缩小问题范围再问"}, ensure_ascii=False) + "\n"
                    return

                # ===== 多智能体博弈（debate）=====
                yield json.dumps({"type": "status", "text": f"正在召集 4 位专家会诊：{message[:40]}…"}, ensure_ascii=False) + "\n"
                tasks = [
                    asyncio.create_task(_run_expert(e, message, fwd_headers, base_url, api_key, model))
                    for e in EXPERTS
                ]
                for fut in asyncio.as_completed(tasks):
                    exp = await fut
                    yield json.dumps({"type": "expert_done", **exp}, ensure_ascii=False) + "\n"
                experts = [await t for t in tasks]
                yield json.dumps({"type": "status", "text": "专家辩论中，合成最终结论…"}, ensure_ascii=False) + "\n"
                brief = "\n\n".join(
                    f"【{e['name']}】{e['emoji']}\n结论：{e['verdict']}（信心 {e['confidence']}）\n核心：{e['core']}\n分析：{e['opinion']}"
                    for e in experts
                )
                synth_input = f"用户问题：{message}\n\n===== 四位专家独立分析 =====\n{brief}"
                final = await _run_single(SYNTHESIS_PROMPT, None, synth_input, fwd_headers, base_url, api_key, model, 1)
                yield json.dumps({"type": "answer", "text": final or "合成失败，请重试"}, ensure_ascii=False) + "\n"
            except urllib.error.HTTPError as exc:
                yield json.dumps({"type": "error", "text": f"AI 接口错误（{exc.code}）：请稍后重试或检查 AI 配置"}, ensure_ascii=False) + "\n"
            except Exception as exc:  # noqa: BLE001
                yield json.dumps({"type": "error", "text": f"智能体异常：{str(exc)[:200]}"}, ensure_ascii=False) + "\n"

        return StreamingResponse(
            stream(),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
