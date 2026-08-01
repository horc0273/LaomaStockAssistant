from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests


class TushareService:
    def __init__(self, token_path: Path) -> None:
        self.token_path = token_path
        self.endpoint = "https://api.tushare.pro"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "LaomaStockAssistant/1.0"})
        self.cache: dict[str, tuple[float, dict]] = {}

    def token(self) -> str:
        configured = os.getenv("TUSHARE_TOKEN", "").strip()
        if configured:
            return configured
        if not self.token_path.exists():
            return ""
        return self.token_path.read_text(encoding="utf-8").strip()

    def save_token(self, token: str) -> dict:
        token = (token or "").strip()
        if len(token) < 8:
            return {"ok": False, "error": "invalid_token", "message": "Tushare Token 不能为空，且长度不能太短"}
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(token, encoding="utf-8")
        self.cache.clear()
        return {"ok": True, "message": "Tushare Token 已保存到服务器数据目录", "masked_token": self.mask_token(token)}

    @staticmethod
    def mask_token(token: str) -> str:
        token = token or ""
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}****{token[-4:]}"

    def config_status(self) -> dict:
        token = self.token()
        return {
            "enabled": bool(token),
            "token_saved": self.token_path.exists(),
            "token_path": str(self.token_path),
            "masked_token": self.mask_token(token) if token else "",
            "source": "env:TUSHARE_TOKEN" if os.getenv("TUSHARE_TOKEN", "").strip() else "server_file" if token else "not_configured",
        }

    def enabled(self) -> bool:
        return bool(self.token())

    @staticmethod
    def ts_code(code: str) -> str:
        raw = code.upper()
        if raw.endswith(".SH") or raw.endswith(".SZ") or raw.endswith(".BJ") or raw.endswith(".HK"):
            return raw
        return f"{raw}.SH" if raw.startswith(("5", "6", "9")) else f"{raw}.SZ"

    @staticmethod
    def rows_from_payload(payload: dict) -> list[dict]:
        data = payload.get("data") or {}
        fields = data.get("fields") or []
        rows = data.get("items") or []
        return [dict(zip(fields, row)) for row in rows]

    def query(self, api_name: str, params: dict | None = None, fields: str = "", ttl: int = 600) -> dict:
        token = self.token()
        if not token:
            return {"ok": False, "error": "missing_token", "rows": [], "source": "tushare-disabled"}
        params = params or {}
        cache_key = json.dumps({"api": api_name, "params": params, "fields": fields}, ensure_ascii=False, sort_keys=True)
        cached = self.cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < ttl:
            data = dict(cached[1])
            data["cached"] = True
            return data
        try:
            response = self.session.post(
                self.endpoint,
                json={"api_name": api_name, "token": token, "params": params, "fields": fields},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc), "rows": [], "source": "tushare"}
        if payload.get("code") != 0:
            return {
                "ok": False,
                "error": payload.get("msg") or f"tushare_code_{payload.get('code')}",
                "rows": [],
                "source": "tushare",
            }
        result = {
            "ok": True,
            "error": "",
            "rows": self.rows_from_payload(payload),
            "source": f"tushare:{api_name}",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "cached": False,
        }
        self.cache[cache_key] = (now, result)
        return result

    def status(self) -> dict:
        if not self.enabled():
            return {"enabled": False, "ok": False, "message": "Tushare Token 未配置"}
        today = datetime.now().strftime("%Y%m%d")
        result = self.query("trade_cal", {"exchange": "SSE", "start_date": today, "end_date": today}, "exchange,cal_date,is_open", ttl=3600)
        error = result.get("error") or ""
        if "频率超限" in error:
            return {
                "enabled": True,
                "ok": True,
                "message": "Tushare Pro 已接入；状态检测接口频率受限，行情接口继续使用",
                "source": result.get("source"),
                "sample_rows": len(result.get("rows", [])),
            }
        return {
            "enabled": True,
            "ok": bool(result.get("ok")),
            "message": error or "Tushare Pro 已接入",
            "source": result.get("source"),
            "sample_rows": len(result.get("rows", [])),
        }

    def daily(self, code: str, days: int = 160) -> dict:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        return self.query(
            "daily",
            {"ts_code": self.ts_code(code), "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
            ttl=1800,
        )

    def daily_basic(self, code: str, days: int = 80) -> dict:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        return self.query(
            "daily_basic",
            {"ts_code": self.ts_code(code), "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pb,total_mv,circ_mv",
            ttl=3600,
        )

    def moneyflow(self, code: str, days: int = 80) -> dict:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        return self.query(
            "moneyflow",
            {"ts_code": self.ts_code(code), "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,buy_sm_amount,sell_sm_amount,buy_md_amount,sell_md_amount,buy_lg_amount,sell_lg_amount,buy_elg_amount,sell_elg_amount,net_mf_amount",
            ttl=3600,
        )

    def minute(self, code: str, freq: str = "1min", days: int = 1) -> dict:
        end = datetime.now()
        start = end - timedelta(days=max(1, min(int(days or 1), 5)))
        return self.query(
            "stk_mins",
            {
                "ts_code": self.ts_code(code),
                "freq": freq,
                "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "ts_code,trade_time,open,close,high,low,vol,amount",
            ttl=120,
        )

    def adj_factor(self, code: str, days: int = 160) -> dict:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        return self.query(
            "adj_factor",
            {"ts_code": self.ts_code(code), "start_date": start_date, "end_date": end_date},
            "ts_code,trade_date,adj_factor",
            ttl=86400,
        )

    def company_profile(self, code: str) -> dict:
        return self.query(
            "stock_company",
            {"ts_code": self.ts_code(code)},
            "ts_code,chairman,manager,secretary,reg_capital,setup_date,province,city,introduction,website,employees,main_business,business_scope",
            ttl=86400,
        )

    def financial_indicators(self, code: str) -> dict:
        return self.query(
            "fina_indicator",
            {"ts_code": self.ts_code(code)},
            "ts_code,ann_date,end_date,eps,dt_eps,bps,ocfps,roe,roa,roic,grossprofit_margin,netprofit_margin,debt_to_assets,current_ratio,quick_ratio,assets_turn,rd_exp,basic_eps_yoy,netprofit_yoy,tr_yoy,ocf_yoy,assets_yoy,eqt_yoy",
            ttl=21600,
        )

    def income_statements(self, code: str) -> dict:
        return self.query(
            "income",
            {"ts_code": self.ts_code(code)},
            "ts_code,ann_date,f_ann_date,end_date,report_type,total_revenue,revenue,operate_profit,total_profit,n_income,n_income_attr_p,basic_eps,diluted_eps",
            ttl=21600,
        )

    def holder_numbers(self, code: str) -> dict:
        return self.query(
            "stk_holdernumber",
            {"ts_code": self.ts_code(code)},
            "ts_code,ann_date,end_date,holder_num",
            ttl=21600,
        )

    def performance_forecasts(self, code: str) -> dict:
        return self.query(
            "forecast",
            {"ts_code": self.ts_code(code)},
            "ts_code,ann_date,end_date,type,p_change_min,p_change_max,net_profit_min,net_profit_max,last_parent_net,first_ann_date,summary,change_reason",
            ttl=21600,
        )

    def analysis_bundle(self, code: str) -> dict:
        company = self.company_profile(code)
        indicators = self.financial_indicators(code)
        income = self.income_statements(code)
        holders = self.holder_numbers(code)
        forecast = self.performance_forecasts(code)
        valuation = self.daily_basic(code, days=20)
        return {
            "company_profile": {**company, "rows": company.get("rows", [])[:1]},
            "financial_indicators": {**indicators, "rows": indicators.get("rows", [])[:8]},
            "income_statements": {**income, "rows": income.get("rows", [])[:8]},
            "holder_numbers": {**holders, "rows": holders.get("rows", [])[:12]},
            "performance_forecasts": {**forecast, "rows": forecast.get("rows", [])[:6]},
            "valuation": {**valuation, "rows": valuation.get("rows", [])[:20]},
        }

    def stock_snapshot(self, code: str) -> dict:
        daily = self.daily(code)
        basic = self.daily_basic(code)
        money = self.moneyflow(code)
        adj = self.adj_factor(code)
        return {
            "enabled": self.enabled(),
            "code": self.ts_code(code),
            "daily": daily,
            "daily_basic": basic,
            "moneyflow": money,
            "adj_factor": adj,
            "sources": [item.get("source") for item in (daily, basic, money, adj) if item.get("source")],
        }
