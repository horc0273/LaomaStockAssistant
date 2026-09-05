from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .auth_service import AuthService, membership_plan_catalog
from .abnormal_service import AbnormalMonitorService
from .ai_service import AIService
from .backtest_service import BacktestService
from .data_provider import DemoDataProvider
from .industry_chain_service import IndustryChainService
from .market_data_gateway import MarketDataGateway
from .preheat_service import DataPreheatService
from .quant_engine import build_watchlist_item, score_candidate
from .risk_engine import calculate_dynamic_risk
from .factor_engine import calculate_factor_snapshot, classify_momentum_regime
from .resonance_engine import calculate_resonance
from .t_strategy_engine import calculate_t_strategy
from .recommendation_scoring_service import RecommendationScoringService
from .screener_service import ScreenerService, StrategyValidationError
from .wencai_service import WencaiService
from .eastmoney_ai_service import EastMoneyAIService

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
STATIC_DIR = ROOT / "static"

app = FastAPI(title="老马智能股票盯盘助手", version="1.6.3")
provider = DemoDataProvider()
auth_service = AuthService(provider.data_dir)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
ai_service = AIService(provider.data_dir)
backtest_service = BacktestService()
screener_service = ScreenerService()
abnormal_service = AbnormalMonitorService()
industry_chain_service = IndustryChainService()
recommendation_scoring_service = RecommendationScoringService()
market_data_gateway = MarketDataGateway([
    ("eastmoney-full-a", provider.eastmoney_full_market_universe),
    ("eastmoney-ranked-fallback", provider.ranked_market_universe_fallback),
])
preheat_service = DataPreheatService(provider, market_data_gateway)


def user_ai_config_path(user: dict) -> Path:
    return provider.data_dir / "user_ai_configs" / f"user_{int(user['id'])}.json"


def ai_service_for_user(user: dict) -> tuple[AIService, str]:
    if user.get("role") == "admin":
        return ai_service, "system"
    return AIService.for_personal_config(user_ai_config_path(user)), "personal"


class CodePayload(BaseModel):
    code: str


class LoginPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    phone: str
    password: str
    display_name: str = ""


class MemberPayload(BaseModel):
    username: str
    password: str
    display_name: str = ""
    phone: str = ""
    role: str = "member"
    plan: str = "trial"
    days: int = 30


