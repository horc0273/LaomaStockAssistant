from __future__ import annotations

from pydantic import BaseModel, Field


class Stock(BaseModel):
    market: str
    name: str
    code: str
    price: float
    change_pct: float
    cost: float = 0
    quantity: int = 0
    pnl_amount: float | None = None
    pnl_pct: float | None = None
    tag: str = "观察"
    ai: str = "等待模型计算"
    keys: str = ""
    source: str = "demo"
    alert_pct: float = 3
    alert_price: float = 0
    sort_order: int = 0
    open_price_target: float = 0
    take_profit: float = 0
    stop_loss: float = 0


class MarketIndex(BaseModel):
    name: str
    code: str
    price: float
    change_pct: float
    market: str
    source: str = "demo"
    latency_sec: int = 0


class MarketOverview(BaseModel):
    source_mode: str = "demo"
    source_note: str
    updated_at: str
    indices: list[MarketIndex]
    up_count: int
    down_count: int
    limit_up: int
    limit_down: int
    turnover_billion: float
    mood: str
    themes: list[str]


class ModelSignal(BaseModel):
    name: str
    status: str
    score: int
    evidence: list[str] = Field(default_factory=list)
    invalidation: str = ""


class Candidate(BaseModel):
    stock: Stock
    market_state: str
    signals: list[ModelSignal]
    sector_strength: int
    fund_strength: int
    risk_penalty: int
    total_score: int
    action: str = "WATCH"
    confidence: int = 50
    recommendation: str
    reason: str


class WatchlistItem(BaseModel):
    stock: Stock
    quantity: int = 0
    pnl_pct: float = 0
    pnl_amount: float = 0
    daily_pnl_amount: float = 0
    daily_pnl_pct: float = 0
    cost_valid: bool = True
    data_warnings: list[str] = Field(default_factory=list)
    signals: list[ModelSignal] = Field(default_factory=list)
