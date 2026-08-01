from __future__ import annotations

import re
from typing import Any


class StrategyValidationError(ValueError):
    pass


class ScreenerService:
    FIELD_CATALOG = {
        "price": "最新价", "change_pct": "涨跌幅", "amount": "成交额", "turnover_rate": "换手率",
        "volume_ratio": "量比", "pe_ttm": "市盈率TTM", "pb": "市净率", "market_cap": "总市值",
        "main_net": "主力净流入", "sector_strength": "板块强度",
    }
    OPS = {">", ">=", "<", "<=", "==", "between"}
    SIGNALS = {
        "macd_golden_cross": "MACD金叉", "kdj_golden_cross": "KDJ金叉", "volume_breakout": "放量突破",
        "ma_bullish": "均线多头", "low_fund_inflow": "低位资金流入", "continuous_volume": "连续放量",
        "gap_up": "向上跳空", "bullish_engulfing": "阳包阴", "trend_reversal": "趋势反转",
    }

    def catalog(self) -> dict:
        return {
            "fields": [{"key": key, "label": value} for key, value in self.FIELD_CATALOG.items()],
            "operators": sorted(self.OPS),
            "signals": [{"key": key, "label": value} for key, value in self.SIGNALS.items()],
            "hot_strategies": self.hot_strategies(),
        }

    def hot_strategies(self) -> list[dict]:
        return [
            {"id": "turnover_value", "name": "活跃资金过滤", "description": "换手与成交额共振", "dsl": {"all": [{"field": "turnover_rate", "op": ">=", "value": 3}, {"field": "amount", "op": ">=", "value": 500_000_000}], "sort": [{"field": "main_net", "direction": "desc"}], "limit": 50}},
            {"id": "low_valuation", "name": "低估值质量观察", "description": "正PE且不高于30倍", "dsl": {"all": [{"field": "pe_ttm", "op": "between", "value": [0, 30]}], "sort": [{"field": "amount", "direction": "desc"}], "limit": 50}},
            {"id": "momentum", "name": "动量资金共振", "description": "涨幅、量比和主力净流入", "dsl": {"all": [{"field": "change_pct", "op": ">=", "value": 2}, {"field": "volume_ratio", "op": ">=", "value": 1.2}, {"field": "main_net", "op": ">", "value": 0}], "sort": [{"field": "main_net", "direction": "desc"}], "limit": 30}},
        ]

    def validate_dsl(self, dsl: dict) -> dict:
        if not isinstance(dsl, dict):
            raise StrategyValidationError("策略必须是对象")
        conditions = dsl.get("all") or []
        if not isinstance(conditions, list) or len(conditions) > 20:
            raise StrategyValidationError("条件数量必须在0到20之间")
        for condition in conditions:
            if not isinstance(condition, dict):
                raise StrategyValidationError("条件格式错误")
            if "signal" in condition:
                if condition["signal"] not in self.SIGNALS:
                    raise StrategyValidationError(f"不支持的形态：{condition['signal']}")
                continue
            if condition.get("field") not in self.FIELD_CATALOG:
                raise StrategyValidationError(f"不支持的字段：{condition.get('field')}")
            if condition.get("op") not in self.OPS:
                raise StrategyValidationError(f"不支持的操作符：{condition.get('op')}")
            value = condition.get("value")
            if condition.get("op") == "between":
                if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, (int, float)) for item in value):
                    raise StrategyValidationError("区间条件需要两个数字")
            elif not isinstance(value, (int, float)):
                raise StrategyValidationError("比较值必须是数字")
        sorts = dsl.get("sort") or []
        if not isinstance(sorts, list) or len(sorts) > 3:
            raise StrategyValidationError("排序字段最多3个")
        for sort in sorts:
            if sort.get("field") not in self.FIELD_CATALOG or sort.get("direction") not in {"asc", "desc"}:
                raise StrategyValidationError("排序配置无效")
        limit = dsl.get("limit", 50)
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise StrategyValidationError("结果数量必须在1到200之间")
        return {"all": conditions, "sort": sorts, "limit": limit}

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        if not isinstance(actual, (int, float)):
            return False
        if op == ">": return actual > expected
        if op == ">=": return actual >= expected
        if op == "<": return actual < expected
        if op == "<=": return actual <= expected
        if op == "==": return actual == expected
        if op == "between": return expected[0] <= actual <= expected[1]
        return False

    def run(self, universe: list[dict], dsl: dict, source_meta: dict | None = None) -> dict:
        validated = self.validate_dsl(dsl)
        items = []
        for row in universe:
            matched = []
            for condition in validated["all"]:
                if "signal" in condition:
                    ok = condition["signal"] in (row.get("signals") or [])
                    label = self.SIGNALS.get(condition["signal"], condition["signal"])
                else:
                    ok = self._compare(row.get(condition["field"]), condition["op"], condition["value"])
                    label = f"{self.FIELD_CATALOG[condition['field']]} {condition['op']} {condition['value']}"
                if not ok:
                    break
                matched.append(label)
            else:
                items.append({**row, "matched_conditions": matched, "matched_count": len(matched)})
        for sort in reversed(validated["sort"]):
            items.sort(key=lambda item: item.get(sort["field"]) if isinstance(item.get(sort["field"]), (int, float)) else float("-inf"), reverse=sort["direction"] == "desc")
        meta = source_meta or {}
        return {"items": items[:validated["limit"]], "total": len(items), "scanned_count": len(universe), "dsl": validated, "source": meta.get("source", "unknown"), "fetched_at": meta.get("fetched_at", ""), "latency_ms": meta.get("latency_ms"), "is_stale": bool(meta.get("is_stale")), "fallback_used": bool(meta.get("fallback_used"))}

    def parse_natural_language(self, text: str) -> dict:
        conditions = []
        mappings = [
            (r"换手率(?:大于|高于|超过)\s*([\d.]+)%?", "turnover_rate", ">"),
            (r"换手率(?:不低于|至少)\s*([\d.]+)%?", "turnover_rate", ">="),
            (r"(?:市盈率|PE)(?:低于|小于)\s*([\d.]+)", "pe_ttm", "<"),
            (r"(?:市盈率|PE)(?:不高于|小于等于)\s*([\d.]+)", "pe_ttm", "<="),
            (r"涨幅(?:大于|高于|超过)\s*([\d.]+)%?", "change_pct", ">"),
            (r"量比(?:大于|高于|超过)\s*([\d.]+)", "volume_ratio", ">"),
        ]
        for pattern, field, op in mappings:
            match = re.search(pattern, text, re.I)
            if match:
                conditions.append({"field": field, "op": op, "value": float(match.group(1))})
        for key, label in self.SIGNALS.items():
            if label in text:
                conditions.append({"signal": key, "within_days": 3})
        sorts = []
        if "主力净流入" in text and ("排序" in text or "优先" in text):
            sorts.append({"field": "main_net", "direction": "desc"})
        limit_match = re.search(r"(?:最多|前)\s*(\d+)\s*只", text)
        result = {"all": conditions, "sort": sorts, "limit": min(200, int(limit_match.group(1))) if limit_match else 50, "original_text": text}
        self.validate_dsl(result)
        return result

    @staticmethod
    def recommendation_metrics(entry_price: float, later_prices: list[float]) -> dict:
        if entry_price <= 0 or not later_prices:
            return {"return_1d_pct": None, "return_3d_pct": None, "return_5d_pct": None, "max_return_pct": None, "max_drawdown_pct": None}
        returns = [round((price / entry_price - 1) * 100, 2) for price in later_prices]
        peak = later_prices[0]
        drawdowns = []
        for price in later_prices:
            peak = max(peak, price)
            drawdowns.append((price / peak - 1) * 100)
        at = lambda days: returns[min(days, len(returns)) - 1]
        return {"return_1d_pct": at(1), "return_3d_pct": at(3), "return_5d_pct": at(5), "return_10d_pct": at(10), "max_return_pct": max(returns), "max_drawdown_pct": round(min(drawdowns), 2)}


