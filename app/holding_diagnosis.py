from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HoldingDiagnosis:
    """单只持仓的诊断结果"""
    code: str
    name: str
    price: float = 0.0
    cost: float = 0.0
    change_pct: float = 0.0
    pnl_pct: float = 0.0
    pnl_amount: float = 0.0
    health_score: int = 50  # 0-100
    diagnosis: str = ""
    suggestion: str = ""
    trend: str = "neutral"  # strong / moderate / weak / neutral
    risk_level: str = "medium"  # low / medium / high
    attribution: dict = field(default_factory=dict)
    signals: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "name": self.name,
            "price": self.price,
            "cost": self.cost,
            "change_pct": round(self.change_pct, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "pnl_amount": round(self.pnl_amount, 2),
            "health_score": self.health_score,
            "diagnosis": self.diagnosis,
            "suggestion": self.suggestion,
            "trend": self.trend,
            "risk_level": self.risk_level,
            "attribution": self.attribution,
            "signals": self.signals,
        }


class HoldingDiagnosisEngine:
    """
    持仓诊断引擎。
    对每只持仓进行"体检"：评分 + 诊断 + 建议 + 波动归因。
    """

    def diagnose(self, holding: dict, market_context: dict | None = None) -> HoldingDiagnosis:
        """
        对单只持仓进行全面诊断。
        """
        code = holding.get("code", "")
        name = holding.get("name", "")
        price = holding.get("price", 0.0)
        cost = holding.get("cost", 0.0)
        change_pct = holding.get("change_pct", 0.0)
        pnl_amount = holding.get("pnl_amount", 0.0)
        open_price = holding.get("open", price)
        high = holding.get("high", price)
        low = holding.get("low", price)
        prev_close = holding.get("prev_close", price)
        volume = holding.get("volume", 0.0)
        turnover = holding.get("turnover", 0.0)
        ma20 = holding.get("ma20", price)
        ma60 = holding.get("ma60", price)

        diag = HoldingDiagnosis(
            code=code,
            name=name,
            price=price,
            cost=cost,
            change_pct=change_pct,
        )

        if cost > 0:
            diag.pnl_pct = (price - cost) / cost
            diag.pnl_amount = pnl_amount or (price - cost) * holding.get("quantity", 0)

        # ---------- 1. 健康度评分 ----------
        diag.health_score = self._calc_health_score(
            price, cost, change_pct, high, low, prev_close,
            ma20, ma60, turnover
        )

        # ---------- 2. 趋势判断 ----------
        diag.trend = self._judge_trend(price, ma20, ma60, change_pct, high, low, prev_close)

        # ---------- 3. 风险等级 ----------
        diag.risk_level = self._judge_risk(price, cost, change_pct, diag.health_score)

        # ---------- 4. 诊断文本 ----------
        diag.diagnosis = self._generate_diagnosis(
            price, cost, change_pct, diag.trend, diag.health_score, turnover
        )

        # ---------- 5. 操作建议 ----------
        diag.suggestion = self._generate_suggestion(
            price, cost, change_pct, diag.trend, diag.health_score, diag.risk_level
        )

        # ---------- 6. 波动归因 ----------
        diag.attribution = self._analyze_attribution(
            holding, market_context
        )

        return diag

    def diagnose_all(self, holdings: list[dict], market_context: dict | None = None) -> list[HoldingDiagnosis]:
        """批量诊断所有持仓。"""
        results = []
        for h in holdings:
            results.append(self.diagnose(h, market_context))
        # 按健康度排序
        results.sort(key=lambda x: x.health_score, reverse=True)
        return results

    # ---------- 内部方法 ----------

    def _calc_health_score(
        self, price: float, cost: float, change_pct: float,
        high: float, low: float, prev_close: float,
        ma20: float, ma60: float, turnover: float
    ) -> int:
        """计算持仓健康度评分（0-100）。"""
        score = 50  # 基础分

        # 盈亏状态
        if cost > 0:
            pnl = (price - cost) / cost
            if pnl > 0:
                score += min(int(pnl * 100), 20)  # 盈利加分
            else:
                score += max(int(pnl * 100), -30)  # 亏损扣分

        # 趋势分
        if ma20 > 0 and price > ma20:
            score += 10
        if ma60 > 0 and price > ma60:
            score += 10
        if ma20 > ma60:
            score += 5

        # 活跃度
        if turnover >= 3:
            score += 5
        elif turnover >= 1:
            score += 2
        elif turnover < 0.5:
            score -= 5

        # 日内强弱
        if prev_close > 0:
            position = (price - low) / (high - low + 0.001)
            if position > 0.7:
                score += 5
            elif position < 0.3:
                score -= 5

        return max(0, min(100, score))

    def _judge_trend(
        self, price: float, ma20: float, ma60: float,
        change_pct: float, high: float, low: float, prev_close: float
    ) -> str:
        """判断趋势强度。"""
        score = 0

        if ma20 > 0 and price > ma20:
            score += 1
        if ma60 > 0 and price > ma60:
            score += 1
        if ma20 > ma60:
            score += 1
        if change_pct > 0.03:
            score += 1
        if prev_close > 0 and (high - low) / prev_close > 0.02:
            score += 1

        if score >= 4:
            return "strong"
        elif score >= 2:
            return "moderate"
        elif score >= 1:
            return "neutral"
        else:
            return "weak"

    def _judge_risk(self, price: float, cost: float, change_pct: float, health_score: int) -> str:
        """判断风险等级。"""
        if cost > 0:
            pnl = (price - cost) / cost
            if pnl <= -0.10:
                return "high"
            if health_score < 30:
                return "high"
            if pnl <= -0.05:
                return "medium"

        if health_score < 40:
            return "high"
        if health_score < 60:
            return "medium"
        return "low"

    def _generate_diagnosis(
        self, price: float, cost: float, change_pct: float,
        trend: str, health_score: int, turnover: float
    ) -> str:
        """生成诊断文本。"""
        parts = []

        # 趋势描述
        trend_desc = {
            "strong": "趋势强劲",
            "moderate": "趋势向好",
            "neutral": "趋势震荡",
            "weak": "趋势偏弱",
        }.get(trend, "趋势不明")
        parts.append(trend_desc)

        # 盈亏描述
        if cost > 0:
            pnl = (price - cost) / cost
            if pnl > 0.05:
                parts.append(f"，浮盈 {fmt_pct(pnl)}")
            elif pnl < -0.05:
                parts.append(f"，浮亏 {fmt_pct(abs(pnl))}")
            else:
                parts.append("，成本附近")

        # 活跃度
        if turnover >= 5:
            parts.append("，成交活跃")
        elif turnover < 1:
            parts.append("，成交清淡")

        # 健康度
        if health_score >= 80:
            parts.append("，状态良好")
        elif health_score < 40:
            parts.append("，需关注风险")

        return "".join(parts)

    def _generate_suggestion(
        self, price: float, cost: float, change_pct: float,
        trend: str, health_score: int, risk_level: str
    ) -> str:
        """生成操作建议。"""
        if risk_level == "high":
            if cost > 0 and (price - cost) / cost < -0.10:
                return "考虑止损或减仓，关注止跌信号"
            return "风险较高，建议控制仓位"

        if trend == "strong" and health_score >= 70:
            if cost > 0 and (price - cost) / cost > 0.10:
                return "趋势良好，可考虑止盈部分仓位"
            return "趋势向好，可持有或适当加仓"

        if trend == "weak" and health_score < 50:
            return "趋势偏弱，建议观望或减少持仓"

        if trend == "neutral":
            return "震荡格局，可做T降低成本"

        return "继续持有，关注关键价位"

    def _analyze_attribution(self, holding: dict, market_context: dict | None = None) -> dict:
        """
        波动归因分析：将涨跌幅分解到各个因素。
        返回 {technical, sector, fund_flow, news} 各因素的贡献。
        """
        code = holding.get("code", "")
        change_pct = holding.get("change_pct", 0)
        name = holding.get("name", "")

        # 简化版归因（实际应接入板块数据、资金流数据等）
        attribution = {
            "technical": {
                "contribution": round(change_pct * 0.5, 2),
                "reason": "技术面因素",
                "details": [],
            },
            "sector": {
                "contribution": round(change_pct * 0.3, 2),
                "reason": "板块效应",
                "details": [],
            },
            "fund_flow": {
                "contribution": round(change_pct * 0.15, 2),
                "reason": "资金流向",
                "details": [],
            },
            "news": {
                "contribution": round(change_pct * 0.05, 2),
                "reason": "消息面",
                "details": [],
            },
        }

        # 根据具体条件细化
        turnover = holding.get("turnover", 0)
        if turnover >= 3:
            attribution["technical"]["details"].append(f"高换手 {turnover:.1f}%，资金活跃")
            attribution["fund_flow"]["contribution"] = round(change_pct * 0.25, 2)
        else:
            attribution["technical"]["details"].append("正常换手")

        if change_pct > 0.03:
            attribution["technical"]["details"].append(f"涨幅 {fmt_pct(change_pct)}，强于大盘")
        elif change_pct < -0.03:
            attribution["technical"]["details"].append(f"跌幅 {fmt_pct(abs(change_pct))}，弱于大盘")

        # 如果有板块信息
        if market_context:
            sector_change = market_context.get("sector_change", 0)
            if abs(sector_change) > 0.01:
                attribution["sector"]["details"].append(f"所属板块 {fmt_pct(sector_change)}")
                # 重新分配权重
                total = abs(change_pct)
                if total > 0:
                    attribution["sector"]["contribution"] = round(change_pct * 0.4, 2)
                    attribution["technical"]["contribution"] = round(change_pct * 0.35, 2)
                    attribution["fund_flow"]["contribution"] = round(change_pct * 0.2, 2)
                    attribution["news"]["contribution"] = round(change_pct * 0.05, 2)

        return attribution


def fmt_pct(value: float) -> str:
    return f"{value >= 0 and '+' or ''}{value * 100:.2f}%"