class MemberUpdatePayload(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    role: str | None = None
    plan: str | None = None
    days: int | None = None
    is_active: bool | None = None
    password: str | None = None


class AIConfigPayload(BaseModel):
    enabled: bool = True
    provider: str = "custom"
    base_url: str
    model: str
    api_key: str = ""
    profile_id: str = ""
    profile_name: str = ""


class AIAnalyzePayload(BaseModel):
    model_id: str
    system_prompt: str = ""
    question: str = ""
    tools_enabled: bool = True
    analysis_mode: str = "decision_report"


class BacktestPayload(BaseModel):
    strategy: str = "sma_cross"
    short_period: int = 20
    long_period: int = 60
    initial_cash: float = 100000
    fee_bps: float = 10
    slippage_bps: float = 5
    parameter_scan: bool = False


class TradeActionPayload(BaseModel):
    code: str
    mode: str = "paper"
    note: str = ""


class EASimulationPayload(BaseModel):
    strategy_id: str = "anti_quant_tail"
    max_orders: int = 5


class TradePrecheckPayload(BaseModel):
    code: str
    side: str = "BUY"
    price: float = 0
    quantity: int = 0
    intent: str = ""


class TradeCooldownPayload(BaseModel):
    code: str
    reason: str = "情绪波动，先冷静再确认"
    minutes: int = 5


class PositionPayload(BaseModel):
    code: str
    cost: float = 0
    quantity: int = 0
    alert_pct: float = 3
    alert_price: float = 0
    sort_order: int = 0
    open_price_target: float = 0
    take_profit: float = 0
    stop_loss: float = 0


class PortfolioCashPayload(BaseModel):
    cash_available: float = 0


class TushareConfigPayload(BaseModel):
    token: str


class ScreenerParsePayload(BaseModel):
    text: str


class ScreenerRunPayload(BaseModel):
    dsl: dict


class ScreenerStrategyPayload(BaseModel):
    name: str
    description: str = ""
    dsl: dict
    enabled: bool = True


class StockRecommendationPayload(BaseModel):
    code: str
    strategy_name: str = "手动推荐"
    reason: str = ""
    risk_note: str = ""


class AbnormalSnapshotPayload(BaseModel):
    selected_types: list[str] = []


class IndustryChainPayload(BaseModel):
    query: str
    mode: str = "quick"


class RecommendationScorePayload(BaseModel):
    code: str
    topic: str = ""
    persist: bool = False


class DailyReviewSavePayload(BaseModel):
    title: str = ""
    summary: str = ""


class WencaiScreenPayload(BaseModel):
    conditions: list[str] = []
    question: str = ""


class EastMoneyAIQueryPayload(BaseModel):
    code: str = ""
    name: str = ""
    question: str = ""
    query_type: str = "hotspot"
    title: str = ""
    summary: str = ""


def request_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.cookies.get("laoma_session", "")


def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if user:
        return user
    resolved = auth_service.user_from_token(request_token(request))
    if not resolved:
        raise RuntimeError("unauthorized")
    return resolved


def source_traffic_light(source: str = "", warnings: list[str] | None = None, stale: bool = False, fallback_used: bool = False) -> dict:
    raw = str(source or "").lower()
    warning_count = len(warnings or [])
    if stale or "missing" in raw or "not_configured" in raw or "unavailable" in raw or "disabled" in raw:
        level = "red"
        label = "不可用/需确认"
    elif fallback_used or warning_count or "fallback" in raw or "pending" in raw or "local" in raw or "manual" in raw:
        level = "yellow"
        label = "降级/备用"
    else:
        level = "green"
        label = "真实可用"
    return {
        "level": level,
        "label": label,
        "source": source or "unknown",
        "warning_count": warning_count,
    }


def detect_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        return None
    return None


def build_access_payload(request: Request) -> dict:
    parsed = urlsplit(str(request.base_url))
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path_suffix = "?v=desktop"
    local_url = f"{parsed.scheme}://127.0.0.1:{port}/{path_suffix}" if port not in {80, 443} else f"{parsed.scheme}://127.0.0.1/{path_suffix}"
    lan_ip = detect_lan_ip()
    if lan_ip:
        lan_url = f"{parsed.scheme}://{lan_ip}:{port}/{path_suffix}" if port not in {80, 443} else f"{parsed.scheme}://{lan_ip}/{path_suffix}"
        hint = "手机和电脑连同一个 Wi‑Fi 后，优先用局域网地址打开。"
    else:
        lan_url = ""
        hint = "暂未识别到局域网地址，请确认电脑已连网，并与手机处于同一 Wi‑Fi。"
    return {
        "local_url": local_url,
        "lan_url": lan_url,
        "lan_ip": lan_ip or "",
        "hint": hint,
    }


def build_mobile_dashboard_payload(user: dict, request: Request | None = None) -> dict:
    market = provider.market_overview()
    data_quality = provider.data_quality()
    emotion = provider.market_emotion_volume()
    user_state = provider.read_user_state(user)
    watch_items = [build_watchlist_item(stock, market) for stock in provider.get_user_watchlist(user)]
    watch_items_sorted = sorted(watch_items, key=lambda item: item.stock.change_pct, reverse=True)
    held_items = [item for item in watch_items if item.quantity > 0]
    portfolio_snapshot = provider.account_snapshot
    manual_cash_available = user_state.get("manual_cash_available")
    if manual_cash_available is not None:
        cash_available = float(manual_cash_available or 0)
        cash_source = "manual_input"
    elif user.get("username") == "laoma":
        cash_available = float(portfolio_snapshot.get("cash_available") or 0)
        cash_source = "broker_cash_snapshot"
    else:
        cash_available = 0.0
        cash_source = "not_configured"
    total_market_value = sum(item.stock.price * item.quantity for item in held_items)
    total_pnl = sum(item.pnl_amount for item in held_items)
    total_daily_pnl = sum(item.daily_pnl_amount for item in held_items)
    invalid_cost_items = [item for item in held_items if not item.cost_valid]
    portfolio_summary_data = {
        "total_assets": round(total_market_value + cash_available, 2),
        "cash_available": round(cash_available, 2),
        "cash_source": cash_source,
        "position_count": len(held_items),
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_daily_pnl": round(total_daily_pnl, 2),
        "invalid_cost_count": len(invalid_cost_items),
        "data_warnings": [
            {"code": item.stock.code, "name": item.stock.name, "warning": "持仓成本待确认，浮盈亏未计入汇总。"}
            for item in invalid_cost_items
        ],
    }
    watchlist_summary = {
        "scope": "current_user_watchlist",
        "total": len(watch_items),
        "up_count": sum(1 for item in watch_items if item.stock.change_pct >= 0),
        "down_count": sum(1 for item in watch_items if item.stock.change_pct < 0),
        "leaders": [
            {"code": item.stock.code, "name": item.stock.name, "change_pct": round(item.stock.change_pct, 2), "price": item.stock.price}
            for item in watch_items_sorted[:3]
        ],
        "laggards": [
            {"code": item.stock.code, "name": item.stock.name, "change_pct": round(item.stock.change_pct, 2), "price": item.stock.price}
            for item in sorted(watch_items, key=lambda item: item.stock.change_pct)[:3]
        ],
    }
    ai_reco_rows = (provider.ai_stock_recommendations(limit=3).get("items") or [])[:3]
    action_queue = provider.user_trading_action_queue(user)
    quant_control = action_queue.get("quant_control") or provider.quant_control_radar()
    quant_fund_radar = action_queue.get("quant_fund_radar") or provider.user_quant_fund_radar(user, limit=8)
    action_rows = (action_queue.get("actions") or [])[:2]
    risk_alerts = []
    quant_summary = quant_fund_radar.get("summary") or {}
    tail_session = quant_fund_radar.get("tail_session") or {}
    if quant_summary.get("high_count", 0) > 0 or quant_summary.get("top_score", 0) >= 75:
        risk_alerts.append({
            "title": "量化资金雷达预警",
            "level": "warning" if tail_session.get("level") == "高" else "info",
            "detail": f"高风险 {quant_summary.get('high_count', 0)} 只，最高嫌疑 {quant_summary.get('top_score', 0)}/100；{tail_session.get('action', '')}",
        })
    if action_queue.get("gate"):
        risk_alerts.append({
            "title": "市场闸门",
            "level": "warning",
            "detail": str(action_queue.get("gate") or ""),
        })
    for item in action_rows:
        risk_alerts.append({
            "title": item.get("name") or item.get("code") or "持仓风险",
            "level": "warning" if item.get("action") in {"REDUCE_RISK", "STOP_REVIEW"} else "info",
            "detail": item.get("reason") or item.get("label") or "",
        })
    if not risk_alerts and data_quality.get("fallback_used"):
        risk_alerts.append({
            "title": "数据源降级",
            "level": "warning",
            "detail": "当前行情使用了降级数据源，请结合更新时间复核。",
        })
    source_card = source_traffic_light(
        data_quality.get("provider") or data_quality.get("source") or data_quality.get("quote_source") or market.source_note,
        warnings=data_quality.get("warnings") or [],
        stale=bool(data_quality.get("is_stale")),
        fallback_used=bool(data_quality.get("fallback_used")),
    )
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "data_state": {
            "status": "degraded" if data_quality.get("fallback_used") else "ok",
            "source": data_quality.get("provider") or data_quality.get("source") or market.source_note,
            "stale": bool(data_quality.get("is_stale")),
            "fallback_used": bool(data_quality.get("fallback_used")),
            "updated_at": market.updated_at,
        },
        "data_source_card": {
            **source_card,
            "title": "数据源状态",
            "detail": " / ".join((data_quality.get("warnings") or [])[:2]) or "核心行情源可用，关键模块会继续标注来源。",
        },
        "mobile_layout": {
            "mode": "six_core_cards",
            "core_cards": ["market", "portfolio", "risk", "actions", "ai", "data"],
        },
        "market_mood": {
            "state": emotion.get("state") or market.mood,
            "composite_score": emotion.get("composite_score"),
            "up_count": market.up_count,
            "down_count": market.down_count,
            "turnover_billion": market.turnover_billion,
            "summary": emotion.get("summary") or f"{market.mood} · 上涨 {market.up_count} / 下跌 {market.down_count}",
        },
        "morning_briefing": provider.morning_briefing(),
        "portfolio_summary": portfolio_summary_data,
        "watchlist_summary": watchlist_summary,
        "ai_recommendations": [
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "score": item.get("score"),
                "action": item.get("action"),
                "signal_category": item.get("signal_category"),
                "signal_label": item.get("signal_label"),
                "reason": item.get("reason"),
                "change_pct": item.get("change_pct"),
                "price": item.get("price"),
            }
            for item in ai_reco_rows
        ],
        "trade_actions": [
            {
                "code": item.get("code"),
                "name": item.get("name"),
                "label": item.get("label"),
                "action": item.get("action"),
                "priority": item.get("priority"),
                "reason": item.get("reason"),
                "next_step": item.get("next_step"),
            }
            for item in action_rows
        ],
        "risk_alerts": risk_alerts[:3],
        "quant_control": quant_control,
        "quant_fund_radar": quant_fund_radar,
        "access": build_access_payload(request) if request else {
            "local_url": "",
            "lan_url": "",
            "lan_ip": "",
            "hint": "当前未附带访问地址信息。",
        },
        "quick_links": [
            {"key": "abnormal", "label": "异动监控"},
            {"key": "screener", "label": "智能选股"},
            {"key": "market", "label": "热点事件"},
            {"key": "research", "label": "研究中心"},
        ],
    }


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    public_paths = ("/", "/static/", "/api/auth/")
    if path == "/" or path.startswith(public_paths[1]) or path.startswith(public_paths[2]):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "same-origin"
        return response
    if path.startswith("/api/"):
        user = auth_service.user_from_token(request_token(request))
        if not user:
            return JSONResponse({"error": "unauthorized", "message": "请先登录"}, status_code=401)
        request.state.user = user
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/auth/login")
def login(payload: LoginPayload, response: Response):
    result = auth_service.login(payload.username, payload.password)
    if not result:
        return JSONResponse({"error": "invalid_login", "message": "账号或密码错误，或会员已到期"}, status_code=401)
    response.set_cookie(
        "laoma_session",
        result["token"],
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        secure=os.getenv("COOKIE_SECURE") == "1",
    )
    return {"ok": True, "user": result["user"], "expires_at": result["expires_at"]}


@app.post("/api/auth/register")
def register(payload: RegisterPayload):
    result = auth_service.register_by_phone(payload.phone, payload.password, payload.display_name)
    if result.get("error"):
        status = 409 if result.get("error") in {"username_exists", "phone_exists"} else 400
        return JSONResponse(result, status_code=status)
    return result


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth_service.logout(request_token(request))
    response.delete_cookie("laoma_session")
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    user = auth_service.user_from_token(request_token(request))
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"ok": True, "user": user}


@app.get("/api/membership/plans")
def membership_plans(request: Request):
    user = current_user(request)
    catalog = membership_plan_catalog()
    return {**catalog, "current": user.get("membership", {})}


