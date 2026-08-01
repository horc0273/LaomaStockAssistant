from __future__ import annotations

from datetime import datetime, timedelta


class AKShareService:
    """
    AKShare 主力数据源适配器。
    提供：实时全A行情、历史K线、板块/行业数据。
    失败时自动降级到 HTTP 直连源。
    """

    def __init__(self) -> None:
        self._ak = None
        self.error = ""
        try:
            import akshare as ak

            self._ak = ak
        except Exception as exc:
            self.error = str(exc)

    @property
    def enabled(self) -> bool:
        return self._ak is not None

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "source": "AKShare",
            "mode": "primary" if self.enabled else "disabled",
            "message": "AKShare 已启用，作为主力数据源。" if self.enabled else "AKShare 未安装，将使用 HTTP 直连源。",
            "error": self.error if not self.enabled else "",
        }

    # ---------- 实时行情 ----------

    def spot_all(self) -> dict:
        """获取全A实时行情快照（东方财富接口，最稳定）。"""
        if not self.enabled:
            return {"ok": False, "source": "akshare-disabled", "items": [], "error": self.error or "not_installed"}
        try:
            df = self._ak.stock_zh_a_spot_em()
            items = []
            for _, row in df.iterrows():
                code_raw = str(row.get("代码", "")).strip()
                name = str(row.get("名称", "")).strip()
                if not code_raw or not name:
                    continue
                market = "SH" if code_raw.startswith(("5", "6", "9")) else "SZ"
                code = f"{code_raw}.{market}"
                items.append(
                    {
                        "code": code,
                        "name": name,
                        "price": float(row.get("最新价") or 0),
                        "change_pct": float(row.get("涨跌幅") or 0),
                        "change": float(row.get("涨跌额") or 0),
                        "open": float(row.get("今开") or 0),
                        "high": float(row.get("最高") or 0),
                        "low": float(row.get("最低") or 0),
                        "prev_close": float(row.get("昨收") or 0),
                        "volume": float(row.get("成交量") or 0),
                        "amount": float(row.get("成交额") or 0),
                        "turnover": float(row.get("换手率") or 0),
                        "pe_ttm": float(row.get("市盈率-动态") or 0),
                        "pb": float(row.get("市净率") or 0),
                        "market_cap": float(row.get("总市值") or 0),
                        "flow_cap": float(row.get("流通市值") or 0),
                    }
                )
            return {"ok": bool(items), "source": "akshare:stock_zh_a_spot_em", "items": items, "count": len(items), "updated_at": datetime.now().isoformat(timespec="seconds"), "error": ""}
        except Exception as exc:
            return {"ok": False, "source": "akshare", "items": [], "error": str(exc)}

    # ---------- 历史K线 ----------

    def daily(self, code: str, limit: int = 240) -> dict:
        if not self.enabled:
            return {"ok": False, "source": "akshare-disabled", "items": [], "error": self.error or "not_installed"}
        symbol = code.split(".")[0]
        end = datetime.now()
        start = end - timedelta(days=max(limit * 2, 500))
        try:
            frame = self._ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",
            )
            items = []
            for _, row in frame.tail(limit).iterrows():
                items.append(
                    {
                        "date": str(row.get("日期", ""))[:10],
                        "open": float(row.get("开盘") or 0),
                        "close": float(row.get("收盘") or 0),
                        "price": float(row.get("收盘") or 0),
                        "high": float(row.get("最高") or 0),
                        "low": float(row.get("最低") or 0),
                        "volume": float(row.get("成交量") or 0),
                        "amount": float(row.get("成交额") or 0),
                        "change_pct": float(row.get("涨跌幅") or 0),
                        "turnover": float(row.get("换手率") or 0),
                    }
                )
            return {"ok": bool(items), "source": "akshare:stock_zh_a_hist", "items": items, "updated_at": datetime.now().isoformat(timespec="seconds"), "error": ""}
        except Exception as exc:
            return {"ok": False, "source": "akshare", "items": [], "error": str(exc)}

    # ---------- 板块/行业数据 ----------

    def sector_board(self, symbol: str = "GN") -> dict:
        """
        获取板块行情。symbol: GN=概念板块, HY=行业板块, DY=地域板块。
        """
        if not self.enabled:
            return {"ok": False, "source": "akshare-disabled", "items": [], "error": self.error or "not_installed"}
        try:
            if symbol == "HY":
                df = self._ak.stock_board_industry_name_em()
            elif symbol == "DY":
                df = self._ak.stock_board_concept_name_em()  # fallback
            else:
                df = self._ak.stock_board_concept_name_em()
            items = []
            for _, row in df.head(100).iterrows():
                items.append(
                    {
                        "name": str(row.get("板块名称", row.get("名称", ""))).strip(),
                        "change_pct": float(row.get("涨跌幅") or 0),
                        "total": int(row.get("板块家数", 0)),
                        "up": int(row.get("上涨家数", 0)),
                        "down": int(row.get("下跌家数", 0)),
                        "leading": str(row.get("领涨股票", "")).strip(),
                        "leading_pct": float(row.get("领涨股-涨跌幅") or 0),
                    }
                )
            return {"ok": bool(items), "source": f"akshare:board_{symbol}", "items": items, "updated_at": datetime.now().isoformat(timespec="seconds"), "error": ""}
        except Exception as exc:
            return {"ok": False, "source": "akshare", "items": [], "error": str(exc)}
