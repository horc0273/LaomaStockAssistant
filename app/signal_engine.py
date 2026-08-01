from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class Signal:
    """交易信号数据模型"""
    id: str
    type: str  # buy / sell / ttrade / stop_loss / take_profit / alert
    code: str
    name: str
    priority: str  # high / medium / low
    trigger_time: str
    trigger_reason: str
    suggested_price: float = 0.0
    suggested_position: float = 0.0  # 仓位比例 0-1
    stop_loss: float = 0.0
    target: float = 0.0
    win_rate: float = 0.0  # 0-1
    confidence: int = 0  # 0-100
    status: str = "pending"  # pending / executed / ignored / expired / snoozed
    dismissed_reason: str = ""
    executed_price: float = 0.0
    executed_time: str = ""
    result: str = ""  # hit / miss / pending
    result_profit: float = 0.0
    lesson: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "code": self.code,
            "name": self.name,
            "priority": self.priority,
            "trigger_time": self.trigger_time,
            "trigger_reason": self.trigger_reason,
            "suggested_price": self.suggested_price,
            "suggested_position": self.suggested_position,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "win_rate": round(self.win_rate, 2),
            "confidence": self.confidence,
            "status": self.status,
            "dismissed_reason": self.dismissed_reason,
            "executed_price": self.executed_price,
            "executed_time": self.executed_time,
            "result": self.result,
            "result_profit": round(self.result_profit, 2),
            "lesson": self.lesson,
            "extra": self.extra,
        }


