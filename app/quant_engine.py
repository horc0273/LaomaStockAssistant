from __future__ import annotations

from .models import Candidate, MarketOverview, ModelSignal, Stock, WatchlistItem


def _cost_is_valid(stock: Stock) -> bool:
    """A non-positive average cost is not a usable broker position cost."""
    try:
        return float(stock.cost or 0) > 0
    except (TypeError, ValueError):
        return False


def signal_2060(stock: Stock, market: MarketOverview) -> ModelSignal:
    evidence = [
        "大盘环境：观察指数是否站上20/60/120均线",
        "个股条件：超跌横盘、缩地量、回踩20日线",
        "确认条件：阳包阴且量能重新穿5/10/60均量线",
    ]
    score = 68
    status = "观察"
    if stock.name == "新大陆":
        score = 78
        evidence.append("新大陆主题匹配数字乡村/电子发票/RFID，适合纳入2060观察池")
    if stock.change_pct < -5:
        status = "等待止跌"
        score -= 8
    if market.mood in {"修复", "强势"}:
        score += 5
    return ModelSignal(name="2060战法", status=status, score=score, evidence=evidence, invalidation="跌穿20日线或放量下跌")


def divergence_signal(stock: Stock) -> ModelSignal:
    if stock.change_pct < -5:
        return ModelSignal(
            name="底背离",
            status="观察",
            score=70,
            evidence=["价格下探后等待MACD/RSI/WR不再创新低", "需要放量止跌确认"],
            invalidation="继续放量破位",
        )
    if stock.change_pct > 4:
        return ModelSignal(
            name="顶背离",
            status="预警",
            score=45,
            evidence=["涨幅较大，需检查动能是否同步创新高", "高位缩量上涨降低追涨评分"],
            invalidation="放量突破并站稳前高",
        )
    return ModelSignal(name="背离模型", status="未触发", score=55, evidence=["未发现显著顶/底背离"], invalidation="无")


def trend_signal(stock: Stock) -> ModelSignal:
    if stock.change_pct > 1.5:
        return ModelSignal(name="趋势模型", status="偏强", score=72, evidence=["涨幅强于市场平均", "适合观察均线多头排列"], invalidation="跌破MA20")
    if stock.change_pct < -3:
        return ModelSignal(name="趋势模型", status="偏弱", score=38, evidence=["短线弱于市场", "需要先修复关键均线"], invalidation="继续下破支撑")
    return ModelSignal(name="趋势模型", status="震荡", score=58, evidence=["价格波动处于中性区间"], invalidation="放量破位")


def score_candidate(stock: Stock, market: MarketOverview, sector_boost: int = 0, fund_boost: int = 0) -> Candidate:
    signals = [signal_2060(stock, market), divergence_signal(stock), trend_signal(stock)]
    model_score = round(sum(signal.score for signal in signals) / len(signals))
    sector_strength = min(100, (76 if stock.tag in market.themes or stock.name == "新大陆" else 62) + sector_boost)
    core_theme = any(key in f"{stock.tag} {stock.ai}" for key in ("半导体", "存储", "芯片", "PCB", "算力", "液冷", "电力", "黄金", "铜"))
    theme_matched = stock.tag in market.themes or any(stock.tag in theme or theme in stock.tag for theme in market.themes)
    sector_strength = min(100, (78 if theme_matched else 72 if core_theme else 62) + sector_boost)
    fund_strength = min(100, max(0, 65 + min(12, max(-12, int(stock.change_pct * 2))) + fund_boost))
    risk_penalty = -12 if stock.change_pct > 5 or stock.change_pct < -6 else -4
    market_score = 72 if market.mood == "修复" else 60
    total = round(market_score * 0.15 + model_score * 0.35 + sector_strength * 0.2 + fund_strength * 0.2 + 80 * 0.1 + risk_penalty)

    if total >= 75:
        recommendation = "强观察"
    elif total >= 65:
        recommendation = "观察"
    elif total >= 55:
        recommendation = "等确认"
    else:
        recommendation = "风险升高"

    action, confidence = derive_action(stock, total, recommendation)

    reason = f"{stock.name} 当前{recommendation}：市场处于{market.mood}，主题为{stock.tag}，模型均分{model_score}，资金强度{fund_strength}。"
    return Candidate(
        stock=stock,
        market_state=market.mood,
        signals=signals,
        sector_strength=sector_strength,
        fund_strength=fund_strength,
        risk_penalty=risk_penalty,
        total_score=total,
        action=action,
        confidence=confidence,
        recommendation=recommendation,
        reason=reason,
    )


def derive_action(stock: Stock, total_score: int, recommendation: str) -> tuple[str, int]:
    cost_valid = _cost_is_valid(stock)
    pnl_pct = stock.pnl_pct if cost_valid and stock.pnl_pct is not None else (0 if not cost_valid else (stock.price - stock.cost) / stock.cost * 100)
    if total_score >= 78 and stock.change_pct < 6 and pnl_pct > -15:
        return "BUY", min(88, total_score)
    if pnl_pct < -25 and total_score < 65:
        return "REDUCE", 72
    if stock.change_pct > 6 or (stock.cost < 0 and (stock.pnl_amount or 0) > 0):
        return "HOLD", 70
    if pnl_pct < -18 and total_score >= 65:
        return "HOLD", 62
    if total_score < 55:
        return "SELL", 66
    if recommendation in {"观察", "强观察"}:
        return "WATCH", max(55, min(75, total_score))
    return "WATCH", 55


def build_watchlist_item(stock: Stock, market: MarketOverview) -> WatchlistItem:
    quantity = stock.quantity or 0
    cost_valid = _cost_is_valid(stock)
    # 成本异常时不把错误的券商快照计入总盈亏，也不让它参与买卖信号。
    # 这比展示数千个百分点的“收益率”更安全；页面会同时标出待确认。
    # 盈亏按实时价重算：旧逻辑优先用券商快照值，price 更新后盈亏不跟着变
    pnl_pct = (stock.price - stock.cost) / stock.cost * 100 if cost_valid else 0
    pnl_amount = (stock.price - stock.cost) * quantity if cost_valid else 0
    previous_close = stock.price if stock.change_pct <= -99 else stock.price / (1 + stock.change_pct / 100)
    daily_pnl_amount = (stock.price - previous_close) * quantity
    return WatchlistItem(
        stock=stock,
        quantity=quantity,
        pnl_pct=round(pnl_pct, 2),
        pnl_amount=round(pnl_amount, 2),
        daily_pnl_amount=round(daily_pnl_amount, 2),
        daily_pnl_pct=round(stock.change_pct, 2),
        cost_valid=cost_valid or quantity == 0,
        data_warnings=[] if cost_valid or quantity == 0 else ["持仓成本为非正数，浮盈亏已暂停计入；请重新同步券商持仓"],
        signals=score_candidate(stock, market).signals,
    )
