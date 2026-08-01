from __future__ import annotations

from statistics import mean, pstdev


INDICATOR_GROUPS = {
    "trend": ("ma", "boll", "sar", "supertrend", "ichimoku"),
    "momentum": ("macd",),
    "oscillation": ("rsi", "kdj", "cci", "bias"),
    "strength": ("dmi", "volume", "obv"),
}


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, float(value)))


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2 / (period + 1)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1 - alpha) * current
    return current


def _score(bullish: bool | None) -> float:
    return 75.0 if bullish is True else 25.0 if bullish is False else 50.0


def calculate_resonance(rows: list[dict], enabled: dict | None = None, quant_risk_score: float = 0, fund_direction: str = "neutral") -> dict:
    enabled = {key: bool(value) for key, value in (enabled or {}).items()}
    active = {key: enabled.get(key, True) for group in INDICATOR_GROUPS.values() for key in group}
    closes = [float(row.get("close") or row.get("price") or 0) for row in rows if row]
    volumes = [float(row.get("volume") or 0) for row in rows if row]
    if not closes:
        closes = [0.0]
    latest = closes[-1]
    ma5 = mean(closes[-5:])
    ma20 = mean(closes[-20:])
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_hist = ema12 - ema26
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]
    volatility = pstdev(returns) * 100 if len(returns) > 1 else 0
    avg_volume = mean(volumes[-20:]) if volumes and any(volumes[-20:]) else 0
    volume_ratio = volumes[-1] / avg_volume if avg_volume else 1
    signals = []

    def add(key: str, group: str, bullish: bool | None, reason: str):
        if not active[key]:
            return
        signals.append({"key": key, "group": group, "score": _score(bullish), "direction": "bullish" if bullish is True else "bearish" if bullish is False else "neutral", "reason": reason})

    ma_bull = latest >= ma5 >= ma20
    add("ma", "trend", ma_bull if latest != ma20 else None, "均线多头排列" if ma_bull else "均线未形成多头排列")
    add("boll", "trend", latest >= ma20, "价格位于布林中轨上方" if latest >= ma20 else "价格位于布林中轨下方")
    add("sar", "trend", latest >= ma20, "以均线作为 SAR 趋势代理")
    add("supertrend", "trend", latest >= ma20, "以趋势均线作为 SuperTrend 代理")
    add("ichimoku", "trend", latest >= ma20, "以价格与中期均线作为均衡表代理")
    add("macd", "momentum", macd_hist >= 0, "MACD 快慢线差值为正" if macd_hist >= 0 else "MACD 快慢线差值为负")

    gains = [max(0, closes[i] - closes[i - 1]) for i in range(max(1, len(closes) - 14), len(closes))]
    losses = [max(0, closes[i - 1] - closes[i]) for i in range(max(1, len(closes) - 14), len(closes))]
    avg_gain = mean(gains) if gains else 0
    avg_loss = mean(losses) if losses else 0
    rs = (avg_gain / avg_loss) if avg_loss else 2
    rsi = 100 - 100 / (1 + rs)
    add("rsi", "oscillation", 55 <= rsi <= 72, f"RSI {rsi:.1f}")
    add("kdj", "oscillation", 50 <= rsi <= 75, "KDJ 使用 RSI 区间代理")
    deviation = (latest / ma20 - 1) * 100 if ma20 else 0
    add("cci", "oscillation", deviation >= 0, f"CCI 价格偏离 {deviation:.2f}%")
    add("bias", "oscillation", deviation >= -3, f"BIAS {deviation:.2f}%")

    add("dmi", "strength", closes[-1] >= closes[max(0, len(closes) - 5)], "DMI 方向代理")
    add("volume", "strength", volume_ratio >= 1, f"量比 {volume_ratio:.2f}")
    obv = sum((volumes[i] if i < len(volumes) else 0) * (1 if closes[i] >= closes[i - 1] else -1) for i in range(1, min(len(closes), len(volumes))))
    add("obv", "strength", obv >= 0, "OBV 累计方向")

    categories = {}
    weights = {"trend": 0.35, "momentum": 0.25, "oscillation": 0.15, "strength": 0.25}
    for group in INDICATOR_GROUPS:
        group_signals = [item for item in signals if item["group"] == group]
        categories[group] = {"score": round(mean(item["score"] for item in group_signals), 2) if group_signals else 50, "enabled": len(group_signals), "total": len(INDICATOR_GROUPS[group])}
    overall = sum(categories[group]["score"] * weights[group] for group in weights)
    risk_cap = 0.75 if float(quant_risk_score or 0) >= 75 else 1.0
    if str(fund_direction).lower() in {"outflow", "bearish", "流出"}:
        risk_cap = min(risk_cap, 0.8)
    overall *= risk_cap
    stance = "bullish" if overall >= 60 else "bearish" if overall <= 40 else "mixed"
    return {
        "stance": stance,
        "overall_score": round(overall, 2),
        "categories": categories,
        "signals": signals,
        "risk_gate": {"allowed": risk_cap >= 1.0, "cap": risk_cap, "reason": "量化风险或资金流向限制了共振评分" if risk_cap < 1 else "未触发额外门控"},
        "config": {"enabled": active, "weights": weights, "volatility_pct": round(volatility, 3), "volume_ratio": round(volume_ratio, 2)},
        "method": "category_weighted_resonance_v1",
    }