def require_admin(request: Request) -> dict | JSONResponse:
    user = current_user(request)
    if user.get("role") != "admin":
        return JSONResponse({"error": "forbidden", "message": "仅管理员可操作会员"}, status_code=403)
    return user


@app.get("/api/admin/users")
def admin_users(request: Request):
    admin = require_admin(request)
    if isinstance(admin, JSONResponse):
        return admin
    return {"items": auth_service.list_users()}


@app.post("/api/admin/users")
def admin_create_user(payload: MemberPayload, request: Request):
    admin = require_admin(request)
    if isinstance(admin, JSONResponse):
        return admin
    return auth_service.create_user(
        payload.username,
        payload.password,
        display_name=payload.display_name,
        phone=payload.phone,
        role=payload.role,
        plan=payload.plan,
        days=payload.days,
    )


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: MemberUpdatePayload, request: Request):
    admin = require_admin(request)
    if isinstance(admin, JSONResponse):
        return admin
    result = auth_service.update_user(
        user_id,
        display_name=payload.display_name,
        phone=payload.phone,
        role=payload.role,
        plan=payload.plan,
        days=payload.days,
        is_active=payload.is_active,
        password=payload.password,
    )
    if result.get("error"):
        status = 404 if result["error"] == "not_found" else 400
        return JSONResponse(result, status_code=status)
    return result


@app.get("/api/market/overview")
def market_overview():
    return provider.market_overview()


@app.get("/api/market/morning-briefing")
def market_morning_briefing(request: Request):
    current_user(request)
    return provider.morning_briefing()


@app.get("/api/market/data-quality")
def market_data_quality():
    provider.market_overview()
    return provider.data_quality()


@app.get("/api/market/data-coverage")
def market_data_coverage():
    return provider.data_coverage()


@app.get("/api/system/infrastructure")
def infrastructure_status(request: Request):
    admin = require_admin(request)
    if isinstance(admin, JSONResponse):
        return admin
    return provider.infrastructure_status()


@app.get("/api/system/data-sources")
def data_source_status():
    return {
        "quotes": provider.data_quality(),
        "tushare": provider.tushare.status(),
        "akshare": provider.akshare.status(),
        "priority": ["Tushare（配置后）", "东方财富/腾讯实时接口", "AKShare备用交叉验证", "明确不可用"],
        "policy": "每个结果必须携带来源；备用源只能显式切换，不伪装成主源。",
    }


@app.get("/api/tushare/status")
def tushare_status():
    return provider.tushare.status()


@app.get("/api/tushare/config")
def tushare_config(request: Request):
    admin = require_admin(request)
    if isinstance(admin, JSONResponse):
        return admin
    return {"ok": True, **provider.tushare.config_status(), "status": provider.tushare.status()}


@app.post("/api/tushare/config")
def save_tushare_config(payload: TushareConfigPayload, request: Request):
    admin = require_admin(request)
    if isinstance(admin, JSONResponse):
        return admin
    result = provider.tushare.save_token(payload.token)
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    return {**result, "status": provider.tushare.status(), **provider.tushare.config_status()}


@app.get("/api/stocks/{code}/tushare")
def stock_tushare_snapshot(code: str):
    return provider.tushare.stock_snapshot(code)


@app.get("/api/stocks/{code}/announcements")
def stock_announcements(code: str, limit: int = 20):
    return provider.stock_announcements(code, min(max(limit, 1), 50))


@app.get("/api/stocks/{code}/research-reports")
def stock_research_reports(code: str, limit: int = 20):
    return provider.stock_research_reports(code, min(max(limit, 1), 50))


@app.get("/api/stocks/{code}/fund-flow")
def stock_real_fund_flow(code: str, limit: int = 20):
    return provider.stock_real_fund_flow(code, min(max(limit, 1), 60))


@app.get("/api/stocks/{code}/capital-events")
def stock_capital_events(code: str, limit: int = 12, window: str = "today"):
    selected_window = window if window in {"today", "recent", "all"} else "today"
    return provider.stock_capital_events(code, min(max(limit, 1), 50), window=selected_window)


@app.get("/api/market/breadth")
def market_breadth():
    return provider.market_breadth()


@app.get("/api/market/movers")
def market_movers():
    return provider.market_movers()


@app.get("/api/market/emotion-volume")
def market_emotion_volume():
    return provider.market_emotion_volume()


@app.get("/api/market/hidden-fund-proxy")
def hidden_fund_proxy(request: Request):
    return provider.user_hidden_fund_proxy(current_user(request))


@app.get("/api/market/sectors")
def market_sectors():
    return provider.sector_rankings()


@app.get("/api/market/fund-flow")
def market_fund_flow(request: Request):
    return provider.user_fund_flow(current_user(request))


@app.get("/api/research/events")
def research_events():
    return provider.events()


@app.get("/api/research/strategy-scan")
def strategy_scan(request: Request):
    return provider.user_strategy_scan(current_user(request))


@app.post("/api/research/backtest/{code}")
def research_backtest(code: str, payload: BacktestPayload, request: Request):
    user = current_user(request)
    normalized = provider.normalize_code(code)
    state = provider.read_user_state(user)
    stock = provider.stock_for_user(normalized, state) or provider.fetch_stock_by_code(normalized)
    chart = provider.stock_kline_chart(normalized, stock, limit=520)
    if not chart.get("is_real"):
        return JSONResponse({"error": "real_history_unavailable", "message": chart.get("message") or "真实历史行情不可用，拒绝使用模拟数据回测。", "source": chart.get("source")}, status_code=503)
    if payload.strategy not in {"sma_cross", "2060_recovery"}:
        return JSONResponse({"error": "invalid_strategy", "message": "不支持的策略"}, status_code=400)
    if payload.parameter_scan:
        result = backtest_service.scan(chart["items"], strategy=payload.strategy, initial_cash=payload.initial_cash, fee_bps=payload.fee_bps, slippage_bps=payload.slippage_bps)
    else:
        result = backtest_service.run(chart["items"], strategy=payload.strategy, short_period=max(2, payload.short_period), long_period=max(payload.short_period + 1, payload.long_period), initial_cash=max(1000, payload.initial_cash), fee_bps=max(0, payload.fee_bps), slippage_bps=max(0, payload.slippage_bps))
    result.update({"code": normalized, "name": stock.name if stock else normalized, "data_source": chart.get("source"), "data_updated_at": chart.get("updated_at"), "is_real_data": True})
    return result


@app.get("/api/research/system-audit")
def trading_system_audit():
    return provider.trading_system_audit()


@app.get("/api/research/chokepoint-atlas")
def chokepoint_atlas():
    return provider.chokepoint_atlas()


@app.get("/api/research/breakthrough-review")
def breakthrough_review(request: Request):
    return provider.user_breakthrough_review(current_user(request))


@app.get("/api/research/agent-debate")
def agent_debate():
    return provider.agent_debate()


@app.get("/api/research/serenity-framework")
def serenity_framework(request: Request):
    return provider.user_serenity_framework(current_user(request))


@app.get("/api/research/data-source-plan")
def data_source_plan():
    return provider.data_source_plan()


