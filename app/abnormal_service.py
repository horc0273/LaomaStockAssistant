from __future__ import annotations

from datetime import datetime
from typing import Any


class AbnormalMonitorService:
    POSITIVE_TYPES = {
        "rocket_launch": "火箭发射",
        "fast_rebound": "快速反弹",
        "large_buy": "大笔买入",
        "limit_up_seal": "封涨停板",
        "limit_up_touch": "打开涨停板",
        "large_bid": "有大买盘",
        "auction_up": "竞价上涨",
        "open_above_ma5": "高开5日线",
        "gap_up": "向上缺口",
        "new_high_60d": "60日新高",
        "surge_60d": "60日大幅上涨",
    }
    NEGATIVE_TYPES = {
        "accelerated_drop": "加速下跌",
        "high_platform_dive": "高台跳水",
        "large_sell": "大笔卖出",
        "limit_down_seal": "封跌停板",
        "limit_down_open": "打开跌停板",
        "large_ask": "有大卖盘",
        "auction_down": "竞价下跌",
        "open_below_ma5": "低开5日线",
        "gap_down": "向下缺口",
        "new_low_60d": "60日新低",
        "drop_60d": "60日大幅下跌",
    }

    def catalog(self) -> dict:
        return {
            "positive": [{"key": key, "label": label} for key, label in self.POSITIVE_TYPES.items()],
            "negative": [{"key": key, "label": label} for key, label in self.NEGATIVE_TYPES.items()],
        }

    def events(self, universe: list[dict], selected_types: list[str] | None = None, source_meta: dict | None = None) -> dict:
        selected = set(selected_types or [*self.POSITIVE_TYPES.keys(), *self.NEGATIVE_TYPES.keys()])
        now = datetime.now().isoformat(timespec="seconds")
        items: list[dict] = []
        for row in universe:
            for type_key, direction in self._detect(row):
                if type_key not in selected:
                    continue
                type_map = self.POSITIVE_TYPES if direction == "positive" else self.NEGATIVE_TYPES
                items.append({
                    "id": f"{now}-{row.get('code', '')}-{type_key}",
                    "time": now,
                    "code": row.get("code", ""),
                    "name": row.get("name", ""),
                    "direction": direction,
                    "type_key": type_key,
                    "type": type_map.get(type_key, type_key),
                    "price": row.get("price"),
                    "change_pct": row.get("change_pct"),
                    "volume": row.get("volume"),
                    "amount": row.get("amount"),
                    "industry": row.get("industry") or row.get("sector") or row.get("tag") or "",
                    "concepts": row.get("concepts") or [],
                    "source": (source_meta or {}).get("source") or row.get("source") or "unknown",
                })
        items.sort(key=lambda item: (abs(float(item.get("change_pct") or 0)), float(item.get("amount") or 0)), reverse=True)
        meta = source_meta or {}
        return {
            "items": items,
            "total": len(items),
            "source": meta.get("source", "unknown"),
            "fetched_at": meta.get("fetched_at", now),
            "latency_ms": meta.get("latency_ms"),
            "fallback_used": bool(meta.get("fallback_used")),
            "is_stale": bool(meta.get("is_stale")),
        }

    def _detect(self, row: dict[str, Any]) -> list[tuple[str, str]]:
        signals = set(row.get("signals") or [])
        change = float(row.get("change_pct") or 0)
        amount = float(row.get("amount") or 0)
        main_net = float(row.get("main_net") or 0)
        volume_ratio = float(row.get("volume_ratio") or 0)
        open_price = float(row.get("open") or 0)
        prev_close = float(row.get("prev_close") or 0)
        high = float(row.get("high") or 0)
        low = float(row.get("low") or 0)
        price = float(row.get("price") or 0)
        result: list[tuple[str, str]] = []

        def add(key: str, direction: str) -> None:
            if key not in [existing for existing, _ in result]:
                result.append((key, direction))

        if "limit_up_touch" in signals or change >= 9.5:
            add("limit_up_touch", "positive")
        if "volume_breakout" in signals or (change >= 3 and volume_ratio >= 1.8):
            add("volume_breakout", "positive")
            add("rocket_launch", "positive")
        if "gap_up" in signals or (open_price and prev_close and open_price >= prev_close * 1.01):
            add("gap_up", "positive")
        if main_net >= 50_000_000 or "large_buy" in signals:
            add("large_buy", "positive")
        if amount >= 500_000_000 and change > 0:
            add("large_bid", "positive")
        if price and low and change > 0 and price >= low * 1.03:
            add("fast_rebound", "positive")

        if "large_sell" in signals or main_net <= -50_000_000:
            add("large_sell", "negative")
        if change <= -9.5:
            add("limit_down_open", "negative")
        if change <= -4:
            add("accelerated_drop", "negative")
        if high and price and high >= price * 1.04:
            add("high_platform_dive", "negative")
        if open_price and prev_close and open_price <= prev_close * 0.99:
            add("gap_down", "negative")
        if amount >= 500_000_000 and change < 0:
            add("large_ask", "negative")
        return result
