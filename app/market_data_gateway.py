from __future__ import annotations

import time
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable


def collect_paginated_batches(fetch_page: Callable[[int, int], dict], page_size: int = 500, max_workers: int = 6) -> list[dict]:
    first = fetch_page(1, page_size)
    total = int(first.get("total") or len(first.get("items") or []))
    page_count = max(1, math.ceil(total / page_size))
    pages: dict[int, list[dict]] = {1: first.get("items") or []}
    if page_count > 1:
        with ThreadPoolExecutor(max_workers=min(max_workers, page_count - 1)) as executor:
            futures = {executor.submit(fetch_page, page, page_size): page for page in range(2, page_count + 1)}
            for future in as_completed(futures):
                page = futures[future]
                try:
                    pages[page] = future.result().get("items") or []
                except Exception:
                    pages[page] = []
    return [item for page in range(1, page_count + 1) for item in pages.get(page, [])]


class MarketDataGateway:
    """Batch market data gateway with observable fallback behavior."""

    def __init__(self, adapters: list[tuple[str, Callable[[], list[dict]]]], stale_after_seconds: int = 5) -> None:
        self.adapters = adapters
        self.stale_after_seconds = stale_after_seconds
        self.health: dict[str, dict] = {
            name: {"name": name, "ok": None, "last_success_at": "", "last_error": "", "latency_ms": None, "calls": 0, "failures": 0}
            for name, _ in adapters
        }

    def full_market_snapshot(self) -> dict:
        started = time.perf_counter()
        errors = []
        for index, (name, adapter) in enumerate(self.adapters):
            source_started = time.perf_counter()
            status = self.health[name]
            status["calls"] += 1
            try:
                items = adapter() or []
                if not items:
                    raise RuntimeError("empty_result")
                now = datetime.now()
                latency = round((time.perf_counter() - source_started) * 1000, 2)
                status.update({"ok": True, "last_success_at": now.isoformat(timespec="seconds"), "last_error": "", "latency_ms": latency})
                return {
                    "items": items,
                    "source": name,
                    "fetched_at": now.isoformat(timespec="seconds"),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "is_stale": False,
                    "fallback_used": index > 0,
                    "errors": errors,
                }
            except Exception as exc:
                status.update({"ok": False, "last_error": str(exc), "latency_ms": round((time.perf_counter() - source_started) * 1000, 2), "failures": status["failures"] + 1})
                errors.append({"source": name, "error": str(exc)})
        return {
            "items": [],
            "source": "unavailable",
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "is_stale": True,
            "fallback_used": bool(self.adapters),
            "errors": errors,
        }

    def health_status(self) -> list[dict]:
        rows = []
        for status in self.health.values():
            calls = max(1, status["calls"])
            rows.append({**status, "error_rate_pct": round(status["failures"] / calls * 100, 2)})
        return rows