@app.get("/api/research/quant-upgrade-plan")
def quant_upgrade_plan(request: Request):
    current_user(request)
    return {
        "judgement": "这份量化升级报告有实际价值，适合作为 BlackHorc 从 AI 盯盘工作台升级到量化研究系统的路线图；但自动实盘只能走 QMT/PTrade/券商开放 API 等合规通道。",
        "current_stage": "AI 决策辅助工作台 + 前向验证雏形",
        "priority_gaps": [
            {"name": "历史数据仓库", "why": "全A日K/分钟K、财务公告日、板块成分快照必须齐备，否则回测容易失真。", "status": "进行中：Tushare 已接入，仍需缓存和完整性看板。"},
            {"name": "回测引擎", "why": "每个信号都要能回答过去5年胜率、盈亏比、最大回撤、最大连亏。", "status": "已有基础回测，需要扩到信号级回测。"},
            {"name": "结构化策略定义", "why": "策略必须明确入场、出场、仓位、失效条件，才能稳定复盘和模拟。", "status": "待做：把选股规则 DSL 与交易动作队列打通。"},
            {"name": "模拟盘闭环", "why": "信号→模拟下单→成交记录→归因，至少跑三个月再谈自动实盘。", "status": "待增强：交易日志已有，缺自动撮合和归因。"},
            {"name": "风控熔断", "why": "自动化前必须有单日亏损、最大回撤、数据异常、连续失败停机。", "status": "已有预检/冷静期，需组合层熔断。"},
        ],
        "phases": [
            {"phase": "1", "title": "数据仓库 + 信号回测", "time": "1-2个月", "deliverable": "Tushare/备用源缓存、PIT数据规则、信号胜率看板。"},
            {"phase": "2", "title": "模拟盘自动执行", "time": "2-3个月", "deliverable": "交易动作自动进入模拟撮合，形成每日归因。"},
            {"phase": "3", "title": "小资金合规实盘", "time": "成熟后", "deliverable": "QMT/miniQMT/PTrade 官方通道，默认人工确认，逐步放权。"},
            {"phase": "4", "title": "组合化自动交易", "time": "长期", "deliverable": "仓位模型、相关性控制、熔断和审计日志。"},
        ],
        "red_lines": [
            "不用破解接口或逆向券商客户端自动下单。",
            "不用当日收盘价、未来公告、今日板块成分去回测过去。",
            "回测必须计算手续费、印花税、滑点、涨跌停无法成交。",
            "自动实盘前必须先模拟盘连续验证，并保留人工一键停机。",
        ],
    }


@app.get("/api/review/daily")
def daily_review(request: Request):
    return provider.user_daily_review(current_user(request))


@app.get("/api/review/next-day")
def next_day_review(request: Request):
    return provider.user_next_day_plan(current_user(request))


@app.get("/api/decision/fusion")
def decision_fusion(request: Request):
    return provider.user_decision_fusion(current_user(request))


@app.post("/api/review/daily/save")
def save_daily_review(payload: DailyReviewSavePayload, request: Request):
    user = current_user(request)
    bundle = provider.user_daily_review(user)
    if payload.title:
        bundle["title"] = payload.title
    if payload.summary:
        bundle["summary"] = payload.summary
    review_id = provider.save_user_daily_review(user, bundle)
    return {"ok": True, "id": review_id, "title": bundle.get("title"), "summary": bundle.get("summary")}


@app.get("/api/review/history")
def review_history(request: Request, limit: int = 20):
    return {"items": provider.list_user_daily_reviews(current_user(request), min(max(limit, 1), 100))}


@app.get("/api/review/daily/export.md", response_class=PlainTextResponse)
def export_daily_review_markdown(request: Request):
    bundle = provider.user_daily_review(current_user(request))
    return provider.daily_review_markdown(bundle)


@app.get("/api/trading/action-queue")
def trading_action_queue(request: Request):
    return provider.user_trading_action_queue(current_user(request))


@app.post("/api/trading/precheck")
def trading_precheck(payload: TradePrecheckPayload, request: Request):
    return provider.order_compliance_check(current_user(request), payload.model_dump())


@app.post("/api/trading/cooldown")
def start_trading_cooldown(payload: TradeCooldownPayload, request: Request):
    return provider.start_trade_cooldown(current_user(request), payload.code, payload.reason, payload.minutes)


@app.get("/api/trading/cooldown/{code}")
def trading_cooldown_status(code: str, request: Request):
    return provider.trade_cooldown_status(current_user(request), code)


@app.get("/api/quant-control/radar")
def quant_control_radar(request: Request):
    current_user(request)
    return provider.quant_control_radar()


@app.get("/api/trading/unified-gate")
def trading_unified_gate(request: Request):
    current_user(request)
    return provider.unified_trading_gate()


@app.get("/api/trading/unified-gate/history")
def trading_unified_gate_history(request: Request, limit: int = 50):
    return {"items": provider.unified_gate_history(current_user(request), limit=limit)}


@app.get("/api/risk/dynamic")
def dynamic_risk(code: str, request: Request):
    current_user(request)
    normalized = provider.normalize_code(code)
    stock = provider.fetch_stock_by_code(normalized) or provider.placeholder_stock(normalized)
    thresholds = calculate_dynamic_risk(price=stock.price, volatility_pct=abs(stock.change_pct))
    return {
        "code": normalized,
        "name": stock.name,
        "thresholds": thresholds,
        "source": "observed_change_pct_proxy",
        "disclaimer": "动态阈值仅用于模拟盘和人工复核，不直接生成实盘订单。",
    }


@app.get("/api/research/factors/{code}")
def factor_analysis(code: str, request: Request):
    current_user(request)
    normalized = provider.normalize_code(code)
    stock = provider.fetch_stock_by_code(normalized) or provider.placeholder_stock(normalized)
    change = float(stock.change_pct or 0)
    market = provider.market_overview()
    momentum_regime = classify_momentum_regime(
        momentum_pct=change,
        volatility_pct=abs(change),
        drawdown_pct=min(0, change),
    )
    factors = calculate_factor_snapshot({
        "momentum": 50 + change * 5,
        "value": 60,
        "quality": 65,
        "risk": 50 + abs(change) * 4,
        "fund_flow": 50 + change * 3,
        "sentiment": 65 if market.mood in {"修复", "强势"} else 45,
    })
    return {
        "code": normalized,
        "name": stock.name,
        "momentum_regime": momentum_regime,
        "factor_snapshot": factors,
        "data_sources": ["行情涨跌幅", "市场情绪", "资金流待 Tushare 完整接入"],
        "disclaimer": "因子评分用于研究和模拟复核，不构成投资建议。",
    }


@app.get("/api/trading/ea-simulation/catalog")
def ea_simulation_catalog(request: Request):
    current_user(request)
    return {
        "mode": "paper_only",
        "items": [
            {"id": "momentum_regime", "name": "动量状态切换", "risk": "中", "mode": "paper_only", "description": "动量加速时跟踪，过热或回撤时自动缩小模拟仓位。"},
            {"id": "factor_blend", "name": "多因子组合", "risk": "中", "mode": "paper_only", "description": "动量、价值、质量、资金和情绪综合评分。"},
            {"id": "t0_simulation", "name": "T0 日内回转模拟", "risk": "高", "mode": "paper_only", "description": "仅用于已有持仓的日内回转研究，不触发 A 股个股实盘订单。"},
            {"id": "trend_guard", "name": "趋势守门", "risk": "低", "mode": "paper_only", "description": "趋势确认后观察或减仓，保留人工复核。"},
        ],
        "blocked_templates": ["martingale", "high_leverage_scalping", "external_binary_ea"],
    }


@app.get("/api/events/stream")
def events_stream(request: Request, once: int = 0):
    token = request.query_params.get("token") or request_token(request)
    user = auth_service.user_from_token(token)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async def event_generator():
        payload = provider.tick()
        yield f"event: market\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        if not once:
            while True:
                await asyncio.sleep(5)
                payload = provider.tick()
                yield f"event: market\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/trading/log")
def trading_log(request: Request):
    return {"items": provider.read_user_trade_log(current_user(request))}


@app.get("/api/trading/ea-simulation")
def ea_simulation_status(request: Request):
    return provider.ea_simulation_status(current_user(request))


