from __future__ import annotations

from dataclasses import dataclass


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def calculate_dynamic_risk(*, price: float, volatility_pct: float, base_stop_pct: float = 3.0) -> dict:
    """Return explainable paper-trading thresholds scaled to observed volatility.

    ``volatility_pct`` is a percentage (e.g. 4.2 means 4.2%). This is a
    guardrail for simulation and decision support, not an order instruction.
    """
    price = max(float(price or 0), 0.01)
    volatility = _clamp(abs(float(volatility_pct or 0)), 0.5, 15.0)
    stop_loss_pct = _clamp(float(base_stop_pct) + volatility * 0.65, 2.0, 12.0)
    take_profit_pct = _clamp(max(stop_loss_pct * 1.8, 5.0), 5.0, 24.0)
    max_position_pct = _clamp(12.0 - volatility * 0.7, 3.0, 12.0)
    risk_level = "high" if volatility >= 6 else "medium" if volatility >= 3 else "low"
    return {
        "volatility_pct": round(volatility, 2),
        "stop_loss_pct": round(stop_loss_pct, 2),
        "take_profit_pct": round(take_profit_pct, 2),
        "max_position_pct": round(max_position_pct, 2),
        "trigger_price": round(price * (1 + min(0.02, volatility / 1000)), 3),
        "invalidation_price": round(price * (1 - stop_loss_pct / 100), 3),
        "take_profit_price": round(price * (1 + take_profit_pct / 100), 3),
        "risk_level": risk_level,
        "method": "volatility_scaled_guardrail",
    }