ScreenerService.SIGNALS.update({
    "high_fund_outflow": "高位资金净流出", "break_ma5": "向上突破5日均线", "ma_bearish": "均线空头排列",
    "shrinking_drop": "跌跌无量", "single_big_bull": "一根大阳线", "two_big_bull": "两根大阳线",
    "sunrise": "旭日东升", "strong_multi_bull": "强势多方炮", "cloud_break": "拨云见日",
    "immortal_guide": "仙人指路", "nine_sun_power": "九阳神功", "four_bull_series": "四串阳",
    "sky_volume_rule": "天量法则", "volume_attack": "放量上攻", "head_break": "穿头破脚",
    "inverted_hammer": "倒转锤头", "shooting_star": "射击之星", "evening_star": "黄昏之星",
    "dawn_break": "曙光初现", "pregnant_six": "身怀六甲", "dark_cloud": "乌云盖顶",
    "morning_star": "早晨之星", "narrow_range": "窄幅整理", "limit_up_touch": "打开涨停板",
    "large_sell": "大笔卖出", "popularity_rank_up_3d": "人气排名连涨3天", "popularity_rank_up_5d": "人气排名连涨5天",
    "popularity_rank_up_7d": "人气排名连涨7天", "follow_rank_top10_7d": "7日关注排名前10名",
    "follow_rank_top50_7d": "7日关注排名前50名", "follow_rank_top100_7d": "7日关注排名前100名",
    "rise_days_3": "连涨3天", "rise_days_5": "连涨5天", "rise_days_8": "连涨8天",
    "fall_days_3": "连跌3天", "fall_days_5": "连跌5天", "fall_days_8": "连跌8天",
    "fall_days_10": "连跌10天", "fall_days_14": "连跌14天",
})
