from __future__ import annotations

from datetime import datetime, timedelta


class AKShareService:
    """Optional AKShare adapter used as a cross-check/fallback, never as silent truth."""

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
            "mode": "optional-cross-check",
            "message": "AKShare 已启用，作为历史行情交叉验证与备用源。" if self.enabled else "AKShare 未安装；当前继续使用 Tushare/东方财富/腾讯。",
            "error": self.error if not self.enabled else "",
        }

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
