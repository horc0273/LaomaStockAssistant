from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


class WencaiService:
    """同花顺问财智能选股/问答服务（双模式兼容）。

    模式一：OpenAI 兼容 API（推荐，使用 IWENCAI_API_KEY）
      - 适合第三方封装服务或 AI 中转平台
      - 需要同时配置 IWENCAI_BASE_URL（OpenAI 兼容端点）
      - 请求头：Authorization: Bearer <api_key>

    模式二：原生 iwencai.com Cookie（使用 IWENCAI_HEXINV）
      - 直接从浏览器 Cookie 获取 hexin-v
      - 无需 base_url，直连 www.iwencai.com
      - 请求头：hexin-v: <cookie_value>

    配置优先级：
      1. 传入参数
      2. 环境变量
      3. token_file（api_key）/ hexinv_file（hexin-v）
    """

    # 原生问财 gateway
    _NATIVE_URL = "https://www.iwencai.com/gateway/urp/v7/landing/getDataList"
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        hexinv: str | None = None,
        token_file: Path | None = None,
        hexinv_file: Path | None = None,
    ) -> None:
        # --- 读取配置 ---
        self.api_key = (api_key or os.getenv("IWENCAI_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("IWENCAI_BASE_URL", "")).rstrip("/")
        self.hexinv = (hexinv or os.getenv("IWENCAI_HEXINV", "")).strip()

        if not self.api_key and token_file and token_file.exists():
            self.api_key = token_file.read_text(encoding="utf-8").strip()
        if not self.hexinv and hexinv_file and hexinv_file.exists():
            self.hexinv = hexinv_file.read_text(encoding="utf-8").strip()

        # --- 确定模式 ---
        if self.api_key and self.base_url:
            self.mode = "openai"
        elif self.hexinv:
            self.mode = "hexinv"
        elif self.api_key:
            # 有 key 但没配 base_url，给个提示性的降级
            self.mode = "openai_incomplete"
        else:
            self.mode = "none"

        self.session = requests.Session()
        if self.mode == "hexinv":
            self.session.headers.update({
                "hexin-v": self.hexinv,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json, text/javascript, */*",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.iwencai.com/unifiedwap/result",
                "Origin": "https://www.iwencai.com",
            })
        elif self.mode in ("openai", "openai_incomplete"):
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

    @property
    def enabled(self) -> bool:
        return self.mode in ("openai", "hexinv")

    # ---------- 核心调用 ----------

    def query(self, question: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """自然语言问答/选股。"""
        if not self.enabled:
            return self._not_configured()
        if self.mode == "hexinv":
            return self._query_native(question, timeout)
        return self._query_openai(question, timeout)

    def screen(self, conditions: list[str], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """条件选股。"""
        question = "，".join(conditions)
        return self.query(question, timeout=timeout)

    def screen_to_stocks(self, conditions: list[str], timeout: int = DEFAULT_TIMEOUT) -> list[dict[str, Any]]:
        """选股并返回标准化股票列表。"""
        result = self.screen(conditions, timeout=timeout)
        if not result.get("ok"):
            return []
        return result.get("items", [])

    # ---------- 原生 iwencai.com 模式 ----------

    def _query_native(self, question: str, timeout: int) -> dict[str, Any]:
        payload = {
            "query": question,
            "perpage": 100,
            "page": 1,
            "secondary_intent": "stock",
            "sort_key": "",
            "sort_order": "",
        }
        try:
            resp = self.session.post(self._NATIVE_URL, data=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            stocks = self._parse_native_stocks(data)
            return {
                "ok": True,
                "source": "iwencai-native",
                "mode": "hexinv",
                "question": question,
                "count": len(stocks),
                "items": stocks,
                "raw": data,
            }
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                return {
                    "ok": False, "error": "wencai_auth_failed",
                    "message": "hexin-v 已过期，请重新登录 iwencai.com 获取",
                    "items": [],
                }
            return {"ok": False, "error": "wencai_http_error", "message": str(exc), "items": []}
        except Exception as exc:
            return {"ok": False, "error": "wencai_exception", "message": str(exc), "items": []}

    def _parse_native_stocks(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        stocks: list[dict[str, Any]] = []
        raw = data.get("data")
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("datas") or raw.get("data") or raw.get("answer", [])
        else:
            items = data.get("answer", []) or data.get("datas", [])
        if not isinstance(items, list):
            return stocks
        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or item.get("股票代码") or item.get("symbol") or item.get("SECURITY_CODE", "")).strip()
            name = item.get("name") or item.get("股票名称") or item.get("SECURITY_NAME_ABBR", "")
            if code and "." not in code:
                code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
            stocks.append({
                "code": code,
                "name": name,
                "price": float(item.get("price") or item.get("最新价") or item.get("f2") or 0),
                "change_pct": float(item.get("change_pct") or item.get("涨跌幅") or item.get("f3") or 0),
                "market": item.get("market") or item.get("所属市场", "A股"),
                "source": "iwencai",
                "raw": item,
            })
        return stocks

    # ---------- OpenAI 兼容模式 ----------

    def _query_openai(self, question: str, timeout: int) -> dict[str, Any]:
        """通过 OpenAI 兼容接口调用（适合第三方中转/封装服务）。"""
        if self.mode == "openai_incomplete":
            return {
                "ok": False,
                "error": "wencai_incomplete_config",
                "message": (
                    "已配置 IWENCAI_API_KEY，但缺少 IWENCAI_BASE_URL。\n"
                    "请同时设置环境变量：IWENCAI_BASE_URL=https://你的中转域名/v1"
                ),
                "items": [],
            }
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": os.getenv("IWENCAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是同花顺问财智能选股助手。用户用自然语言描述选股条件，"
                        "你需要返回符合条件的 A 股列表，格式为 JSON 数组："
                        '[{"code":"代码","name":"名称","price":价格,"change_pct":涨跌幅},...]'
                    ),
                },
                {"role": "user", "content": question},
            ],
            "temperature": 0.2,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            # 尝试解析 JSON
            try:
                stocks = json.loads(content)
                if not isinstance(stocks, list):
                    stocks = []
            except json.JSONDecodeError:
                # 如果不是纯 JSON，尝试从文本中提取
                stocks = self._extract_json_from_text(content)
            return {
                "ok": True,
                "source": "iwencai-openai",
                "mode": "openai",
                "question": question,
                "count": len(stocks),
                "items": stocks,
                "raw": result,
            }
        except requests.exceptions.HTTPError as exc:
            return {"ok": False, "error": "wencai_http_error", "message": str(exc), "items": []}
        except Exception as exc:
            return {"ok": False, "error": "wencai_exception", "message": str(exc), "items": []}

    @staticmethod
    def _extract_json_from_text(text: str) -> list[dict[str, Any]]:
        """从 LLM 返回的文本中提取 JSON 数组。"""
        # 尝试找 ```json ... ``` 或 [...]
        import re
        # 找代码块
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # 找中括号数组
        m = re.search(r"(\[.*?\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return []

    # ---------- 状态 ----------

    def _not_configured(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "wencai_not_configured",
            "message": (
                "问财未配置。请二选一：\n"
                "1) 原生模式：IWENCAI_HEXINV=<浏览器Cookie hexin-v>\n"
                "2) OpenAI兼容模式：IWENCAI_API_KEY=<sk-proj-key> + IWENCAI_BASE_URL=<中转URL>"
            ),
            "items": [],
        }

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "api_key_prefix": self.api_key[:12] + "..." if len(self.api_key) > 15 else "(empty)",
            "hexinv_prefix": self.hexinv[:12] + "..." if len(self.hexinv) > 15 else "(empty)",
            "base_url": self.base_url or "(not set)",
            "native_url": self._NATIVE_URL,
        }
