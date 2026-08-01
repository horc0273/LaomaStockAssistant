from __future__ import annotations

from datetime import datetime


class DataPreheatService:
    """Warm the critical market paths and expose observable health metadata."""

    def __init__(self, provider, gateway) -> None:
        self.provider = provider
        self.gateway = gateway
        self.last_result: dict = {}

    def should_run(self, interval_seconds: int = 300) -> bool:
        if not self.last_result.get("last_run_at"):
            return True
        try:
            last = datetime.fromisoformat(str(self.last_result["last_run_at"]))
            return (datetime.now() - last).total_seconds() >= interval_seconds
        except (TypeError, ValueError):
            return True

    def run_once(self, reason: str = "dashboard", force: bool = False) -> dict:
        if not force and self.last_result and not self.should_run():
            return {**self.last_result, "skipped": True, "reason": reason}
        started = datetime.now()
        errors = []
        try:
            market = self.provider.market_overview()
            snapshot = self.gateway.full_market_snapshot()
            quality = self.provider.data_quality()
            result = {
                "ok": bool(snapshot.get("items") or market),
                "reason": reason,
                "last_run_at": datetime.now().isoformat(timespec="seconds"),
                "elapsed_ms": round((datetime.now() - started).total_seconds() * 1000, 2),
                "gateway": self.gateway.health_status(),
                "quality": quality,
                "snapshot": {"source": snapshot.get("source"), "count": len(snapshot.get("items") or []), "latency_ms": snapshot.get("latency_ms"), "fallback_used": snapshot.get("fallback_used")},
            }
        except Exception as exc:
            errors.append(str(exc))
            result = {"ok": False, "reason": reason, "last_run_at": datetime.now().isoformat(timespec="seconds"), "gateway": self.gateway.health_status(), "quality": self.provider.data_quality(), "errors": errors}
        self.last_result = result
        return result
