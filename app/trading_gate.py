from __future__ import annotations


def calculate_unified_gate(*, quality: dict | None = None, emotion: dict | None = None, quant_window: dict | None = None) -> dict:
    """Return one conservative decision gate shared by precheck, AI and paper EA."""
    quality = quality or {}
    emotion = emotion or {}
    quant_window = quant_window or {}
    reasons: list[str] = []
    warnings: list[str] = []

    stale = bool(quality.get("is_stale"))
    fallback = bool(quality.get("fallback_used"))
    ages = [quality.get(key) for key in ("quote_age_sec", "index_age_sec", "market_age_sec")]
    numeric_ages = [float(value) for value in ages if isinstance(value, (int, float))]
    if numeric_ages and max(numeric_ages) > 180:
        stale = True
    if stale:
        reasons.append("行情数据过期，暂停新增买入")
    if fallback:
        warnings.append("行情正在使用备用数据源")

    score = emotion.get("composite_score")
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = None
    if score is not None and (score < 25 or score > 88):
        reasons.append("市场情绪处于极端区间，暂停追涨杀跌")

    try:
        risk = float(quant_window.get("risk") or 0)
    except (TypeError, ValueError):
        risk = 0
    if risk >= 75:
        reasons.append("当前交易时段风险较高，新增买入仅保留观察")

    blocked = bool(reasons)
    return {
        "allowed": not blocked,
        "status": "blocked" if blocked else "ready",
        "action_cap": "observe_only" if blocked else "manual_confirm",
        "reasons": reasons,
        "warnings": warnings,
        "policy": "数据中断、情绪极端或高风险窗口时只允许观察/减仓，禁止新增买入",
    }