@app.post("/api/trading/ea-simulation/run")
def run_ea_simulation(payload: EASimulationPayload, request: Request):
    return provider.run_user_ea_simulation(current_user(request), strategy_id=payload.strategy_id, max_orders=payload.max_orders)


@app.post("/api/trading/log")
def record_trading_action(payload: TradeActionPayload, request: Request):
    return provider.record_user_trade_action(current_user(request), payload.model_dump())


@app.get("/api/stocks/search")
def search_stocks(q: str = ""):
    return {"query": q, "items": provider.search_stocks(q)}


@app.get("/api/stocks/{code}/chart")
def stock_chart(code: str, type: str = "minute"):
    return provider.stock_chart(code, type)


@app.get("/api/stocks/{code}/technical-fund-analysis")
def stock_technical_fund_analysis(code: str, request: Request):
    current_user(request)
    return provider.technical_fund_analysis(code)


@app.get("/api/stocks/{code}/resonance")
def stock_resonance(code: str, request: Request, disabled: str = "", quant_risk_score: float = 0):
    """Return configurable multi-indicator resonance for the selected stock.

    The endpoint deliberately keeps the signal calculation server-side so the
    same scoring is used by desktop and mobile clients.  ``disabled`` is a
    comma-separated list of indicator keys (for example ``rsi,cci``).
    """
    current_user(request)
    normalized = provider.normalize_code(code)
    stock = provider.fetch_stock_by_code(normalized) or provider.placeholder_stock(normalized)
    kline = provider.stock_kline_chart(normalized, stock, limit=120)
    indicator_keys = ("ma", "macd", "boll", "sar", "supertrend", "ichimoku", "rsi", "kdj", "cci", "bias", "dmi", "volume", "obv")
    disabled_keys = {item.strip().lower() for item in disabled.split(",") if item.strip()}
    enabled = {key: key not in disabled_keys for key in indicator_keys}
    radar = provider.quant_control_radar()
    risk_window = radar.get("current_window", {}) if isinstance(radar, dict) else {}
    risk_score = float(quant_risk_score or risk_window.get("risk") or 0)
    fund = provider.stock_real_fund_flow(normalized, limit=1)
    latest = (fund.get("items") or [{}])[0]
    main_net = float(latest.get("main_net_wan") or latest.get("main_net") or 0)
    fund_direction = "outflow" if main_net < 0 else "inflow" if main_net > 0 else "neutral"
    result = calculate_resonance(
        kline.get("items") or [],
        enabled=enabled,
        quant_risk_score=risk_score,
        fund_direction=fund_direction,
    )
    return {
        "code": normalized,
        "name": stock.name,
        "period": "day",
        "source": kline.get("source"),
        "data_sources": [kline.get("source"), fund.get("source")],
        **result,
    }


@app.get("/api/stocks/{code}/t-strategy")
def stock_t_strategy(code: str, request: Request):
    current_user(request)
    normalized = provider.normalize_code(code)
    stock = provider.fetch_stock_by_code(normalized) or provider.placeholder_stock(normalized)
    minute = provider.stock_chart(normalized, "minute")
    context = {
        "price": getattr(stock, "price", 0),
        "pe_ttm": getattr(stock, "pe_ttm", 0),
        "amount": getattr(stock, "amount", 0),
        "change_pct": getattr(stock, "change_pct", 0),
    }
    result = calculate_t_strategy(minute.get("items") or [], context)
    return {
        "code": normalized,
        "name": stock.name,
        "source": minute.get("source"),
        "updated_at": minute.get("updated_at"),
        **result,
    }


@app.get("/api/stocks/{code}/compliance-gate")
def stock_compliance_gate(code: str, request: Request):
    user = current_user(request)
    state = provider.read_user_state(user)
    stock = provider.stock_for_user(code, state) or provider.fetch_stock_by_code(code)
    return provider.stock_compliance_gate({
        "code": code,
        "name": stock.name if stock else code,
        "turnover_rate": getattr(stock, "turnover_rate", 0) if stock else 0,
        "amount": getattr(stock, "amount", 0) if stock else 0,
        "pe_ttm": getattr(stock, "pe_ttm", 0) if stock else 0,
    })


@app.get("/api/stocks/{code}/three-source-profile")
def stock_three_source_profile(code: str, request: Request):
    current_user(request)
    return provider.three_source_profile(code)


@app.get("/api/watchlist")
def watchlist(request: Request):
    market = provider.market_overview()
    return [build_watchlist_item(stock, market) for stock in provider.get_user_watchlist(current_user(request))]


@app.get("/api/mobile/dashboard")
def mobile_dashboard(request: Request):
    return build_mobile_dashboard_payload(current_user(request), request)


@app.get("/api/dashboard/bootstrap")
def dashboard_bootstrap(request: Request):
    user = current_user(request)
    market = provider.market_overview()
    data_quality = provider.data_quality()
    source_card = source_traffic_light(
        data_quality.get("provider") or data_quality.get("source") or data_quality.get("quote_source") or market.source_note,
        warnings=data_quality.get("warnings") or [],
        stale=bool(data_quality.get("is_stale")),
        fallback_used=bool(data_quality.get("fallback_used")),
    )
    recommendations = provider.ai_stock_recommendations(limit=5)
    ea_auto_run = provider.ensure_ea_paper_snapshot(user)
    unified_gate = provider.unified_trading_gate()
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "market": market,
        "portfolio": portfolio_summary(request),
        "watchlist": watchlist(request),
        "data_sources": {
            **source_card,
            "warnings": data_quality.get("warnings") or [],
            "quote_source": data_quality.get("quote_source"),
            "index_source": data_quality.get("index_source"),
            "market_source": data_quality.get("market_source"),
            "quote_age_sec": data_quality.get("quote_age_sec"),
            "index_age_sec": data_quality.get("index_age_sec"),
            "market_age_sec": data_quality.get("market_age_sec"),
            "preheat": preheat_service.last_result,
        },
        "ai_recommendations": recommendations,
        "ea_auto_run": ea_auto_run,
        "unified_gate": unified_gate,
        "membership": user.get("membership", {}),
    }


