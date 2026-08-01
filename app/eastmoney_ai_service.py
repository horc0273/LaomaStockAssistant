from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


class EastMoneyAIService:
    """东方财富妙想 AI 服务（go-stock 同款接口）。

    接口来源：逆向自 go-stock 项目（GitHub: ArvinLovegood/go-stock）。
    BASE_URL 与路径均与 go-stock 保持一致，请求头带 em_base_info。
    """

    BASE_URL = "https://ai-saas.eastmoney.com"
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        api_key: str | None = None,
        qgqp_b_id: str | None = None,
        token_file: Path | None = None,
        cookie_file: Path | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("EASTMONEY_AI_API_KEY", "").strip()
        self.qgqp_b_id = qgqp_b_id or os.getenv("EASTMONEY_QGQP_B_ID", "").strip()

        if not self.api_key and token_file and token_file.exists():
            self.api_key = token_file.read_text(encoding="utf-8").strip()
        if not self.qgqp_b_id and cookie_file and cookie_file.exists():
            self.qgqp_b_id = cookie_file.read_text(encoding="utf-8").strip()

        self.session = requests.Session()
        headers: dict[str, str] = {
            "em-api-key": self.api_key,
            "em_base_info": json.dumps({"productType": "mx"}),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://ai.eastmoney.com",
            "Referer": "https://ai.eastmoney.com/",
        }
        if self.qgqp_b_id:
            headers["Cookie"] = f"qgqp_b_id={self.qgqp_b_id}"
        self.session.headers.update(headers)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _post(self, path: str, payload: dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "error": "em_ai_not_configured", "message": "东财 AI API Key 未配置"}
        try:
            resp = self.session.post(
                f"{self.BASE_URL}{path}",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return {"ok": True, "source": "eastmoney-ai", "data": resp.json()}
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None:
                if exc.response.status_code == 401:
                    return {"ok": False, "error": "em_ai_auth_failed", "message": "东财 AI Key 无效"}
                if exc.response.status_code == 403:
                    return {"ok": False, "error": "em_ai_forbidden", "message": "东财 Cookie (qgqp_b_id) 可能已失效，请重新获取"}
            return {"ok": False, "error": "em_ai_http_error", "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": "em_ai_exception", "message": str(exc)}

    # ---------- 核心能力接口（路径与 go-stock 一致） ----------

    def hotspot_discovery(self, question: str = "今日热点") -> dict[str, Any]:
        """AI 热点发现 — 早盘简报的核心数据来源。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/hotspot-discovery", {"question": question})

    def ask(self, question: str) -> dict[str, Any]:
        """金融问答。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/ask", {"question": question})

    def performance_review(self, code: str) -> dict[str, Any]:
        """个股业绩点评。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/write/performance/comment", {"code": code})

    def report_list(self, code: str) -> dict[str, Any]:
        """研报列表。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/write/choice/reportList", {"code": code})

    def industry_research(self, question: str) -> dict[str, Any]:
        """行业研究。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/write/industry/research", {"question": question})

    def tracking_report(self, code: str) -> dict[str, Any]:
        """跟踪报告。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/write/tracking/report", {"code": code})

    def comparable_company_analysis(self, code: str) -> dict[str, Any]:
        """可比公司分析。"""
        return self._post("/proxy/app-robo-advisor-api/assistant/comparable-company-analysis", {"code": code})

    def dialog_tags(self, text: str) -> dict[str, Any]:
        """实体识别 / 标签解析。"""
        return self._post("/proxy/entity/dialogTagsV2", {"text": text})

    def search_data(self, query: str) -> dict[str, Any]:
        """金融数据查询（MCP 工具）。"""
        return self._post("/proxy/b/mcp/tool/searchData", {"query": query})

    def search_news(self, query: str) -> dict[str, Any]:
        """金融资讯搜索（MCP 工具）。"""
        return self._post("/proxy/b/mcp/tool/searchNews", {"query": query})

    # ---------- 兼容旧路由的别名 ----------

    def stock_analysis(self, code: str, name: str = "") -> dict[str, Any]:
        """个股 AI 深度分析（别名：底层调用 ask）。"""
        q = f"请深度分析股票 {code}"
        if name:
            q += f" {name}"
        q += "的基本面、技术面、资金面及投资价值"
        return self.ask(q)

    def market_sentiment(self) -> dict[str, Any]:
        """市场情绪分析（别名：底层调用 ask）。"""
        return self.ask("当前市场情绪如何？大盘方向和热点板块分析")

    def chat(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """通用 AI 问答（别名：底层调用 ask）。"""
        payload: dict[str, Any] = {"question": question}
        if context:
            payload.update(context)
        return self.ask(question)

    # ---------- 状态接口 ----------

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "api_key_prefix": self.api_key[:12] + "..." if len(self.api_key) > 15 else "(empty)",
            "has_cookie": bool(self.qgqp_b_id),
            "base_url": self.BASE_URL,
        }
