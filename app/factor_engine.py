from __future__ import annotations


def _clamp(value: float, lower: float = 0, upper: float = 100) -> float:
    return max(lower, min(upper, float(value)))


def classify_momentum_regime(*, momentum_pct: float, volatility_pct: float, drawdown_pct: float) -> dict:
    momentum = float(momentum_pct or 0)
    volatility = abs(float(volatility_pct or 0))
    drawdown = float(drawdown_pct or 0)
    if drawdown <= -10:
        return {"key": "drawdown_risk", "label": "回撤风险", "risk_score": 88, "position_scale": 0.5, "reason": "回撤与波动同时放大，优先缩小仓位并等待确认。"}
    if momentum >= 8 and volatility >= 6:
        return {"key": "overheated", "label": "动量过热", "risk_score": 82, "position_scale": 0.6, "reason": "强动量伴随高波动，警惕拥挤交易和后期反转。"}
    if momentum >= 3:
        return {"key": "accelerating", "label": "动量加速", "risk_score": 54, "position_scale": 0.8, "reason": "动量仍在增强，但需要资金和趋势共同确认。"}
    if momentum <= -3:
        return {"key": "weakening", "label": "动量走弱", "risk_score": 68, "position_scale": 0.7, "reason": "动量转弱，暂缓追涨并观察支撑是否有效。"}
    return {"key": "neutral", "label": "动量中性", "risk_score": 42, "position_scale": 1.0, "reason": "动量信号不突出，等待更多因子共振。"}


def calculate_factor_snapshot(values: dict) -> dict:
    weights = {
        "momentum": 0.25,
        "value": 0.15,
        "quality": 0.15,
        "risk": 0.15,
        "fund_flow": 0.20,
        "sentiment": 0.10,
    }
    factors = []
    explanations = []
    total = 0.0
    for name, weight in weights.items():
        raw = _clamp(values.get(name, 50))
        score = 100 - raw if name == "risk" else raw
        total += score * weight
        factors.append({"key": name, "score": round(score, 2), "weight": weight})
        if score >= 75:
            explanations.append(f"{name} 因子偏强")
        elif score <= 35:
            explanations.append(f"{name} 因子偏弱")
    return {
        "total_score": round(total, 2),
        "factors": factors,
        "explanations": explanations or ["各因子处于中性区间，等待新的共振信号。"],
        "method": "weighted_multi_factor_v1",
    }
