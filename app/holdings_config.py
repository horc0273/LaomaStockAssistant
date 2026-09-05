# -*- coding: utf-8 -*-
"""持仓配置加载。

真实持仓放在 holdings.json（不进 git，但会打进 Docker 镜像）；
仓库里只保留脱敏的 holdings.example.json。

盈亏一律按「实时价 - 成本」计算，不读取配置文件里的快照值，
避免历史快照价污染盈亏展示（紫金矿业 +113.34% vs +111.50% 的根因）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import Stock

_HERE = Path(__file__).resolve().parent
_PRIMARY = _HERE / "holdings.json"
_FALLBACK = _HERE / "holdings.example.json"


def _recalc(stock: Stock) -> Stock:
    """按当前 price 重算盈亏。成本非正数时不做计算（沿用上游的异常保护）。"""
    if stock.cost > 0 and stock.quantity:
        stock.pnl_amount = round((stock.price - stock.cost) * stock.quantity, 2)
        stock.pnl_pct = round((stock.price - stock.cost) / stock.cost * 100, 2)
    return stock


def load_holdings() -> list[Stock]:
    for path in (_PRIMARY, _FALLBACK):
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = raw.get("holdings", []) if isinstance(raw, dict) else raw
        result = []
        for item in items:
            try:
                result.append(_recalc(Stock(**item)))
            except Exception:
                continue
        if result:
            return result
    return []
