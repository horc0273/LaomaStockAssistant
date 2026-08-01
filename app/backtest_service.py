from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev


@dataclass
class Position:
    entry_date: str
    entry_price: float
    shares: int
    cost: float


class BacktestService:
    """Small deterministic research engine; signals execute at the next bar open."""

    @staticmethod
    def moving_average(values: list[float], period: int) -> list[float | None]:
        result: list[float | None] = []
        window_sum = 0.0
        for index, value in enumerate(values):
            window_sum += value
            if index >= period:
                window_sum -= values[index - period]
            result.append(window_sum / period if index >= period - 1 else None)
        return result

    @staticmethod
    def max_drawdown(equity: list[float]) -> float:
        peak = equity[0] if equity else 0.0
        worst = 0.0
        for value in equity:
            peak = max(peak, value)
            if peak:
                worst = min(worst, value / peak - 1)
        return worst * 100

    def run(
        self,
        rows: list[dict],
        *,
        strategy: str = "sma_cross",
        short_period: int = 20,
        long_period: int = 60,
        initial_cash: float = 100000,
        fee_bps: float = 10,
        slippage_bps: float = 5,
    ) -> dict:
        cleaned = [row for row in rows if float(row.get("close") or row.get("price") or 0) > 0]
        cleaned.sort(key=lambda row: str(row.get("date", "")))
        if len(cleaned) < max(long_period + 3, 30):
            return {"error": "insufficient_history", "message": f"历史数据不足，至少需要 {max(long_period + 3, 30)} 根日K。"}
        closes = [float(row.get("close") or row.get("price")) for row in cleaned]
        opens = [float(row.get("open") or row.get("close") or row.get("price")) for row in cleaned]
        short_ma = self.moving_average(closes, short_period)
        long_ma = self.moving_average(closes, long_period)
        cash = float(initial_cash)
        position: Position | None = None
        trades: list[dict] = []
        equity: list[float] = []
        pending_signal = ""
        fee_rate = max(0, fee_bps) / 10000
        slippage_rate = max(0, slippage_bps) / 10000

        for i, row in enumerate(cleaned):
            if pending_signal == "BUY" and position is None:
                fill = opens[i] * (1 + slippage_rate)
                shares = int(cash / (fill * (1 + fee_rate)) / 100) * 100
                if shares > 0:
                    cost = shares * fill * (1 + fee_rate)
                    cash -= cost
                    position = Position(str(row.get("date", "")), fill, shares, cost)
            elif pending_signal == "SELL" and position is not None:
                fill = opens[i] * (1 - slippage_rate)
                proceeds = position.shares * fill * (1 - fee_rate)
                pnl = proceeds - position.cost
                trades.append({"entry_date": position.entry_date, "exit_date": str(row.get("date", "")), "entry_price": round(position.entry_price, 3), "exit_price": round(fill, 3), "shares": position.shares, "pnl": round(pnl, 2), "return_pct": round(pnl / position.cost * 100, 2)})
                cash += proceeds
                position = None
            pending_signal = ""

            if i > 0 and short_ma[i] is not None and long_ma[i] is not None and short_ma[i - 1] is not None and long_ma[i - 1] is not None:
                if strategy == "sma_cross":
                    if position is None and short_ma[i - 1] <= long_ma[i - 1] and short_ma[i] > long_ma[i]:
                        pending_signal = "BUY"
                    elif position is not None and short_ma[i - 1] >= long_ma[i - 1] and short_ma[i] < long_ma[i]:
                        pending_signal = "SELL"
                else:  # 2060 trend recovery: close regains MA20 while MA20 is above MA60
                    if position is None and closes[i - 1] <= short_ma[i - 1] and closes[i] > short_ma[i] and short_ma[i] > long_ma[i]:
                        pending_signal = "BUY"
                    elif position is not None and (closes[i] < short_ma[i] or short_ma[i] < long_ma[i]):
                        pending_signal = "SELL"
            equity.append(cash + (position.shares * closes[i] if position else 0))

        if position is not None:
            fill = closes[-1] * (1 - slippage_rate)
            proceeds = position.shares * fill * (1 - fee_rate)
            pnl = proceeds - position.cost
            trades.append({"entry_date": position.entry_date, "exit_date": str(cleaned[-1].get("date", "")), "entry_price": round(position.entry_price, 3), "exit_price": round(fill, 3), "shares": position.shares, "pnl": round(pnl, 2), "return_pct": round(pnl / position.cost * 100, 2), "forced_close": True})
            cash += proceeds
            equity[-1] = cash

        daily_returns = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity)) if equity[i - 1] > 0]
        total_return = (equity[-1] / initial_cash - 1) * 100
        benchmark_return = (closes[-1] / closes[0] - 1) * 100
        years = max(len(cleaned) / 242, 1 / 242)
        annualized = ((equity[-1] / initial_cash) ** (1 / years) - 1) * 100 if equity[-1] > 0 else -100
        volatility = pstdev(daily_returns) if len(daily_returns) > 1 else 0
        sharpe = mean(daily_returns) / volatility * math.sqrt(242) if volatility else 0
        wins = sum(1 for trade in trades if trade["pnl"] > 0)
        return {
            "strategy": strategy,
            "parameters": {"short_period": short_period, "long_period": long_period, "initial_cash": initial_cash, "fee_bps": fee_bps, "slippage_bps": slippage_bps},
            "period": {"start": cleaned[0].get("date"), "end": cleaned[-1].get("date"), "bars": len(cleaned)},
            "metrics": {"total_return_pct": round(total_return, 2), "annualized_return_pct": round(annualized, 2), "benchmark_return_pct": round(benchmark_return, 2), "excess_return_pct": round(total_return - benchmark_return, 2), "max_drawdown_pct": round(self.max_drawdown(equity), 2), "sharpe": round(sharpe, 2), "trade_count": len(trades), "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else 0, "final_equity": round(equity[-1], 2)},
            "equity_curve": [{"date": cleaned[i].get("date"), "equity": round(value, 2)} for i, value in enumerate(equity)],
            "trades": trades,
            "audit": {"execution": "信号在收盘后确认，下一交易日开盘成交", "cost_model": "双边费用与滑点均按可配置 bps 计算", "known_limits": ["未模拟涨跌停无法成交", "未处理停牌与退市股票的幸存者偏差", "结果只用于策略验证，不代表未来收益"]},
        }

    def scan(self, rows: list[dict], *, strategy: str = "sma_cross", initial_cash: float = 100000, fee_bps: float = 10, slippage_bps: float = 5) -> dict:
        combinations = [(5, 20), (10, 30), (10, 60), (20, 60), (20, 120), (30, 120)]
        results = []
        for short_period, long_period in combinations:
            outcome = self.run(rows, strategy=strategy, short_period=short_period, long_period=long_period, initial_cash=initial_cash, fee_bps=fee_bps, slippage_bps=slippage_bps)
            if not outcome.get("error"):
                results.append({"short_period": short_period, "long_period": long_period, **outcome["metrics"]})
        results.sort(key=lambda item: (item["max_drawdown_pct"] >= -30, item["sharpe"], item["total_return_pct"]), reverse=True)
        return {"strategy": strategy, "results": results, "warning": "参数排名用于发现过拟合，不应直接作为实盘参数。"}