class SignalEngine:
    """
    交易信号生成引擎。
    核心逻辑：从行情数据中识别交易机会，生成带置信度的可执行信号。
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.signals: list[Signal] = []
        self.signal_counter = 0
        self.data_dir = data_dir or (Path(__file__).resolve().parents[1] / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.signal_log_path = self.data_dir / "signals.json"
        self._load_signals()

    def _load_signals(self) -> None:
        """从本地加载历史信号。"""
        if self.signal_log_path.exists():
            try:
                raw = json.loads(self.signal_log_path.read_text(encoding="utf-8"))
                self.signals = [Signal(**item) for item in raw.get("signals", [])]
                self.signal_counter = raw.get("counter", 0)
            except Exception:
                self.signals = []
                self.signal_counter = 0

    def _save_signals(self) -> None:
        """保存信号到本地。"""
        try:
            payload = {
                "counter": self.signal_counter,
                "signals": [s.to_dict() for s in self.signals],
            }
            self.signal_log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _next_id(self) -> str:
        self.signal_counter += 1
        return f"sig_{self.signal_counter:06d}"

    # ---------- 信号生成逻辑 ----------

    def generate_signals(self, market_data: dict, holdings: list[dict]) -> list[Signal]:
        """
        主入口：基于市场数据和持仓生成所有信号。
        返回新产生的信号列表（已保存到本地）。
        """
        new_signals: list[Signal] = []

        # 1. 持仓股的诊断信号（做T、止损、止盈）
        for holding in holdings:
            signals = self._diagnose_holding(holding, market_data)
            new_signals.extend(signals)

        # 2. 全A扫描的选股信号
        watchlist_codes = {h["code"] for h in holdings}
        scan_signals = self._scan_market(market_data, exclude_codes=watchlist_codes)
        new_signals.extend(scan_signals)

        # 3. 过滤已存在的相同信号（同股票同类型，24小时内）
        filtered = []
        for sig in new_signals:
            if not self._is_duplicate(sig):
                filtered.append(sig)
                self.signals.append(sig)

        if filtered:
            self._save_signals()
        return filtered

    def _is_duplicate(self, sig: Signal, hours: int = 24) -> bool:
        """检查是否已有相同股票相同类型的近期信号。"""
        now = datetime.now()
        cutoff = now - timedelta(hours=hours)
        for existing in self.signals:
            if existing.code == sig.code and existing.type == sig.type:
                try:
                    t = datetime.fromisoformat(existing.trigger_time)
                    if t > cutoff:
                        return True
                except Exception:
                    pass
        return False

    # ---------- 持仓诊断 ----------

    def _diagnose_holding(self, holding: dict, market_data: dict) -> list[Signal]:
        """对单只持仓进行诊断，生成做T/止损/止盈/预警信号。"""
        signals: list[Signal] = []
        code = holding.get("code", "")
        name = holding.get("name", "")
        price = holding.get("price", 0)
        cost = holding.get("cost", 0)
        change_pct = holding.get("change_pct", 0)
        high = holding.get("high", price)
        low = holding.get("low", price)
        open_price = holding.get("open", price)
        prev_close = holding.get("prev_close", price)
        volume = holding.get("volume", 0)
        avg_volume = holding.get("avg_volume", volume)

        if price <= 0 or not code:
            return signals

        now_str = datetime.now().isoformat(timespec="seconds")

        # --- 止损信号 ---
        if cost > 0:
            loss_pct = (price - cost) / cost
            if loss_pct <= -0.08:  # 亏损8%触发止损预警
                sig = Signal(
                    id=self._next_id(),
                    type="stop_loss",
                    code=code,
                    name=name,
                    priority="high",
                    trigger_time=now_str,
                    trigger_reason=f"持仓亏损已达 {fmt_pct(loss_pct)}，跌破8%止损线",
                    suggested_price=price,
                    stop_loss=round(cost * 0.92, 2),
                    confidence=min(70 + int(abs(loss_pct) * 100), 95),
                    extra={"loss_pct": round(loss_pct * 100, 2), "cost": cost},
                )
                signals.append(sig)

        # --- 止盈信号 ---
        if cost > 0:
            profit_pct = (price - cost) / cost
            if profit_pct >= 0.15:  # 盈利15%触发止盈
                sig = Signal(
                    id=self._next_id(),
                    type="take_profit",
                    code=code,
                    name=name,
                    priority="medium",
                    trigger_time=now_str,
                    trigger_reason=f"持仓盈利已达 {fmt_pct(profit_pct)}，建议分批止盈",
                    suggested_price=price,
                    target=round(cost * 1.20, 2),
                    confidence=min(60 + int(profit_pct * 50), 90),
                    extra={"profit_pct": round(profit_pct * 100, 2), "cost": cost},
                )
                signals.append(sig)

        # --- 做T信号：日内振幅大 ---
        if prev_close > 0:
            amplitude = (high - low) / prev_close
            if amplitude >= 0.03:  # 振幅3%以上
                mid_price = (high + low) / 2
                if price > mid_price:  # 当前在高位
                    sig = Signal(
                        id=self._next_id(),
                        type="ttrade",
                        code=code,
                        name=name,
                        priority="medium",
                        trigger_time=now_str,
                        trigger_reason=f"日内振幅 {fmt_pct(amplitude)}，当前处于相对高位",
                        suggested_price=price,
                        target=round(low + (high - low) * 0.3, 2),
                        confidence=min(50 + int(amplitude * 1000), 80),
                        extra={"amplitude": round(amplitude * 100, 2), "high": high, "low": low},
                    )
                    signals.append(sig)

        # --- 预警：接近止损线 ---
        if cost > 0:
            stop_line = cost * 0.92
            if price > stop_line and price <= stop_line * 1.03:  # 在止损线上方3%内
                sig = Signal(
                    id=self._next_id(),
                    type="alert",
                    code=code,
                    name=name,
                    priority="medium",
                    trigger_time=now_str,
                    trigger_reason=f"价格接近止损线（¥{round(stop_line, 2)}），需密切监控",
                    suggested_price=price,
                    stop_loss=round(stop_line, 2),
                    confidence=65,
                    extra={"distance_to_stop": round((price - stop_line) / stop_line * 100, 2)},
                )
                signals.append(sig)

        return signals

    # ---------- 市场扫描 ----------

    def _scan_market(self, market_data: dict, exclude_codes: set[str]) -> list[Signal]:
        """扫描全A，生成买入信号。"""
        signals: list[Signal] = []
        stocks = market_data.get("stocks", [])
        now_str = datetime.now().isoformat(timespec="seconds")

        for stock in stocks:
            code = stock.get("code", "")
            if code in exclude_codes:
                continue

            price = stock.get("price", 0)
            change_pct = stock.get("change_pct", 0)
            turnover = stock.get("turnover", 0)
            volume = stock.get("volume", 0)
            amount = stock.get("amount", 0)
            pe = stock.get("pe_ttm", 0)
            pb = stock.get("pb", 0)
            market_cap = stock.get("market_cap", 0)
            name = stock.get("name", "")

            if price <= 0 or not code:
                continue

            # --- 突破信号：放量 + 涨幅适中 ---
            if turnover >= 2 and 0.02 <= change_pct <= 0.07 and amount >= 100000000:
                confidence = 50
                reasons = []

                if turnover >= 5:
                    confidence += 10
                    reasons.append(f"高换手 {turnover:.1f}%")
                else:
                    reasons.append(f"放量 {turnover:.1f}%")

                if 0.03 <= change_pct <= 0.05:
                    confidence += 10
                    reasons.append("健康涨幅")
                else:
                    reasons.append(f"涨幅 {fmt_pct(change_pct)}")

                if amount >= 500000000:
                    confidence += 5
                    reasons.append("大额成交")

                if market_cap > 5000000000:  # 50亿以上
                    confidence += 5

                sig = Signal(
                    id=self._next_id(),
                    type="buy",
                    code=code,
                    name=name,
                    priority="high" if confidence >= 75 else "medium",
                    trigger_time=now_str,
                    trigger_reason="、".join(reasons) + "，触发买入关注",
                    suggested_price=round(price * 1.01, 2),
                    suggested_position=0.1,
                    stop_loss=round(price * 0.95, 2),
                    target=round(price * 1.08, 2),
                    win_rate=0.55 + confidence / 1000,
                    confidence=min(confidence, 95),
                    extra={"turnover": turnover, "amount": amount, "pe": pe, "pb": pb},
                )
                signals.append(sig)

        # 按置信度排序，取前20
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals[:20]

    # ---------- 信号操作 ----------

    def get_active_signals(self) -> list[Signal]:
        """获取所有待处理的信号。"""
        return [s for s in self.signals if s.status == "pending"]

    def get_signals_by_type(self, signal_type: str | None = None) -> list[Signal]:
        """按类型过滤信号。"""
        if signal_type:
            return [s for s in self.signals if s.type == signal_type]
        return self.signals

    def execute_signal(self, signal_id: str, executed_price: float) -> Signal | None:
        """用户确认执行信号。"""
        for sig in self.signals:
            if sig.id == signal_id:
                sig.status = "executed"
                sig.executed_price = executed_price
                sig.executed_time = datetime.now().isoformat(timespec="seconds")
                self._save_signals()
                return sig
        return None

    def dismiss_signal(self, signal_id: str, reason: str = "") -> Signal | None:
        """用户忽略信号。"""
        for sig in self.signals:
            if sig.id == signal_id:
                sig.status = "ignored"
                sig.dismissed_reason = reason
                self._save_signals()
                return sig
        return None

    def snooze_signal(self, signal_id: str) -> Signal | None:
        """延后信号（1小时后重新评估）。"""
        for sig in self.signals:
            if sig.id == signal_id:
                sig.status = "snoozed"
                self._save_signals()
                return sig
        return None

    def review_signal(self, signal_id: str, result: str, profit: float, lesson: str = "") -> Signal | None:
        """复盘：记录信号结果。"""
        for sig in self.signals:
            if sig.id == signal_id:
                sig.result = result  # hit / miss
                sig.result_profit = profit
                sig.lesson = lesson
                self._save_signals()
                return sig
        return None

    def get_stats(self, days: int = 7) -> dict:
        """获取信号统计。"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for sig in self.signals:
            try:
                t = datetime.fromisoformat(sig.trigger_time)
                if t >= cutoff:
                    recent.append(sig)
            except Exception:
                pass

        total = len(recent)
        executed = [s for s in recent if s.status == "executed"]
        hits = [s for s in executed if s.result == "hit"]
        misses = [s for s in executed if s.result == "miss"]

        hit_rate = len(hits) / len(executed) if executed else 0
        total_profit = sum(s.result_profit for s in executed)

        return {
            "period_days": days,
            "total_signals": total,
            "executed": len(executed),
            "hit_rate": round(hit_rate, 2),
            "profit": round(total_profit, 2),
            "pending": len([s for s in recent if s.status == "pending"]),
            "ignored": len([s for s in recent if s.status == "ignored"]),
        }

    def clear_expired(self, hours: int = 48) -> int:
        """清理过期的 pending 信号。"""
        cutoff = datetime.now() - timedelta(hours=hours)
        cleared = 0
        for sig in self.signals:
            if sig.status == "pending":
                try:
                    t = datetime.fromisoformat(sig.trigger_time)
                    if t < cutoff:
                        sig.status = "expired"
                        cleared += 1
                except Exception:
                    pass
        if cleared:
            self._save_signals()
        return cleared


def fmt_pct(value: float) -> str:
    return f"{value >= 0 and '+' or ''}{value * 100:.2f}%"
