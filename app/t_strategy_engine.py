from __future__ import annotations

from statistics import mean, pstdev


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_t_strategy(rows: list[dict], stock_context: dict | None = None) -> dict:
    """Score an intraday T opportunity only after an enterprise-quality gate."""
    context = stock_context or {}
    prices = [_num(row.get("price") or row.get("close")) for row in rows if row]
    prices = [price for price in prices if price > 0]
    volumes = [_num(row.get("volume")) for row in rows if row]
    latest = prices[-1] if prices else _num(context.get("price"))
    high = max(prices) if prices else latest
    low = min(prices) if prices else latest
    spread_pct = ((high - low) / low * 100) if low else 0
    returns = [(prices[i] / prices[i - 1] - 1) * 100 for i in range(1, len(prices)) if prices[i - 1]]
    volatility_pct = pstdev(returns) if len(returns) > 1 else 0
    avg_volume = mean(volumes) if volumes and any(volumes) else 0
    volume_ratio = (volumes[-1] / avg_volume) if avg_volume else 1
    midpoint = (high + low) / 2 if prices else latest

    pe = _num(context.get("pe_ttm"), 0)
    amount = _num(context.get("amount"), 0)
    change_pct = _num(context.get("change_pct"), 0)
    enterprise_reasons = []
    if pe <= 0 or pe > 100:
        enterprise_reasons.append("估值或财务数据需要复核")
    if amount < 50_000_000:
        enterprise_reasons.append("成交额偏低，T操作滑点风险较高")
    if change_pct <= -7:
        enterprise_reasons.append("当日跌幅过大，先处理基本面和风险，不追求做T")
    gate_passed = len(enterprise_reasons) == 0
    if not enterprise_reasons:
        enterprise_reasons.append("企业质量与流动性达到当前T策略的基础门槛")

    opportunity_score = min(100, max(0, 35 + spread_pct * 8 + min(volume_ratio, 3) * 8 + volatility_pct * 4))
    if not gate_passed:
        suitability = "不适合做T"
    elif opportunity_score >= 65:
        suitability = "适合做T"
    elif opportunity_score >= 45:
        suitability = "观察"
    else:
        suitability = "不适合做T"

    band = max((high - low) * 0.18, latest * 0.006) if latest else 0
    support = max(low, midpoint - band)
    resistance = min(high, midpoint + band)
    plan = [
        {"time": "09:15-09:25", "label": "集合竞价观察", "action": "不追价，确认高开/低开与量能"},
        {"time": "10:30-11:30", "label": "上午确认窗口", "action": f"价格靠近 {support:.2f} 支撑且量能稳定，再考虑小仓位"},
        {"time": "14:30-14:57", "label": "尾盘T窗口", "action": f"接近 {support:.2f} 可分批低吸，接近 {resistance:.2f} 分批兑现"},
    ]
    return {
        "suitability": suitability,
        "opportunity_score": round(opportunity_score, 2),
        "enterprise_gate": {"passed": gate_passed, "reasons": enterprise_reasons},
        "levels": {"high": round(high, 3), "low": round(low, 3), "support": round(support, 3), "resistance": round(resistance, 3), "current": round(latest, 3)},
        "metrics": {"spread_pct": round(spread_pct, 3), "volatility_pct": round(volatility_pct, 3), "volume_ratio": round(volume_ratio, 3)},
        "intraday_plan": plan,
        "rationale": ["先理解企业，再利用日内波动做仓位优化", "单次T仓位不超过持仓的30%，只做模拟和人工确认"],
        "disclaimer": "做T策略仅用于研究与模拟，不构成投资建议；企业基本面恶化时优先停止做T。",
    }