@app.get("/api/portfolio/summary")
def portfolio_summary(request: Request):
    user = current_user(request)
    market = provider.market_overview()
    user_state = provider.read_user_state(user)
    items = [build_watchlist_item(stock, market) for stock in provider.get_user_watchlist(user)]
    held_items = [item for item in items if item.quantity > 0]
    calculated_market_value = sum(item.stock.price * item.quantity for item in held_items)
    calculated_pnl = sum(item.pnl_amount for item in held_items)
    calculated_daily_pnl = sum(item.daily_pnl_amount for item in held_items)
    snapshot = provider.account_snapshot
    manual_cash_available = user_state.get("manual_cash_available")
    if manual_cash_available is not None:
        cash_available = float(manual_cash_available or 0)
        cash_source = "manual_input"
    elif user.get("username") == "laoma":
        cash_available = float(snapshot.get("cash_available") or 0)
        cash_source = "broker_cash_snapshot"
    else:
        cash_available = 0
        cash_source = "not_configured"
    total_market_value = calculated_market_value
    total_pnl = calculated_pnl
    total_daily_pnl = calculated_daily_pnl
    total_assets = total_market_value + cash_available
    valid_held_items = [item for item in held_items if item.cost_valid]
    invalid_cost_items = [item for item in held_items if not item.cost_valid]
    profitable = sum(1 for item in valid_held_items if item.pnl_amount >= 0)
    losing = sum(1 for item in valid_held_items if item.pnl_amount < 0)
    top_positions = sorted(held_items, key=lambda item: item.stock.price * item.quantity, reverse=True)[:3]
    risk_positions = sorted(valid_held_items, key=lambda item: item.pnl_pct)[:3]
    return {
        "total_market_value": round(total_market_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_daily_pnl": round(total_daily_pnl, 2),
        "total_assets": round(total_assets, 2),
        "cash_available": round(cash_available, 2),
        "account": snapshot.get("account") if user.get("username") == "laoma" else f"{user.get('display_name') or user.get('username')} 的账户",
        "snapshot_time": market.updated_at,
        "source": "position_calc_realtime_quote",
        "cash_source": cash_source,
        "calculated_market_value": round(calculated_market_value, 2),
        "calculated_pnl": round(calculated_pnl, 2),
        "calculated_daily_pnl": round(calculated_daily_pnl, 2),
        "pnl_source": "real_time_position_cost",
        "daily_pnl_source": "real_time_position_change",
        "profitable_count": profitable,
        "losing_count": losing,
        "invalid_cost_count": len(invalid_cost_items),
        "data_warnings": [
            {
                "code": item.stock.code,
                "name": item.stock.name,
                "warning": "持仓成本为非正数，浮盈亏未计入汇总；请重新同步券商持仓或手动确认成本。",
            }
            for item in invalid_cost_items
        ],
        "position_count": len(held_items),
        "top_positions": [
            {"name": item.stock.name, "code": item.stock.code, "market_value": round(item.stock.price * item.quantity, 2)}
            for item in top_positions
        ],
        "risk_positions": [
            {"name": item.stock.name, "code": item.stock.code, "pnl_pct": item.pnl_pct, "pnl_amount": item.pnl_amount}
            for item in risk_positions
        ],
    }


@app.post("/api/portfolio/cash")
def update_portfolio_cash(payload: PortfolioCashPayload, request: Request):
    return provider.update_user_manual_cash(current_user(request), payload.cash_available)


@app.post("/api/watchlist")
def add_watchlist(payload: CodePayload, request: Request):
    user = current_user(request)
    provider.add_user_watchlist(user, payload.code)
    return {"ok": True, "code": provider.normalize_code(payload.code)}


@app.delete("/api/watchlist/{code}")
def remove_watchlist(code: str, request: Request):
    provider.remove_user_watchlist(current_user(request), code)
    return watchlist(request)


@app.post("/api/watchlist/position")
def update_watchlist_position(payload: PositionPayload, request: Request):
    result = provider.update_user_position(current_user(request), payload.model_dump())
    if result.get("error"):
        return result
    return watchlist(request)


@app.get("/api/research/candidates")
def candidates(request: Request):
    market = provider.market_overview()
    sectors = provider.sector_rankings()
    user = current_user(request)
    funds = {item["code"]: item for item in provider.user_fund_flow(user)}
    items = []
    for stock in provider.get_user_watchlist(user):
        sector = next((item for item in sectors if item["name"] == stock.tag or stock.tag in item["name"] or item["name"] in stock.tag), None)
        sector_boost = round(((sector or {}).get("strength", 60) - 60) / 5)
        fund = funds.get(stock.code, {})
        fund_boost = 4 if fund.get("estimated_flow_wan", 0) > 0 else -3
        items.append(score_candidate(stock, market, sector_boost=sector_boost, fund_boost=fund_boost))
    return sorted(items, key=lambda item: item.total_score, reverse=True)


@app.get("/api/recommendations/ai")
def ai_recommendations(limit: int = 10):
    return provider.ai_stock_recommendations(limit=limit)


@app.get("/api/recommendations/log")
def recommendation_log():
    return {"items": provider.read_recommendation_log()}


@app.get("/api/screener/catalog")
def screener_catalog(request: Request):
    current_user(request)
    return screener_service.catalog()


@app.post("/api/screener/parse")
def screener_parse(payload: ScreenerParsePayload, request: Request):
    current_user(request)
    try:
        return {"ok": True, "dsl": screener_service.parse_natural_language(payload.text)}
    except StrategyValidationError as exc:
        return JSONResponse({"error": "invalid_strategy", "message": str(exc)}, status_code=400)


@app.post("/api/screener/run")
def screener_run(payload: ScreenerRunPayload, request: Request):
    current_user(request)
    snapshot = market_data_gateway.full_market_snapshot()
    if not snapshot["items"]:
        return JSONResponse({"error": "market_data_unavailable", "message": "全市场数据源暂不可用", **snapshot}, status_code=503)
    try:
        return screener_service.run(snapshot["items"], payload.dsl, snapshot)
    except StrategyValidationError as exc:
        return JSONResponse({"error": "invalid_strategy", "message": str(exc)}, status_code=400)


@app.get("/api/screener/strategies")
def screener_strategies(request: Request):
    user = current_user(request)
    return {"items": provider.persistence.list_screener_strategies(int(user["id"])), "backend": provider.persistence.backend}


@app.post("/api/screener/strategies")
def save_screener_strategy(payload: ScreenerStrategyPayload, request: Request):
    user = current_user(request)
    try:
        dsl = screener_service.validate_dsl(payload.dsl)
    except StrategyValidationError as exc:
        return JSONResponse({"error": "invalid_strategy", "message": str(exc)}, status_code=400)
    strategy_id = provider.persistence.save_screener_strategy(int(user["id"]), {**payload.model_dump(), "dsl": dsl})
    return {"ok": True, "id": strategy_id}


@app.delete("/api/screener/strategies/{strategy_id}")
def delete_screener_strategy(strategy_id: int, request: Request):
    user = current_user(request)
    return {"ok": provider.persistence.delete_screener_strategy(int(user["id"]), strategy_id)}


@app.get("/api/data-sources/health")
def screener_data_health(request: Request):
    current_user(request)
    return {"gateway": market_data_gateway.health_status(), "infrastructure": provider.infrastructure_status(), "quality": provider.data_quality(), "preheat": preheat_service.last_result, "trading_tools": provider.trading_tool_data_sources(), "fullstack_toolkit": provider.fullstack_data_toolkit()}


@app.get("/api/data-sources/preheat")
def run_data_preheat(request: Request):
    current_user(request)
    return preheat_service.run_once(reason="dashboard", force=False)


@app.get("/api/abnormal/catalog")
def abnormal_catalog(request: Request):
    current_user(request)
    return abnormal_service.catalog()


@app.get("/api/abnormal/events")
def abnormal_events(request: Request, mode: str = "realtime", types: str = "", limit: int = 200):
    user = current_user(request)
    if mode == "history":
        return provider.persistence.list_abnormal_events(int(user["id"]), min(max(limit, 1), 500))
    snapshot = market_data_gateway.full_market_snapshot()
    selected = [item.strip() for item in types.split(",") if item.strip()]
    data = abnormal_service.events(snapshot.get("items", []), selected or None, snapshot)
    data["items"] = data["items"][: min(max(limit, 1), 500)]
    return data


@app.post("/api/abnormal/snapshot")
def save_abnormal_snapshot(payload: AbnormalSnapshotPayload, request: Request):
    user = current_user(request)
    snapshot = market_data_gateway.full_market_snapshot()
    data = abnormal_service.events(snapshot.get("items", []), payload.selected_types or None, snapshot)
    snapshot_id = provider.persistence.save_abnormal_events(
        int(user["id"]),
        data["items"],
        {"source": data.get("source"), "fetched_at": data.get("fetched_at"), "selected_types": payload.selected_types},
    )
    return {"ok": True, "id": snapshot_id, **data}


@app.get("/api/research/industry-chain/catalog")
def industry_chain_catalog(request: Request):
    current_user(request)
    return industry_chain_service.catalog()


@app.post("/api/research/industry-chain/analyze")
def analyze_industry_chain(payload: IndustryChainPayload, request: Request):
    user = current_user(request)
    snapshot = market_data_gateway.full_market_snapshot()
    report = industry_chain_service.analyze(payload.query, snapshot.get("items", []), payload.mode)
    report["source"] = snapshot.get("source")
    report["fetched_at"] = snapshot.get("fetched_at")
    report_id = provider.persistence.save_industry_chain_report(int(user["id"]), report)
    return {"ok": True, "id": report_id, "report": report}


@app.get("/api/research/industry-chain/stock/{code}")
def analyze_stock_industry_chain(code: str, request: Request):
    current_user(request)
    snapshot = market_data_gateway.full_market_snapshot()
    report = industry_chain_service.analyze_stock(provider.normalize_code(code), snapshot.get("items", []))
    report["source"] = snapshot.get("source")
    report["fetched_at"] = snapshot.get("fetched_at")
    return report


@app.get("/api/research/industry-chain/history")
def industry_chain_history(request: Request, limit: int = 30):
    user = current_user(request)
    return {"items": provider.persistence.list_industry_chain_reports(int(user["id"]), min(max(limit, 1), 100)), "backend": provider.persistence.backend}


@app.post("/api/recommendations/score")
def recommendation_score(payload: RecommendationScorePayload, request: Request):
    user = current_user(request)
    normalized = provider.normalize_code(payload.code)
    snapshot = market_data_gateway.full_market_snapshot()
    stock = next((item for item in snapshot.get("items", []) if provider.normalize_code(item.get("code", "")) == normalized), None)
    if not stock:
        return JSONResponse({"error": "stock_not_in_snapshot", "message": "当前全市场快照未找到该股票"}, status_code=404)
    abnormal_data = abnormal_service.events([stock], None, snapshot)
    topic = payload.topic or ",".join(stock.get("concepts") or stock.get("matched_conditions") or []) or stock.get("name") or normalized
    industry_report = industry_chain_service.analyze(topic, snapshot.get("items", []), "quick")
    score = recommendation_scoring_service.score(stock, abnormal_data.get("items", []), industry_report)
    recommendation_id = None
    if payload.persist:
        recommendation_id = provider.persistence.save_stock_recommendation(int(user["id"]), {
            "code": normalized,
            "stock_name": stock.get("name") or normalized,
            "strategy_name": f"选股中枢评分 {score['level']}",
            "entry_price": float(stock.get("price") or 0),
            "reason": "；".join(score.get("evidence") or ["选股中枢综合评分纳入观察"]),
            "risk_note": score.get("risk_note", "候选推荐仅用于后续验证，不构成交易建议。"),
            "source": snapshot.get("source", ""),
            "snapshot": {**stock, "score": score, "abnormal": abnormal_data, "industry_chain": industry_report},
            "metrics": {"hub_score": score.get("total_score"), "level": score.get("level")},
        })
    return {"ok": True, "code": normalized, "stock": stock, "score": score, "abnormal": abnormal_data, "industry_chain": industry_report, "recommendation_id": recommendation_id}


@app.post("/api/recommendations")
def create_stock_recommendation(payload: StockRecommendationPayload, request: Request):
    user = current_user(request)
    normalized = provider.normalize_code(payload.code)
    snapshot = market_data_gateway.full_market_snapshot()
    stock = next((item for item in snapshot["items"] if provider.normalize_code(item.get("code", "")) == normalized), None)
    if not stock:
        return JSONResponse({"error": "stock_not_in_snapshot", "message": "当前全市场快照未找到该股票"}, status_code=404)
    recommendation_id = provider.persistence.save_stock_recommendation(int(user["id"]), {
        "code": normalized,
        "stock_name": stock.get("name") or normalized,
        "strategy_name": payload.strategy_name,
        "entry_price": float(stock["price"]),
        "reason": payload.reason or "；".join(stock.get("matched_conditions") or stock.get("signals") or ["人工纳入推荐验证"]),
        "risk_note": payload.risk_note or "候选推荐仅用于后续验证，不构成交易建议。",
        "source": snapshot["source"],
        "snapshot": {**stock, "fetched_at": snapshot["fetched_at"], "fallback_used": snapshot["fallback_used"]},
    })
    return {"ok": True, "id": recommendation_id}


@app.get("/api/recommendations/validation")
def recommendation_validation(request: Request, limit: int = 100):
    user = current_user(request)
    user_id = int(user["id"])
    rows = provider.persistence.list_stock_recommendations(user_id, min(max(limit, 1), 200))
    snapshot = market_data_gateway.full_market_snapshot()
    current_map = {item["code"]: item for item in snapshot["items"]}
    provider.persistence.record_recommendation_prices(user_id, {code: item["price"] for code, item in current_map.items()}, datetime.now().date().isoformat())
    histories = provider.persistence.recommendation_price_history(user_id, [item["id"] for item in rows])
    for item in rows:
        current = current_map.get(item["code"], {})
        item["current_price"] = current.get("price")
        item["current_return_pct"] = round((float(current["price"]) / item["entry_price"] - 1) * 100, 2) if current.get("price") and item["entry_price"] else None
        item["metrics"] = screener_service.recommendation_metrics(item["entry_price"], histories.get(item["id"], []))
        item["tracked_days"] = len(histories.get(item["id"], []))
    return {"items": rows, "source": snapshot["source"], "fetched_at": snapshot["fetched_at"], "is_stale": snapshot["is_stale"]}


@app.post("/api/recommendations/track")
def track_recommendation(payload: CodePayload, request: Request):
    user = current_user(request)
    provider.add_user_watchlist(user, payload.code)
    return {"ok": True, "code": provider.normalize_code(payload.code)}


@app.get("/api/ai/status")
def ai_status(request: Request):
    user = current_user(request)
    scoped_ai, scope = ai_service_for_user(user)
    return {
        "enabled": scoped_ai.enabled,
        "mode": "api" if scoped_ai.enabled else "default",
        "model": scoped_ai.model if scoped_ai.enabled else "local-rule-engine",
        "provider": scoped_ai.provider if scoped_ai.enabled else "local",
        "can_configure": True,
        "config_scope": scope,
        "scope_label": "系统默认配置" if scope == "system" else "个人模型配置",
        "models": scoped_ai.model_options(),
    }


@app.get("/api/ai/config")
def ai_config(request: Request):
    user = current_user(request)
    scoped_ai, scope = ai_service_for_user(user)
    return {**scoped_ai.public_config(), "config_scope": scope, "scope_label": "系统默认配置" if scope == "system" else "个人模型配置"}


@app.put("/api/ai/config")
def save_ai_config(payload: AIConfigPayload, request: Request):
    user = current_user(request)
    scoped_ai, scope = ai_service_for_user(user)
    try:
        config = scoped_ai.save_config(**payload.model_dump())
    except ValueError as exc:
        return JSONResponse({"error": "invalid_ai_config", "message": str(exc)}, status_code=400)
    return {"ok": True, "config": {**config, "config_scope": scope}}


@app.post("/api/ai/config/test")
def test_ai_config(payload: AIConfigPayload, request: Request):
    user = current_user(request)
    scoped_ai, _scope = ai_service_for_user(user)
    try:
        return scoped_ai.test_connection(base_url=payload.base_url, model=payload.model, api_key=payload.api_key, profile_id=payload.profile_id)
    except (ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        return JSONResponse({"ok": False, "error": "connection_failed", "message": str(exc)}, status_code=400)


@app.get("/api/ai/models")
def ai_models(request: Request):
    scoped_ai, scope = ai_service_for_user(current_user(request))
    return {"items": scoped_ai.model_options(), "active_profile_id": scoped_ai.active_profile_id, "config_scope": scope}


@app.get("/api/ai/reports")
def ai_reports(request: Request, code: str = "", limit: int = 30):
    user = current_user(request)
    return {"items": provider.persistence.list_ai_reports(int(user["id"]), provider.normalize_code(code) if code else "", min(max(limit, 1), 100)), "backend": provider.persistence.backend}


def build_ai_analysis(code: str, user: dict, *, model_id: str = "", system_prompt: str = "", question: str = "", allow_local_fallback: bool = True, tools_enabled: bool = True, analysis_mode: str = "decision_report"):
    market = provider.market_overview()
    user_state = provider.read_user_state(user)
    normalized = provider.normalize_code(code)
    stock = provider.stock_for_user(normalized, user_state) or provider.fetch_stock_by_code(normalized)
    if not stock:
        return {"error": "stock_not_found", "code": code}
    item = build_watchlist_item(stock, market)
    sectors = provider.sector_rankings()
    events = provider.events()
    sector = next((entry for entry in sectors if entry["name"] == stock.tag or stock.tag in entry["name"] or entry["name"] in stock.tag), None)
    sector_boost = round(((sector or {}).get("strength", 60) - 60) / 5)
    fund = next((entry for entry in provider.user_fund_flow(user) if entry["code"] == stock.code), {})
    fund_boost = 4 if fund.get("estimated_flow_wan", 0) > 0 else -3
    candidate = score_candidate(stock, market, sector_boost=sector_boost, fund_boost=fund_boost)
    intelligence = {}
    if tools_enabled:
        kline = provider.stock_kline_chart(normalized, stock, 240)
        fundamentals = provider.stock_analysis_fundamentals(normalized)
        intelligence = {
            "data_policy": {
                "rule": "只能引用本对象中实际返回的数据；缺失项必须写明数据未返回，禁止推测或编造。",
                "as_of": datetime.now().isoformat(timespec="seconds"),
            },
            "kline_240d": {**kline, "items": (kline.get("items") or [])[-240:]},
            "fundamentals": fundamentals,
            "announcements": provider.stock_announcements(normalized, 12),
            "research_reports": provider.stock_research_reports(normalized, 12),
            "fund_flow": provider.stock_real_fund_flow(normalized, 20),
        }
        intelligence["tool_audit"] = [
            {"name": "日K行情", "ok": bool(kline.get("is_real")), "source": kline.get("source"), "count": len(kline.get("items") or [])},
            {"name": "公司与财务", "ok": any(part.get("ok") for part in fundamentals.values() if isinstance(part, dict)), "source": "Tushare Pro", "count": sum(len(part.get("rows") or []) for part in fundamentals.values() if isinstance(part, dict))},
            {"name": "公告", "ok": bool(intelligence["announcements"].get("ok")), "source": intelligence["announcements"].get("source"), "count": len(intelligence["announcements"].get("items") or [])},
            {"name": "研报", "ok": bool(intelligence["research_reports"].get("ok")), "source": intelligence["research_reports"].get("source"), "count": len(intelligence["research_reports"].get("items") or [])},
            {"name": "资金流", "ok": bool(intelligence["fund_flow"].get("ok")), "source": intelligence["fund_flow"].get("source"), "count": len(intelligence["fund_flow"].get("items") or [])},
        ]
    scoped_ai, scope = ai_service_for_user(user)
    result = scoped_ai.analyze_stock(item, candidate, market, sectors, events, model_id=model_id, system_prompt=system_prompt, question=question, allow_local_fallback=allow_local_fallback, intelligence=intelligence, analysis_mode=analysis_mode)
    result["config_scope"] = scope
    if result.get("mode") == "api":
        report_id = provider.persistence.save_ai_report(user_id=int(user["id"]), code=normalized, stock_name=stock.name, provider=str(result.get("provider") or ""), model=str(result.get("model") or ""), system_prompt=system_prompt, question=question, result=result)
        result["report_id"] = report_id
        result["persistence_backend"] = provider.persistence.backend
    return result


@app.get("/api/ai/analyze/{code}")
def ai_analyze_stock(code: str, request: Request):
    user = current_user(request)
    return build_ai_analysis(code, user, allow_local_fallback=True)


@app.post("/api/ai/analyze/{code}")
def ai_analyze_stock_with_model(code: str, payload: AIAnalyzePayload, request: Request):
    return build_ai_analysis(code, current_user(request), model_id=payload.model_id, system_prompt=payload.system_prompt, question=payload.question, allow_local_fallback=False, tools_enabled=payload.tools_enabled, analysis_mode=payload.analysis_mode)


@app.websocket("/ws/market")
async def market_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(provider.tick())
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


# ---------- 问财智能选股 / 自然语言问答 ----------

@app.get("/api/wencai/status")
def wencai_status(request: Request):
    current_user(request)
    return provider.wencai.status()


@app.post("/api/wencai/query")
def wencai_query(payload: WencaiScreenPayload, request: Request):
    current_user(request)
    if payload.question:
        return provider.wencai.query(payload.question)
    if payload.conditions:
        return provider.wencai.screen(payload.conditions)
    return JSONResponse({"error": "invalid_request", "message": "请提供 question 或 conditions"}, status_code=400)


@app.post("/api/wencai/screen")
def wencai_screen(payload: WencaiScreenPayload, request: Request):
    current_user(request)
    if not payload.conditions:
        return JSONResponse({"error": "invalid_request", "message": "conditions 不能为空"}, status_code=400)
    stocks = provider.wencai.screen_to_stocks(payload.conditions)
    return {"ok": True, "source": "iwencai", "count": len(stocks), "items": stocks}


# ---------- 东方财富妙想 AI ----------

@app.get("/api/eastmoney-ai/status")
def eastmoney_ai_status(request: Request):
    current_user(request)
    return provider.eastmoney_ai.status()


@app.post("/api/eastmoney-ai/hotspot")
def eastmoney_ai_hotspot(payload: EastMoneyAIQueryPayload, request: Request):
    current_user(request)
    return provider.eastmoney_ai.hotspot_discovery(payload.question or "今日热点")


@app.post("/api/eastmoney-ai/stock-analysis")
def eastmoney_ai_stock_analysis(payload: EastMoneyAIQueryPayload, request: Request):
    current_user(request)
    if not payload.code:
        return JSONResponse({"error": "invalid_request", "message": "code 不能为空"}, status_code=400)
    normalized = provider.normalize_code(payload.code)
    stock = provider.fetch_stock_by_code(normalized) or provider.placeholder_stock(normalized)
    return provider.eastmoney_ai.stock_analysis(normalized, name=stock.name)


@app.post("/api/eastmoney-ai/performance")
def eastmoney_ai_performance(payload: EastMoneyAIQueryPayload, request: Request):
    current_user(request)
    if not payload.code:
        return JSONResponse({"error": "invalid_request", "message": "code 不能为空"}, status_code=400)
    return provider.eastmoney_ai.performance_review(provider.normalize_code(payload.code))


@app.post("/api/eastmoney-ai/sentiment")
def eastmoney_ai_sentiment(request: Request):
    current_user(request)
    return provider.eastmoney_ai.market_sentiment()


@app.post("/api/eastmoney-ai/chat")
def eastmoney_ai_chat(payload: EastMoneyAIQueryPayload, request: Request):
    current_user(request)
    if not payload.question:
        return JSONResponse({"error": "invalid_request", "message": "question 不能为空"}, status_code=400)
    context = {}
    if payload.code:
        context["code"] = provider.normalize_code(payload.code)
    if payload.name:
        context["name"] = payload.name
    return provider.eastmoney_ai.chat(payload.question, context)


# ---- 盯盘智能体（对话式 agent）v4 ----
from .agent_service import register_agent_routes  # noqa: E402

register_agent_routes(app, ai_service)
