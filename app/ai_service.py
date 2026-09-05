from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .models import Candidate, MarketOverview, WatchlistItem


class AIService:
    ANALYSIS_MODE_HINTS = {
        "decision_report": "按机构决策报告方式输出，强调结论、评分、催化、风险、执行清单。",
        "trend_following": "按趋势跟随方式输出，重点看强度延续、均线结构、量价配合、支撑压力和加减仓节奏。",
        "breakout_hunter": "按突破捕手方式输出，重点看放量突破、板块联动、次日承接、假突破风险和触发条件。",
        "rebound_repair": "按超跌修复方式输出，重点看止跌信号、缩量企稳、修复空间、失败条件和试错仓位。",
        "risk_guard": "按风险守门方式输出，优先识别回撤、估值过热、业绩兑现和公告扰动风险。",
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        self.config_path = Path(data_dir) / "ai_config.json" if data_dir else None
        self.provider = "openai"
        self.api_key = os.getenv("AI_API_KEY", "")
        self.base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("AI_MODEL", "gpt-4.1-mini")
        self.external_enabled = bool(self.api_key)
        self.active_profile_id = "default"
        self.profiles: list[dict] = []
        self._load_config()
        if not self.profiles:
            self.profiles = [self._current_profile()]

    @classmethod
    def for_personal_config(cls, config_path: Path) -> "AIService":
        service = cls(None)
        service.config_path = Path(config_path)
        service.provider = "custom"
        service.api_key = ""
        service.base_url = "https://api.deepseek.com/v1"
        service.model = "deepseek-chat"
        service.external_enabled = False
        service.active_profile_id = "default"
        service.profiles = []
        service._load_config()
        if not service.profiles:
            service.profiles = [service._current_profile()]
        return service

    @property
    def enabled(self) -> bool:
        return self.external_enabled and bool(self.api_key)

    def _load_config(self) -> None:
        if not self.config_path or not self.config_path.exists():
            return
        try:
            saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.provider = str(saved.get("provider") or self.provider)
        self.api_key = str(saved.get("api_key") or self.api_key)
        self.base_url = str(saved.get("base_url") or self.base_url).rstrip("/")
        self.model = str(saved.get("model") or self.model)
        self.external_enabled = bool(saved.get("enabled", bool(self.api_key)))
        self.active_profile_id = str(saved.get("active_profile_id") or "default")
        saved_profiles = saved.get("profiles") or []
        if isinstance(saved_profiles, list):
            self.profiles = [profile for profile in saved_profiles if isinstance(profile, dict)]
            active = next((profile for profile in self.profiles if profile.get("id") == self.active_profile_id), None)
            if active:
                self._apply_profile(active)

    def _current_profile(self) -> dict:
        return {
            "id": self.active_profile_id,
            "name": f"{self.provider} · {self.model}",
            "enabled": self.external_enabled,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
        }

    def _apply_profile(self, profile: dict) -> None:
        self.active_profile_id = str(profile.get("id") or "default")
        self.provider = str(profile.get("provider") or "custom")
        self.base_url = str(profile.get("base_url") or self.base_url).rstrip("/")
        self.model = str(profile.get("model") or self.model)
        self.api_key = str(profile.get("api_key") or "")
        self.external_enabled = bool(profile.get("enabled", True))

    @staticmethod
    def _validate(base_url: str, model: str) -> tuple[str, str]:
        normalized_url = base_url.strip().rstrip("/")
        parsed = urlparse(normalized_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Base URL 必须是有效的 http/https 地址")
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("模型名称不能为空")
        return normalized_url, normalized_model

    @staticmethod
    def _mask_key(api_key: str) -> str:
        if not api_key:
            return ""
        if len(api_key) <= 8:
            return "••••••••"
        return f"{api_key[:3]}••••{api_key[-4:]}"

    def public_config(self) -> dict:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": bool(self.api_key),
            "masked_api_key": self._mask_key(self.api_key),
            "active_profile_id": self.active_profile_id,
            "profiles": [self._public_profile(profile) for profile in self.profiles],
        }

    def _public_profile(self, profile: dict) -> dict:
        return {
            "id": profile.get("id"),
            "name": profile.get("name") or f"{profile.get('provider')} · {profile.get('model')}",
            "enabled": bool(profile.get("enabled", True) and profile.get("api_key")),
            "provider": profile.get("provider"),
            "base_url": profile.get("base_url"),
            "model": profile.get("model"),
            "has_api_key": bool(profile.get("api_key")),
            "masked_api_key": self._mask_key(str(profile.get("api_key") or "")),
        }

    def model_options(self) -> list[dict]:
        return [self._public_profile(profile) for profile in self.profiles if profile.get("enabled", True) and profile.get("api_key")]

    def save_config(self, *, enabled: bool, provider: str, base_url: str, model: str, api_key: str = "", profile_id: str = "", profile_name: str = "") -> dict:
        normalized_url, normalized_model = self._validate(base_url, model)
        existing = next((profile for profile in self.profiles if profile.get("id") == profile_id), None)
        resolved_key = api_key.strip() or str((existing or {}).get("api_key") or self.api_key)
        if enabled and not resolved_key:
            raise ValueError("启用外部 AI 时必须填写 API Key")
        resolved_id = profile_id.strip() or re.sub(r"[^a-zA-Z0-9_-]+", "-", f"{provider}-{normalized_model}").strip("-").lower() or "custom-model"
        profile = {
            "id": resolved_id,
            "name": profile_name.strip() or f"{provider.strip() or 'custom'} · {normalized_model}",
            "enabled": bool(enabled),
            "provider": provider.strip() or "custom",
            "base_url": normalized_url,
            "model": normalized_model,
            "api_key": resolved_key,
        }
        profiles = [item for item in self.profiles if item.get("id") != resolved_id and item.get("api_key")]
        profiles.append(profile)
        self.profiles = profiles
        self._apply_profile(profile)
        config = {**profile, "active_profile_id": resolved_id, "profiles": profiles}
        if self.config_path:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.config_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self.config_path)
        return self.public_config()

    def test_connection(self, *, base_url: str, model: str, api_key: str = "", profile_id: str = "") -> dict:
        normalized_url, normalized_model = self._validate(base_url, model)
        existing = next((profile for profile in self.profiles if profile.get("id") == profile_id), None)
        resolved_key = api_key.strip() or str((existing or {}).get("api_key") or self.api_key)
        if not resolved_key:
            raise ValueError("请先填写 API Key")
        body = {
            "model": normalized_model,
            "messages": [{"role": "user", "content": "只回复 OK"}],
            "temperature": 0,
            "max_tokens": 3,
        }
        payload = self._request_chat(normalized_url, resolved_key, body, timeout=20)
        answer = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "model": normalized_model, "message": answer.strip() or "连接成功"}

    def analyze_stock(
        self,
        item: WatchlistItem,
        candidate: Candidate,
        market: MarketOverview,
        sectors: list[dict],
        events: list[dict],
        *,
        model_id: str = "",
        system_prompt: str = "",
        question: str = "",
        allow_local_fallback: bool = True,
        intelligence: dict | None = None,
        analysis_mode: str = "decision_report",
    ) -> dict:
        context = self._build_context(item, candidate, market, sectors, events)
        if intelligence:
            context["market_intelligence"] = intelligence
        profile = next((entry for entry in self.profiles if entry.get("id") == model_id), None) if model_id else next((entry for entry in self.profiles if entry.get("id") == self.active_profile_id), None)
        if profile and profile.get("enabled", True) and profile.get("api_key"):
            try:
                return self._call_external_ai(context, profile, system_prompt=system_prompt, question=question, analysis_mode=analysis_mode)
            except Exception as exc:
                if not allow_local_fallback:
                    return {
                        "error": "ai_request_failed",
                        "message": str(exc),
                        "mode": "api-error",
                        "model": profile.get("model"),
                        "provider": profile.get("provider"),
                        "analysis_mode": analysis_mode,
            "assistant_role": assistant_role,
            "pitfall_checks": pitfall_checks,
            "assistant_role": assistant_role,
            "pitfall_checks": pitfall_checks,
                    }
                fallback = self._local_analysis(item, candidate, market, sectors, events, analysis_mode=analysis_mode)
                fallback["mode"] = "fallback"
                fallback["api_error"] = str(exc)
                return fallback
        if not allow_local_fallback:
            return {"error": "ai_model_required", "message": "请先在 AI 网关中配置外部模型，然后选择模型开始分析。", "mode": "setup-required", "analysis_mode": analysis_mode}
        return self._local_analysis(item, candidate, market, sectors, events, analysis_mode=analysis_mode)

    def _build_context(self, item: WatchlistItem, candidate: Candidate, market: MarketOverview, sectors: list[dict], events: list[dict]) -> dict:
        stock = item.stock
        return {
            "stock": stock.model_dump(),
            "holding": {
                "quantity": item.quantity,
                "pnl_pct": item.pnl_pct,
                "pnl_amount": item.pnl_amount,
            },
            "candidate": candidate.model_dump(),
            "market": market.model_dump(),
            "sectors": sectors,
            "events": [event for event in events if not event.get("symbols") or stock.code in event.get("symbols", [])],
        }

    def _call_external_ai(self, context: dict, profile: dict, *, system_prompt: str = "", question: str = "", analysis_mode: str = "decision_report") -> dict:
        mode_hint = self.ANALYSIS_MODE_HINTS.get(analysis_mode, self.ANALYSIS_MODE_HINTS["decision_report"])
        prompt = f"""你是严谨的A股研究助手，不是股神，也不是收益承诺器。请像成熟券商研究报告一样完成多维分析，但只能使用用户提供的结构化数据。
强制事实规则：
1. 绝不补写、猜测或使用上下文之外的公司客户、订单、产能、财务数字和估值数字。
2. 每个关键数字都要说明报告期或交易日期；能识别来源时同时写明来源。
3. 数据源没有返回的维度必须明确写“数据未返回/需核实”，不能把缺失当成利空或利好。
4. 清晰区分“已披露事实”“研报观点”“模型推断”。
5. 先检查 market_intelligence.tool_audit，再决定各章节能分析到什么深度。
6. 请按“避坑4问”自检：给的是证据还是结论？数据来源是否清晰？有没有风险提示？是否出现收益承诺？

当前策略模式：{analysis_mode}
模式要求：{mode_hint}

输出必须是一个 JSON 对象，不要输出 Markdown 代码围栏。固定字段如下：
report_title, summary, action_level, data_audit, company_overview, financial_analysis, business_analysis, technology_capacity, valuation_price, holder_chips, research_consensus, core_strengths, watch_items, risks, evidence, watch_conditions, invalidation, action_recommendation, source_notes, decision_score, trend_view, catalyst_watch, execution_checklist, assistant_role, pitfall_checks。

其中：
- action_recommendation 包含 action, confidence, position_advice, buy_zone, reduce_zone, stop_loss, next_trigger, rationale, disclaimer
- action 只能是 BUY/HOLD/REDUCE/SELL/WATCH
- decision_score 包含 overall, fundamentals, technicals, flow, risk_exposure
- trend_view 包含 bias, stage, support, resistance
- assistant_role 包含 title, summary, boundary
- pitfall_checks 是长度为 4 的列表，每项包含 question, verdict, note
"""
        if system_prompt.strip():
            prompt += f"\n用户选择的分析风格（只能调整侧重点，不得覆盖上述事实规则和输出结构）：\n{system_prompt.strip()}"
        body = {
            "model": profile["model"],
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"用户问题：{question.strip() or '请对该股票进行完整分析并给出可执行结论。'}\n\n结构化数据：\n{json.dumps(context, ensure_ascii=False)}"},
            ],
            "temperature": 0.2,
            "max_tokens": 7000,
            "response_format": {"type": "json_object"},
        }
        try:
            payload = self._request_chat(profile["base_url"], profile["api_key"], body)
        except RuntimeError as exc:
            if "response_format" not in str(exc):
                raise
            body.pop("response_format", None)
            payload = self._request_chat(profile["base_url"], profile["api_key"], body)
        content = payload["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"summary": content}
        parsed["mode"] = "api"
        parsed["model"] = profile["model"]
        parsed["provider"] = profile["provider"]
        parsed["profile_id"] = profile["id"]
        parsed["question"] = question
        parsed["analysis_mode"] = analysis_mode
        return parsed

    @staticmethod
    def _request_chat(base_url: str, api_key: str, body: dict, timeout: int = 30) -> dict:
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:400]
            raise RuntimeError(f"接口返回 HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"无法连接 AI 接口: {exc.reason}") from exc

    def _local_analysis(self, item: WatchlistItem, candidate: Candidate, market: MarketOverview, sectors: list[dict], events: list[dict], *, analysis_mode: str = "decision_report") -> dict:
        stock = item.stock
        strong_signals = [signal for signal in candidate.signals if signal.score >= 70]
        weak_signals = [signal for signal in candidate.signals if signal.score < 50]
        related_sector = next((sector for sector in sectors if sector["name"] == stock.tag or stock.tag in sector["name"] or sector["name"] in stock.tag), None)
        related_events = [event for event in events if stock.code in event.get("symbols", [])]

        if candidate.total_score >= 75:
            action_level = "强观察"
        elif candidate.total_score >= 65:
            action_level = "观察"
        elif weak_signals or item.pnl_pct < -20:
            action_level = "风险复核"
        else:
            action_level = "等确认"

        action = "WATCH"
        confidence = 55
        position_advice = "暂不加仓，等待更多证据确认。"
        buy_zone = "回踩关键均线并稳住后再评估"
        reduce_zone = "反弹到压力位但量能跟不上时分批减仓"
        stop_loss = "跌破关键支撑且放量时执行风控"
        next_trigger = "等待量价与板块共振再次确认"

        if candidate.total_score >= 78 and stock.change_pct < 6 and item.pnl_pct > -15:
            action = "BUY"
            confidence = min(88, candidate.total_score)
            position_advice = "可小仓位试探，单票仓位不要超过计划上限。"
            buy_zone = "回踩不破 20 日线，或放量突破后次日承接稳定"
            reduce_zone = "冲高放量但板块转弱时先锁定部分利润"
            next_trigger = "突破结构与主线板块继续共振"
        elif item.pnl_pct < -25 and candidate.total_score < 65:
            action = "REDUCE"
            confidence = 72
            position_advice = "优先降低风险暴露，只保留少量观察仓。"
            buy_zone = "不建议补仓，除非重新站回关键均线"
            reduce_zone = "反弹到短期压力位但无法放量突破"
            stop_loss = "继续放量下跌或跌破阶段低点"
            next_trigger = "先看止跌，不看进攻"
        elif stock.change_pct > 6 or (stock.cost < 0 and item.pnl_amount > 0):
            action = "HOLD"
            confidence = 70
            position_advice = "持有盈利仓位，优先保护利润，不追高。"
            buy_zone = "不建议追高，等待回踩"
            reduce_zone = "高位放量滞涨、顶背离或板块资金流出"
            stop_loss = "跌破 5/10 日短线趋势或利润回撤扩大"
            next_trigger = "观察是否继续强于板块"
        elif item.pnl_pct < -18 and candidate.total_score >= 65:
            action = "HOLD"
            confidence = 62
            position_advice = "暂持观察，不盲目补仓，等修复信号。"
            buy_zone = "出现有效止跌和量能修复后再考虑"
            reduce_zone = "反弹缩量且无法站回关键均线"
            stop_loss = "再次跌破阶段低点"
            next_trigger = "均线修复与资金回流"
        elif candidate.total_score < 55:
            action = "SELL"
            confidence = 66
            position_advice = "模型不支持继续持有，适合退出或显著降仓。"
            buy_zone = "暂不考虑"
            reduce_zone = "当前或反弹减仓"
            stop_loss = "优先处理风险，不等待额外确认"
            next_trigger = "重新进入候选评分前不跟踪"

        evidence = [
            f"市场状态：{market.mood}，上涨/下跌家数 {market.up_count}/{market.down_count}",
            f"候选评分：{candidate.total_score}，推荐状态：{candidate.recommendation}",
            f"持仓盈亏：{item.pnl_pct:.2f}% / {item.pnl_amount:.2f}",
        ]
        if related_sector:
            evidence.append(f"板块：{related_sector['name']}，强度 {related_sector.get('strength', '-')}")
        evidence.extend([f"模型：{signal.name} {signal.status}，分数 {signal.score}" for signal in strong_signals[:3]])

        risks = []
        if item.pnl_pct < -20:
            risks.append("持仓浮亏较深，优先确认是否继续破位。")
        if stock.change_pct > 5:
            risks.append("当日涨幅较大，需警惕冲高回落和假突破。")
        if stock.cost < 0:
            risks.append("券商显示负成本时，盈亏率参考意义较弱。")
        if not risks:
            risks.append("主要风险来自市场风格切换和信号失效。")

        watch_conditions = [
            "是否站回/守住 20 日线",
            "成交量是否从缩量转为温和放量",
            "板块强度是否继续靠前",
            "主力资金估算是否持续改善",
        ]

        report_sections = [
            {
                "title": "一、当前行情与持仓",
                "items": [
                    f"最新价 {stock.price:.2f}，涨跌幅 {stock.change_pct:.2f}%",
                    f"持仓数量 {item.quantity}，浮盈亏 {item.pnl_pct:.2f}% / {item.pnl_amount:.2f}",
                    f"数据源 {stock.source}",
                ],
            },
            {
                "title": "二、模型判断",
                "items": [f"{signal.name}: {signal.status}，分数 {signal.score}" for signal in candidate.signals],
            },
            {
                "title": "三、板块与资金",
                "items": [
                    f"所属主题 {stock.tag}",
                    f"相关板块 {related_sector['name']}，强度 {related_sector.get('strength', '-')}" if related_sector else "暂无强相关板块数据",
                    f"市场状态：{market.mood}",
                ],
            },
            {
                "title": "四、操作结论",
                "items": [
                    f"动作：{action}",
                    f"置信度：{confidence}",
                    position_advice,
                ],
            },
        ]

        decision_score = {
            "overall": max(0, min(100, candidate.total_score)),
            "fundamentals": max(35, min(95, 60 + candidate.sector_strength // 2 - candidate.risk_penalty)),
            "technicals": max(35, min(95, int(sum(signal.score for signal in candidate.signals) / max(1, len(candidate.signals))))),
            "flow": max(30, min(95, 50 + candidate.fund_strength // 2)),
            "risk_exposure": max(5, min(95, 30 + candidate.risk_penalty * 4)),
        }
        trend_view = {
            "bias": "偏多" if candidate.total_score >= 75 else "震荡观察" if candidate.total_score >= 60 else "偏弱",
            "stage": "突破跟踪" if analysis_mode == "breakout_hunter" else "趋势延续" if analysis_mode == "trend_following" else "标准决策评估",
            "support": f"{min(stock.price, max(stock.cost or stock.price, stock.price * 0.97)):.2f}",
            "resistance": f"{max(stock.price * 1.03, stock.take_profit or stock.price * 1.05):.2f}",
        }
        assistant_role = {
            "title": "AI研究助手",
            "summary": "AI 在股市里最适合做研究助理，帮助整理证据、补全视角、提示风险，不替代人工拍板。",
            "boundary": "不承诺收益，不神化预测，最终交易必须由人确认。",
        }
        pitfall_checks = [
            {"question": "它给的是证据，还是结论？", "verdict": "证据优先", "note": "先看数据、公告、研报、资金流和模型依据，再看动作建议。"},
            {"question": "数据来源清不清晰？", "verdict": "已标来源", "note": "优先展示行情、公告、研报和资金流来源；缺失时明确写出待核实。"},
            {"question": "有没有风险提示？", "verdict": "必须有", "note": "每次分析都要同时给出风险、失效条件和观察条件。"},
            {"question": "是不是一上来就承诺收益？", "verdict": "禁止承诺", "note": "AI 只做研究辅助，不输出稳赚表述。"},
        ]
        catalyst_watch = [
            related_events[0]["title"] if related_events else "等待新增公告、研报或资金流拐点",
            f"板块 {related_sector['name']} 强度是否继续维持在 {related_sector.get('strength', '-')}" if related_sector else "关注板块是否重新走强",
            next_trigger,
        ]

        execution_checklist = [
            f"确认策略模式：{analysis_mode}",
            f"执行动作：{action}，置信度 {confidence}/100",
            f"买点参考：{buy_zone}",
            f"风控条件：{stop_loss}",
            "若次日量价结构与预期不一致，先缩小仓位再重新评估",
        ]

        return {
            "mode": "default",
            "model": "local-rule-engine",
            "provider": "local",
            "analysis_mode": analysis_mode,
            "assistant_role": assistant_role,
            "pitfall_checks": pitfall_checks,
            "report_title": f"{stock.name} 决策分析",
            "summary": f"{stock.name} 当前动作建议为 {action}。{candidate.reason}",
            "decision_score": decision_score,
            "trend_view": trend_view,
            "catalyst_watch": catalyst_watch,
            "execution_checklist": execution_checklist,
            "action_recommendation": {
                "action": action,
                "confidence": confidence,
                "position_advice": position_advice,
                "buy_zone": buy_zone,
                "reduce_zone": reduce_zone,
                "stop_loss": stop_loss,
                "next_trigger": next_trigger,
                "rationale": candidate.reason,
                "disclaimer": "系统动作建议仅供内部辅助决策，最终交易请人工确认。",
            },
            "report_sections": report_sections,
            "evidence": evidence,
            "risks": risks,
            "watch_conditions": watch_conditions,
            "invalidation": "跌破关键支撑/20 日线，或放量下跌且板块资金继续流出。",
            "action_level": action_level,
            "related_events": related_events,
            "core_strengths": [signal.name for signal in strong_signals[:3]] or ["暂无显著强势信号"],
            "watch_items": [
                "确认下一交易日承接强度",
                "检查公告与研报是否出现新分歧",
                "观察板块热度是否持续",
            ],
            "source_notes": ["本地规则引擎输出，未调用外部大模型。"],
        }
