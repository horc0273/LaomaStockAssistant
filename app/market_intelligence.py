from __future__ import annotations

from datetime import datetime, timedelta

import requests

from .tushare_service import TushareService


class MarketIntelligenceService:
    def __init__(self, session: requests.Session, tushare: TushareService) -> None:
        self.session = session
        self.tushare = tushare

    @staticmethod
    def raw_code(code: str) -> str:
        return code.upper().split(".")[0]

    @staticmethod
    def secid(code: str) -> str:
        raw = MarketIntelligenceService.raw_code(code)
        return f"1.{raw}" if raw.startswith(("5", "6", "9")) else f"0.{raw}"

    def announcements(self, code: str, limit: int = 20) -> dict:
        raw = self.raw_code(code)
        try:
            response = self.session.get(
                "https://np-anotice-stock.eastmoney.com/api/security/ann",
                params={"sr": -1, "page_size": limit, "page_index": 1, "ann_type": "A", "client_source": "web", "stock_list": raw},
                headers={"Referer": "https://data.eastmoney.com/"},
                timeout=8,
            )
            response.raise_for_status()
            response.encoding = "utf-8"
            rows = (response.json().get("data") or {}).get("list") or []
            items = []
            for row in rows[:limit]:
                columns = row.get("columns") or []
                items.append({"title": row.get("title", ""), "date": str(row.get("notice_date", ""))[:10], "type": columns[0].get("column_name", "公告") if columns else "公告", "url": f"https://data.eastmoney.com/notices/detail/{raw}/{row.get('art_code', '')}.html", "source": "东方财富公告"})
            if items:
                return {"ok": True, "source": "eastmoney-announcement", "items": items, "updated_at": datetime.now().isoformat(timespec="seconds")}
        except Exception as exc:
            error = str(exc)
        else:
            error = "empty_result"
        result = self.tushare.query("anns_d", {"ts_code": self.tushare.ts_code(code)}, "ann_date,ts_code,name,title,url", ttl=900)
        items = [{"title": row.get("title", ""), "date": row.get("ann_date", ""), "type": "公告", "url": row.get("url", ""), "source": "Tushare"} for row in result.get("rows", [])[:limit]]
        return {"ok": bool(items), "source": result.get("source", "tushare:anns_d"), "items": items, "error": result.get("error") or error}

    def research_reports(self, code: str, limit: int = 20) -> dict:
        raw = self.raw_code(code)
        end = datetime.now()
        begin = end - timedelta(days=365)
        try:
            response = self.session.get(
                "https://reportapi.eastmoney.com/report/list",
                params={"pageSize": limit, "pageNo": 1, "code": raw, "qType": 0, "beginTime": begin.strftime("%Y-%m-%d"), "endTime": end.strftime("%Y-%m-%d")},
                headers={"Referer": "https://data.eastmoney.com/report/"},
                timeout=8,
            )
            response.raise_for_status()
            response.encoding = "utf-8"
            rows = response.json().get("data") or []
            items = [{"title": row.get("title", ""), "date": str(row.get("publishDate", ""))[:10], "institution": row.get("orgSName", ""), "rating": row.get("emRatingName", ""), "researcher": row.get("researcher", ""), "url": f"https://data.eastmoney.com/report/info/{row.get('infoCode', '')}.html", "source": "东方财富研报"} for row in rows[:limit]]
            if items:
                return {"ok": True, "source": "eastmoney-research", "items": items, "updated_at": datetime.now().isoformat(timespec="seconds")}
        except Exception as exc:
            error = str(exc)
        else:
            error = "empty_result"
        result = self.tushare.query("report_rc", {"ts_code": self.tushare.ts_code(code)}, "report_date,ts_code,name,title,org_name,author,quarter,op_rt,op_pr", ttl=3600)
        items = [{"title": row.get("title", ""), "date": row.get("report_date", ""), "institution": row.get("org_name", ""), "rating": row.get("quarter", ""), "researcher": row.get("author", ""), "url": "", "source": "Tushare"} for row in result.get("rows", [])[:limit]]
        return {"ok": bool(items), "source": result.get("source", "tushare:report_rc"), "items": items, "error": result.get("error") or error}

    def stock_fund_flow(self, code: str, limit: int = 20) -> dict:
        result = self.tushare.moneyflow(code, days=max(limit * 2, 40))
        rows = result.get("rows", [])[:limit]
        if rows:
            items = [{"date": row.get("trade_date", ""), "main_net_wan": round(float(row.get("net_mf_amount") or 0), 2), "large_net_wan": round(float(row.get("buy_lg_amount") or 0) + float(row.get("buy_elg_amount") or 0) - float(row.get("sell_lg_amount") or 0) - float(row.get("sell_elg_amount") or 0), 2), "source": "Tushare moneyflow"} for row in rows]
            return {"ok": True, "source": result.get("source"), "items": items, "updated_at": result.get("updated_at")}
        try:
            response = self.session.get(
                "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
                params={"lmt": limit, "klt": 101, "secid": self.secid(code), "fields1": "f1,f2,f3,f7", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63"},
                headers={"Referer": "https://quote.eastmoney.com/"},
                timeout=8,
            )
            response.raise_for_status()
            response.encoding = "utf-8"
            klines = ((response.json().get("data") or {}).get("klines") or [])[-limit:]
            items = []
            for line in reversed(klines):
                cols = line.split(",")
                items.append({"date": cols[0], "main_net_wan": round(float(cols[1]) / 10000, 2), "large_net_wan": round((float(cols[3]) + float(cols[5])) / 10000, 2), "source": "东方财富资金流"})
            return {"ok": bool(items), "source": "eastmoney-fund-flow", "items": items, "updated_at": datetime.now().isoformat(timespec="seconds")}
        except Exception as exc:
            return {"ok": False, "source": "unavailable", "items": [], "error": str(exc)}

    def _eastmoney_dataset(self, report_name: str, filter_text: str, sort_columns: str, limit: int) -> dict:
        try:
            response = self.session.get(
                "https://datacenter-web.eastmoney.com/api/data/v1/get",
                params={
                    "reportName": report_name,
                    "columns": "ALL",
                    "filter": filter_text,
                    "pageNumber": 1,
                    "pageSize": limit,
                    "sortColumns": sort_columns,
                    "sortTypes": -1,
                },
                headers={"Referer": "https://data.eastmoney.com/", "User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            response.raise_for_status()
            rows = ((response.json().get("result") or {}).get("data") or [])[:limit]
            return {"ok": bool(rows), "rows": rows, "source": f"eastmoney:{report_name}", "updated_at": datetime.now().isoformat(timespec="seconds")}
        except Exception as exc:
            return {"ok": False, "rows": [], "source": f"eastmoney:{report_name}", "error": str(exc)}

    def _capital_event_section(self, key: str, name: str, dataset: dict, date_fields: tuple[str, ...], title_fields: tuple[str, ...], date_filter: set[str] | None = None) -> dict:
        rows = dataset.get("rows") or []
        items = []
        all_dates = []
        for row in rows:
            date = next((str(row.get(field, ""))[:10] for field in date_fields if row.get(field)), "")
            if date:
                all_dates.append(date)
            if date_filter and date and date not in date_filter:
                continue
            title = next((str(row.get(field, "")) for field in title_fields if row.get(field)), "")
            if not title:
                security_name = row.get("SECURITY_NAME_ABBR") or row.get("SECURITY_NAME") or row.get("SECUCODE") or row.get("SECURITY_CODE") or ""
                title = f"{security_name} {name}".strip()
            items.append({"date": date, "title": title, "raw": row})
        return {
            "key": key,
            "name": name,
            "ok": bool(items) or bool(dataset.get("ok")),
            "source": dataset.get("source", ""),
            "updated_at": dataset.get("updated_at"),
            "count": len(items),
            "items": items,
            "latest_date": max(all_dates) if all_dates else "",
            "error": dataset.get("error"),
        }

    def capital_events(self, code: str, limit: int = 12, window: str = "today") -> dict:
        raw = self.raw_code(code)
        ts_code = self.tushare.ts_code(code)
        today = datetime.now().date()
        if window == "today":
            date_filter = {today.isoformat()}
        elif window == "recent":
            date_filter = {(today - timedelta(days=offset)).isoformat() for offset in range(6)}
        else:
            date_filter = None
        sections = {
            "dragon_tiger": self._capital_event_section(
                "dragon_tiger",
                "龙虎榜席位",
                self._eastmoney_dataset("RPT_DAILYBILLBOARD_DETAILS", f'(SECURITY_CODE="{raw}")', "TRADE_DATE", limit),
                ("TRADE_DATE", "TDATE", "DATE"),
                ("EXPLAIN", "REASON_TYPE", "SECURITY_NAME_ABBR", "SECURITY_NAME"), date_filter,
            ),
            "restricted_release": self._capital_event_section(
                "restricted_release",
                "限售解禁",
                self._eastmoney_dataset("RPT_LIFT_STAGE", f'(SECURITY_CODE="{raw}")', "LIFT_DATE", limit),
                ("LIFT_DATE", "FREE_DATE", "TRADE_DATE", "END_DATE"),
                ("LIFT_MARKET_CAP", "SECURITY_NAME_ABBR", "SECURITY_NAME"), date_filter,
            ),
            "margin_trading": self._capital_event_section(
                "margin_trading",
                "融资融券",
                self._eastmoney_dataset("RPTA_WEB_RZRQ_GGMX", f'(SECURITY_CODE="{raw}")', "TRADE_DATE", limit),
                ("TRADE_DATE", "DATE"),
                ("SECURITY_NAME_ABBR", "SECURITY_NAME", "SECUCODE"), date_filter,
            ),
            "block_trade": self._capital_event_section(
                "block_trade",
                "大宗交易",
                self._eastmoney_dataset("RPT_BLOCKTRADE_STA", f'(SECURITY_CODE="{raw}")', "TRADE_DATE", limit),
                ("TRADE_DATE", "DEAL_DATE", "DATE"),
                ("SECURITY_NAME_ABBR", "SECURITY_NAME", "BUYER_NAME", "SELLER_NAME"), date_filter,
            ),
            "holder_change": self._capital_event_section(
                "holder_change",
                "股东户数变化",
                self._eastmoney_dataset("RPT_HOLDERNUM_DET", f'(SECURITY_CODE="{raw}")', "END_DATE", limit),
                ("END_DATE", "HOLDER_END_DATE", "TRADE_DATE"),
                ("SECURITY_NAME_ABBR", "SECURITY_NAME", "SECUCODE"), date_filter,
            ),
        }
        ok = any(section.get("ok") for section in sections.values())
        return {
            "ok": ok,
            "source": "eastmoney-datacenter-web",
            "code": ts_code,
            "raw_code": raw,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "window": window if window in {"today", "recent", "all"} else "today",
            "latest_available_date": max((section.get("latest_date", "") for section in sections.values()), default=""),
            "sections": sections,
            "message": "" if ok else "东方财富资金事件接口暂未返回有效数据，可稍后刷新或改用公告/资金流交叉验证。",
        }

    def analysis_fundamentals(self, code: str) -> dict:
        raw = self.raw_code(code)
        ts_code = self.tushare.ts_code(code)
        bundle = self.tushare.analysis_bundle(code)
        finance = self._eastmoney_dataset("RPT_F10_FINANCE_MAINFINADATA", f'(SECUCODE="{ts_code}")', "REPORT_DATE", 8)
        holders = self._eastmoney_dataset("RPT_HOLDERNUM_DET", f'(SECURITY_CODE="{raw}")', "END_DATE", 12)
        company = self._eastmoney_dataset("RPT_F10_BASIC_ORGINFO", f'(SECUCODE="{ts_code}")', "SECUCODE", 1)
        if not bundle["financial_indicators"].get("rows") and finance.get("rows"):
            bundle["financial_indicators"] = finance
        if not bundle["income_statements"].get("rows") and finance.get("rows"):
            bundle["income_statements"] = finance
        if not bundle["holder_numbers"].get("rows") and holders.get("rows"):
            bundle["holder_numbers"] = holders
        if not bundle["company_profile"].get("rows") and company.get("rows"):
            bundle["company_profile"] = company
        bundle["enabled"] = self.tushare.enabled() or any(item.get("ok") for item in (finance, holders, company))
        bundle["message"] = "" if bundle["enabled"] else "Tushare 与东方财富财务接口均未返回数据。"
        bundle["fallback_sources"] = [finance.get("source"), holders.get("source"), company.get("source")]
        return bundle
