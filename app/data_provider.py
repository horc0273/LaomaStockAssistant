from __future__ import annotations

import json
import os
import random
import urllib.parse
import urllib.request
import time
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import requests

from .akshare_service import AKShareService
from .models import MarketIndex, MarketOverview, Stock
from .holdings_config import load_holdings
from .infrastructure import Persistence, RedisCache
from .market_intelligence import MarketIntelligenceService
from .market_data_gateway import collect_paginated_batches
from .quant_engine import build_watchlist_item
from .tushare_service import TushareService
from .trading_gate import calculate_unified_gate
from .wencai_service import WencaiService
from .eastmoney_ai_service import EastMoneyAIService



# 持仓从 holdings.json 读取（真实值不进 git）；仓库内只有脱敏模板 holdings.example.json
STOCK_UNIVERSE: list[Stock] = load_holdings()


INDICES: list[MarketIndex] = [
    MarketIndex(name="上证指数", code="SH000001", price=3970.81, change_pct=0.29, market="A股", source="screenshot-calibrated-demo"),
    MarketIndex(name="深证成指", code="SZ399001", price=14930.19, change_pct=0.74, market="A股", source="screenshot-calibrated-demo"),
    MarketIndex(name="创业板指", code="SZ399006", price=3858.02, change_pct=1.21, market="A股", source="screenshot-calibrated-demo"),
    MarketIndex(name="恒生指数", code="HSI", price=24541.13, change_pct=-1.69, market="港股", source="demo"),
    MarketIndex(name="纳斯达克", code="IXIC", price=25709.43, change_pct=-4.18, market="美股", source="demo"),
    MarketIndex(name="黄金", code="GOLD", price=4310.20, change_pct=0.72, market="商品", source="demo"),
]

INDEX_SECIDS = {
    "SH000001": "1.000001",
    "SZ399001": "0.399001",
    "SZ399006": "0.399006",
}

TENCENT_INDEX_SYMBOLS = {
    "SH000001": "s_sh000001",
    "SZ399001": "s_sz399001",
    "SZ399006": "s_sz399006",
    "HSI": "hkHSI",
    "IXIC": "usIXIC",
    "GOLD": "hf_GC",
}

TENCENT_GLOBAL_INDEX_CODES = {"HSI", "IXIC", "GOLD"}

STOCK_PROFILES: dict[str, dict[str, str]] = {
    "688123.SH": {
        "name": "聚辰股份",
        "market": "A股",
        "tag": "存储芯片",
        "ai": "真实持仓，EEPROM/音圈马达驱动芯片/智能卡芯片方向，按半导体存储链条、科创板强弱、顶背离和资金承接综合跟踪。",
        "keys": "juchengufen jc 688123 存储芯片 EEPROM 半导体 科创板",
    },
    "600584.SH": {
        "name": "长电科技",
        "market": "A股",
        "tag": "半导体封测",
        "ai": "先进封装和半导体封测方向，跟踪半导体板块强度、资金流和趋势修复。",
        "keys": "changdiankeji cdkj 600584 半导体 封测 先进封装",
    },
    "603986.SH": {
        "name": "兆易创新",
        "market": "A股",
        "tag": "存储芯片",
        "ai": "存储芯片与MCU方向，适合作为聚辰股份同产业链对照观察。",
        "keys": "zhaoyichuangxin zycx 603986 存储芯片 MCU 半导体",
    },
}

EASTMONEY_CLIST_URLS = [
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
    "https://43.push2.eastmoney.com/api/qt/clist/get",
]
EASTMONEY_TOKEN = "bd1d9ddb04089700cf9c27f6f7426281"
EASTMONEY_A_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
EASTMONEY_SECTOR_FS = "m:90+t:2"


class DemoDataProvider:
    def __init__(self) -> None:
        self.stocks = {stock.code: deepcopy(stock) for stock in STOCK_UNIVERSE}
        self.indices = {index.code: deepcopy(index) for index in INDICES}
        self.watchlist_codes = [
            "000737.SZ",
            "000997.SZ",
            "002130.SZ",
            "002364.SZ",
            "002452.SZ",
            "002463.SZ",
            "002837.SZ",
            "002938.SZ",
            "600183.SH",
            "601138.SH",
            "601899.SH",
        ]
        for code in self.watchlist_codes:
            if code in self.stocks and self.stocks[code].source == "demo":
                self.stocks[code].source = "broker-screenshot"
            if code in self.stocks:
                self.stocks[code].sort_order = self.watchlist_codes.index(code) + 1
                if not self.stocks[code].alert_price:
                    self.stocks[code].alert_price = round(self.stocks[code].price * 1.03, 2)
        self.account_snapshot = {
            "account": "国投证券 101616056558",
            "total_assets": 233450.13,
            "today_pnl": 4838.80,
            "holding_pnl": 82430.95,
            "market_value": 157660.60,
            "cash_available": 75789.53,
            "source": "broker-screenshot",
            "snapshot_time": "2026-06-09 12:24",
        }
        self.last_quote_refresh = 0.0
        self.last_index_refresh = 0.0
        self.last_quote_source = "local"
        self.last_index_source = "local"
        self.data_quality_warnings: list[str] = []
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "close",
            }
        )
        self.market_snapshot: dict | None = None
        self.last_market_snapshot_refresh = 0.0
        self.sector_snapshot: list[dict] = []
        self.last_sector_refresh = 0.0
        configured_data_dir = os.getenv("LAOMA_STOCK_DATA_DIR", "").strip()
        self.data_dir = Path(configured_data_dir) if configured_data_dir else Path(__file__).resolve().parents[1] / "data"
        self.trade_log_path = self.data_dir / "trade_log.json"
        self.position_store_path = self.data_dir / "positions.json"
        self.recommendation_log_path = self.data_dir / "recommendation_log.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tushare = TushareService(self.data_dir / "tushare_token.txt")
        self.akshare = AKShareService()
        self.persistence = Persistence(self.data_dir)
        self.cache = RedisCache()
        self.intelligence = MarketIntelligenceService(self.session, self.tushare)
        self.load_position_store()
        self.wencai = WencaiService()
        self.eastmoney_ai = EastMoneyAIService()

    @staticmethod
    def to_eastmoney_secid(code: str) -> str:
        raw = code.upper().replace(".SZ", "").replace(".SH", "")
        market = "1" if raw.startswith(("5", "6", "9")) else "0"
        return f"{market}.{raw}"

    @staticmethod
    def normalize_code(raw_code: str, quote_id: str | None = None) -> str:
        code = raw_code.upper()
        if "." in code:
            return code
        if quote_id and quote_id.startswith("1."):
            return f"{code}.SH"
        if quote_id and quote_id.startswith("0."):
            return f"{code}.SZ"
        return f"{code}.SH" if code.startswith(("5", "6", "9")) else f"{code}.SZ"

    def eastmoney_clist(self, params: dict, referer: str) -> dict | None:
        request_params = {
            "pn": 1,
            "pz": 100,
            "po": 1,
            "np": 1,
            "ut": EASTMONEY_TOKEN,
            "fltt": 2,
            "invt": 2,
            **params,
        }
        for url in EASTMONEY_CLIST_URLS:
            for _ in range(2):
                try:
                    response = self.session.get(
                        url,
                        params=request_params,
                        headers={"Referer": referer},
                        timeout=3,
                    )
                    response.raise_for_status()
                    payload = json.loads(response.content.decode("utf-8", errors="ignore"))
                    payload["_source_url"] = url
                    return payload
                except Exception:
                    time.sleep(0.35)
        return None

    def eastmoney_ulist(self, params: dict, referer: str) -> dict | None:
        url = "https://push2delay.eastmoney.com/api/qt/ulist.np/get"
        request_params = {"fltt": 2, "invt": 2, **params}
        try:
            response = self.session.get(
                url,
                params=request_params,
                headers={"Referer": referer},
                timeout=4,
            )
            response.raise_for_status()
            payload = json.loads(response.content.decode("utf-8", errors="ignore"))
            payload["_source_url"] = url
            return payload
        except Exception:
            return None

    def eastmoney_history(self, url: str, params: dict) -> dict | None:
        try:
            response = self.session.get(
                url,
                params=params,
                headers={"Referer": "https://quote.eastmoney.com/"},
                timeout=6,
            )
            response.raise_for_status()
            payload = json.loads(response.content.decode("utf-8", errors="ignore"))
            payload["_source_url"] = response.url.split("?", 1)[0]
            return payload
        except Exception:
            return None

    @staticmethod
    def eastmoney_code(raw_code: str) -> str:
        return f"{raw_code}.SH" if raw_code.startswith(("5", "6", "9")) else f"{raw_code}.SZ"

    def apply_stock_profile(self, stock: Stock) -> Stock:
        profile = STOCK_PROFILES.get(stock.code)
        if not profile:
            return stock
        stock.name = profile.get("name", stock.name)
        stock.market = profile.get("market", stock.market)
        stock.tag = profile.get("tag", stock.tag)
        stock.ai = profile.get("ai", stock.ai)
        stock.keys = f"{stock.keys} {profile.get('keys', '')}".strip()
        return stock

    def refresh_market_snapshot(self, force: bool = False) -> dict | None:
        now = time.time()
        if not force and self.market_snapshot and now - self.last_market_snapshot_refresh < 20:
            return self.market_snapshot
        stats_payload = self.eastmoney_ulist(
            {
                "fields": "f12,f14,f2,f3,f6,f104,f105,f106,f124",
                "secids": "1.000001,0.399001",
            },
            "https://quote.eastmoney.com/",
        )
        stats_rows = (stats_payload or {}).get("data", {}).get("diff") or []
        if not stats_rows:
            return self.market_snapshot

        up_count = sum(int(row.get("f104") or 0) for row in stats_rows)
        down_count = sum(int(row.get("f105") or 0) for row in stats_rows)
        flat_count = sum(int(row.get("f106") or 0) for row in stats_rows)
        turnover = sum(float(row.get("f6") or 0) for row in stats_rows)

        def fetch_rank(fid: str, reverse: bool = True) -> list[dict]:
            payload = self.eastmoney_clist(
                {
                    "pz": 100,
                    "po": 1 if reverse else 0,
                    "fid": fid,
                    "fs": EASTMONEY_A_FS,
                    "fields": "f12,f14,f2,f3,f5,f6,f15,f16,f17,f18,f62",
                },
                "https://quote.eastmoney.com/center/gridlist.html",
            )
            rank_rows = (payload or {}).get("data", {}).get("diff") or []
            return [self.parse_market_row(row) for row in rank_rows if self.parse_market_row(row)]

        top_gainers = fetch_rank("f3", True)[:20]
        top_losers = fetch_rank("f3", False)[:20]
        top_amount = fetch_rank("f6", True)[:20]
        top_main_net = fetch_rank("f62", True)[:20]
        limit_up = sum(1 for item in top_gainers if item["change_pct"] >= 9.8)
        limit_down = sum(1 for item in top_losers if item["change_pct"] <= -9.8)
        breadth_ratio = up_count / max(1, up_count + down_count + flat_count)
        if breadth_ratio >= 0.62 and limit_up > limit_down:
            mood = "强修复"
        elif breadth_ratio >= 0.52:
            mood = "修复"
        elif breadth_ratio <= 0.38:
            mood = "偏弱"
        else:
            mood = "震荡"
        self.market_snapshot = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": (stats_payload or {}).get("_source_url", "eastmoney-ulist") + " + eastmoney-rank",
            "total": up_count + down_count + flat_count,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "turnover_billion": round(turnover / 100000000, 2),
            "breadth_ratio": round(breadth_ratio, 4),
            "mood": mood,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "top_amount": top_amount,
            "top_main_net": top_main_net,
            "rows": [],
        }
        self.last_market_snapshot_refresh = now
        return self.market_snapshot

    def parse_market_row(self, row: dict) -> dict | None:
        change_pct = row.get("f3")
        price = row.get("f2")
        amount = row.get("f6")
        if not isinstance(change_pct, (int, float)) or not isinstance(price, (int, float)) or price <= 0:
            return None
        raw_code = str(row.get("f12", ""))
        parsed = {
            "name": row.get("f14") or raw_code,
            "code": self.eastmoney_code(raw_code),
            "price": float(price),
            "change_pct": float(change_pct),
            "volume": row.get("f5") or 0,
            "amount": float(amount) if isinstance(amount, (int, float)) else 0.0,
            "main_net": float(row.get("f62")) if isinstance(row.get("f62"), (int, float)) else 0.0,
            "high": row.get("f15"),
            "low": row.get("f16"),
            "open": row.get("f17"),
            "prev_close": row.get("f18"),
            "turnover_rate": float(row.get("f8")) if isinstance(row.get("f8"), (int, float)) else None,
            "pe_ttm": float(row.get("f9")) if isinstance(row.get("f9"), (int, float)) else None,
            "volume_ratio": float(row.get("f10")) if isinstance(row.get("f10"), (int, float)) else None,
            "market_cap": float(row.get("f20")) if isinstance(row.get("f20"), (int, float)) else None,
            "circulating_market_cap": float(row.get("f21")) if isinstance(row.get("f21"), (int, float)) else None,
            "pb": float(row.get("f23")) if isinstance(row.get("f23"), (int, float)) else None,
        }
        signals = []
        turnover = parsed.get("turnover_rate") or 0
        volume_ratio = parsed.get("volume_ratio") or 0
        main_net = parsed.get("main_net") or 0
        open_price = parsed.get("open") if isinstance(parsed.get("open"), (int, float)) else 0
        prev_close = parsed.get("prev_close") if isinstance(parsed.get("prev_close"), (int, float)) else 0
        if volume_ratio >= 1.5 and parsed["change_pct"] > 0 and turnover >= 2:
            signals.append("volume_breakout")
        if main_net > 0 and turnover >= 3 and -1.5 <= parsed["change_pct"] <= 3:
            signals.append("low_fund_inflow")
        if open_price and prev_close and open_price >= prev_close * 1.01:
            signals.append("gap_up")
        if open_price and prev_close and open_price < prev_close and parsed["price"] > prev_close:
            signals.append("bullish_engulfing")
        parsed["signals"] = signals
        return parsed

    def eastmoney_full_market_universe(self) -> list[dict]:
        cached = self.cache.get_json("market:full-a-universe")
        if cached:
            return cached
        def fetch_page(page: int, page_size: int) -> dict:
            payload = self.eastmoney_clist(
                {
                    "pn": page,
                    "pz": page_size,
                    "po": 1,
                    "fid": "f6",
                    "fs": EASTMONEY_A_FS,
                    "fields": "f12,f14,f2,f3,f5,f6,f8,f9,f10,f15,f16,f17,f18,f20,f21,f23,f62",
                },
                "https://quote.eastmoney.com/center/gridlist.html",
            )
            data = (payload or {}).get("data") or {}
            return {"total": data.get("total") or 0, "items": data.get("diff") or []}

        rows = collect_paginated_batches(fetch_page, page_size=500, max_workers=6)
        items = [parsed for row in rows if (parsed := self.parse_market_row(row))]
        if items:
            self.cache.set_json("market:full-a-universe", items, ttl=5)
        return items

    def ranked_market_universe_fallback(self) -> list[dict]:
        snapshot = self.refresh_market_snapshot(force=True) or {}
        unique: dict[str, dict] = {}
        for bucket in ("top_gainers", "top_losers", "top_amount", "top_main_net"):
            for item in snapshot.get(bucket, []):
                unique[item["code"]] = item
        return list(unique.values())

    def stock_chart(self, code: str, chart_type: str = "minute") -> dict:
        normalized = self.normalize_code(code)
        chart_type = chart_type if chart_type in {"minute", "kline", "fund"} else "minute"
        stock = self.stocks.get(normalized) or self.fetch_stock_by_code(normalized)
        if chart_type == "minute":
            return self.stock_minute_chart(normalized, stock)
        if chart_type == "kline":
            return self.stock_kline_chart(normalized, stock)
        return self.stock_fund_chart(normalized, stock)

    def technical_fund_analysis(self, code: str) -> dict:
        normalized = self.normalize_code(code)
        stock = self.stocks.get(normalized) or self.fetch_stock_by_code(normalized) or self.placeholder_stock(normalized)
        minute = self.stock_minute_chart(normalized, stock)
        kline = self.stock_kline_chart(normalized, stock, limit=120)
        fund = self.stock_fund_chart(normalized, stock, limit=60)
        k_items = kline.get("items") or []
        m_items = minute.get("items") or []
        f_items = fund.get("items") or []

        def avg(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        closes = [float(item.get("close", item.get("price", 0)) or 0) for item in k_items]
        amounts = [float(item.get("amount", 0) or 0) for item in k_items]
        latest_close = closes[-1] if closes else float(stock.price or 0)
        ma5 = avg(closes[-5:])
        ma20 = avg(closes[-20:])
        ma60 = avg(closes[-60:])
        trend_score = 50
        trend_reasons: list[str] = []
        if latest_close and ma5 and latest_close >= ma5:
            trend_score += 10
            trend_reasons.append("收盘价站上5日均线")
        if ma5 and ma20 and ma5 >= ma20:
            trend_score += 12
            trend_reasons.append("短期均线强于中期均线")
        if ma20 and ma60 and ma20 >= ma60:
            trend_score += 10
            trend_reasons.append("中期趋势保持")
        if len(closes) >= 5 and closes[-1] > closes[-5]:
            trend_score += 8
            trend_reasons.append("近5日价格抬升")
        if len(amounts) >= 5 and amounts[-1] > avg(amounts[-5:-1]) * 1.25:
            trend_score += 8
            trend_reasons.append("最新成交额明显放大")
        trend_score = max(0, min(100, round(trend_score)))

        fund_values = [float(item.get("main", item.get("main_net_wan", 0)) or 0) for item in f_items]
        latest_fund = fund_values[-1] if fund_values else 0.0
        recent_fund = sum(fund_values[-3:]) if fund_values else 0.0
        medium_fund = sum(fund_values[-10:]) if fund_values else 0.0
        previous_two_fund = sum(fund_values[-3:-1]) if len(fund_values) >= 3 else 0.0
        if latest_fund < 0 and (recent_fund < 0 or abs(latest_fund) >= abs(previous_two_fund) * 0.65):
            fund_direction = "短线流出"
        elif latest_fund > 0 and recent_fund > 0:
            fund_direction = "持续流入"
        elif medium_fund > 0:
            fund_direction = "中期仍有承接"
        else:
            fund_direction = "分歧观察"

        tail_items = [item for item in m_items if str(item.get("time", ""))[-5:] >= "14:30"]
        day_high = max((float(item.get("price", 0) or 0) for item in m_items), default=0.0)
        tail_low = min((float(item.get("price", 0) or 0) for item in tail_items), default=0.0)
        tail_last = float((tail_items[-1] if tail_items else {}).get("price", latest_close) or latest_close)
        all_minute_volume = [float(item.get("volume", 0) or 0) for item in m_items]
        tail_volume = sum(float(item.get("volume", 0) or 0) for item in tail_items)
        avg_minute_volume = avg(all_minute_volume)
        tail_drop_pct = ((tail_low - day_high) / day_high * 100) if day_high and tail_low else 0.0
        tail_repair_pct = ((tail_last - tail_low) / tail_low * 100) if tail_low else 0.0
        tail_dump_detected = bool(tail_items and tail_drop_pct <= -2.0 and tail_volume > avg_minute_volume * max(3, len(tail_items) * 0.7))

        suspicion_score = 35
        quant_evidence: list[str] = []
        if tail_dump_detected:
            suspicion_score += 38
            quant_evidence.append("14:30后出现放量急跌，疑似尾盘再平衡或量化集中兑现")
        if latest_fund < 0 and latest_close >= ma5 > 0:
            suspicion_score += 12
            quant_evidence.append("价格仍强但主力资金转负，存在高位换手分歧")
        if len(k_items) >= 2 and float(k_items[-1].get("high", latest_close) or latest_close) >= float(k_items[-2].get("high", latest_close) or latest_close) and float(k_items[-1].get("close", latest_close) or latest_close) < float(k_items[-1].get("high", latest_close) or latest_close):
            suspicion_score += 8
            quant_evidence.append("日K冲高后回落，需要警惕追高被动接盘")
        if recent_fund > 0 and not tail_dump_detected:
            suspicion_score -= 12
        suspicion_score = max(0, min(100, round(suspicion_score)))

        if suspicion_score >= 75:
            stance = "警惕量化尾盘扰动"
            action_points = ["早盘不追高", "尾盘急跌先看承接和资金方向，不情绪割肉", "若资金继续流出，降低仓位或等待次日确认"]
        elif fund_direction in {"持续流入", "中期仍有承接"} and trend_score >= 70:
            stance = "趋势资金共振"
            action_points = ["回踩均线不破可继续观察", "放量急拉不追，等分歧后的承接", "失效条件是资金转负并跌破关键均线"]
        else:
            stance = "分歧观察"
            action_points = ["先观察资金连续性", "不在无量反抽时加仓", "等待日K和分时同时修复"]

        return {
            "code": normalized,
            "name": stock.name,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "data_sources": [
                {"name": "分时", "ok": bool(minute.get("is_real")), "source": minute.get("source"), "count": len(m_items)},
                {"name": "日K", "ok": bool(kline.get("is_real")), "source": kline.get("source"), "count": len(k_items)},
                {"name": "资金趋势", "ok": bool(fund.get("is_real")), "source": fund.get("source"), "count": len(f_items)},
            ],
            "multi_periods": {
                "分时": {
                    "samples": len(m_items),
                    "tail_drop_pct": round(tail_drop_pct, 2),
                    "tail_repair_pct": round(tail_repair_pct, 2),
                    "interpretation": "尾盘放量急跌" if tail_dump_detected else "分时未出现明显尾盘砸盘",
                },
                "日K": {
                    "samples": len(k_items),
                    "trend_score": trend_score,
                    "ma5": round(ma5, 2),
                    "ma20": round(ma20, 2),
                    "ma60": round(ma60, 2),
                    "interpretation": "；".join(trend_reasons) or "趋势证据不足",
                },
                "资金": {
                    "samples": len(f_items),
                    "latest_main": round(latest_fund, 2),
                    "recent_3_sum": round(recent_fund, 2),
                    "recent_10_sum": round(medium_fund, 2),
                    "interpretation": fund_direction,
                },
            },
            "fund_trend": {
                "direction": fund_direction,
                "latest_main": round(latest_fund, 2),
                "recent_3_sum": round(recent_fund, 2),
                "recent_10_sum": round(medium_fund, 2),
                "note": "使用公开资金流/主力净额序列估算，不等同于券商Level-2逐笔暗盘。",
            },
            "quant_watch": {
                "suspicion_score": suspicion_score,
                "tail_dump_detected": tail_dump_detected,
                "tail_drop_pct": round(tail_drop_pct, 2),
                "tail_volume": round(tail_volume, 2),
                "evidence": quant_evidence or ["暂未发现强尾盘量化扰动证据"],
            },
            "stance": stance,
            "action_points": action_points,
            "disclaimer": "K线与资金分析只用于盯盘和风控，不构成自动下单依据；真实交易仍需人工确认。",
        }

    def user_quant_fund_radar(self, user: dict, limit: int = 12) -> dict:
        items = self.get_user_watchlist(user)[:limit]
        alerts: list[dict] = []
        for stock in items:
            try:
                analysis = self.technical_fund_analysis(stock.code)
            except Exception as exc:
                alerts.append(
                    {
                        "code": stock.code,
                        "name": stock.name,
                        "tag": getattr(stock, "tag", "") or "未分类",
                        "suspicion_score": 0,
                        "level": "数据异常",
                        "stance": "等待数据恢复",
                        "fund_direction": "未知",
                        "tail_dump_detected": False,
                        "reason": f"多周期资金分析失败：{exc}",
                        "action_points": ["先不依据该信号交易，等待数据源恢复。"],
                        "evidence": [],
                        "data_sources": [],
                    }
                )
                continue
            quant = analysis.get("quant_watch") or {}
            fund = analysis.get("fund_trend") or {}
            score = int(quant.get("suspicion_score") or 0)
            if score >= 80:
                level = "高"
            elif score >= 65:
                level = "中"
            else:
                level = "低"
            evidence = quant.get("evidence") or []
            reason = "；".join(evidence[:2]) if evidence else analysis.get("stance", "等待更多证据")
            alerts.append(
                {
                    "code": analysis.get("code") or stock.code,
                    "name": analysis.get("name") or stock.name,
                    "tag": getattr(stock, "tag", "") or "未分类",
                    "suspicion_score": score,
                    "level": level,
                    "stance": analysis.get("stance", "分歧观察"),
                    "fund_direction": fund.get("direction", "-"),
                    "tail_dump_detected": bool(quant.get("tail_dump_detected")),
                    "reason": reason,
                    "action_points": analysis.get("action_points") or [],
                    "evidence": evidence,
                    "data_sources": analysis.get("data_sources") or [],
                }
            )
        alerts.sort(key=lambda item: (item["suspicion_score"], item["tail_dump_detected"]), reverse=True)
        high_count = sum(1 for item in alerts if item["suspicion_score"] >= 75)
        top_alerts = alerts[:5]
        tail_session = self.build_quant_tail_session(top_alerts)
        linkage = self.build_quant_linkage(top_alerts)
        return {
            "version": "3.0",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "scope": "current_user_watchlist",
            "policy": "只做盯盘、复盘和人工确认，不自动下单。",
            "summary": {
                "scanned": len(alerts),
                "high_count": high_count,
                "top_score": alerts[0]["suspicion_score"] if alerts else 0,
                "tail_pressure": tail_session["level"],
            },
            "tail_session": tail_session,
            "linkage": linkage,
            "top_alerts": top_alerts,
        }

    def build_quant_tail_session(self, alerts: list[dict]) -> dict:
        focused = [item for item in alerts if item.get("tail_dump_detected") or item.get("suspicion_score", 0) >= 75]
        top_scores = [int(item.get("suspicion_score") or 0) for item in alerts[:5]]
        base_score = round(sum(top_scores) / len(top_scores), 1) if top_scores else 0
        pressure_score = max(0, min(100, int(base_score + len(focused) * 4)))
        if pressure_score >= 78 or len(focused) >= 2:
            level = "高"
            action = "14:00以后以防守和确认承接为主；冲高不追，急跌先看是否有真实资金承接。"
        elif pressure_score >= 58 or focused:
            level = "中"
            action = "尾盘只做小仓观察，优先等待分时企稳和资金回流。"
        else:
            level = "低"
            action = "暂未发现集中的尾盘量化扰动，按原计划复盘即可。"
        return {
            "window": "14:00-15:00",
            "focus_window": "14:30-14:57",
            "level": level,
            "pressure_score": pressure_score,
            "alert_count": len(focused),
            "action": action,
            "watch_codes": [item.get("code") for item in focused[:5]],
        }

    def build_quant_linkage(self, alerts: list[dict]) -> dict:
        tag_counts: dict[str, int] = {}
        for item in alerts:
            tag = str(item.get("tag") or "未分类")
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        dominant_tags = [
            {"name": name, "count": count}
            for name, count in sorted(tag_counts.items(), key=lambda pair: pair[1], reverse=True)[:5]
        ]
        try:
            quant = self.quant_control_radar()
            drivers = (quant.get("global_linkage") or {}).get("drivers") or []
        except Exception:
            drivers = []
        try:
            sectors = [
                {"name": item.get("name"), "change_pct": item.get("change_pct")}
                for item in self.sector_rankings()[:5]
            ]
        except Exception:
            sectors = []
        interpretation = "同一主题多股同时高分，优先按板块联动处理。" if dominant_tags and dominant_tags[0]["count"] >= 2 else "暂无明显群体联动，按个股资金证据逐只确认。"
        return {
            "dominant_tags": dominant_tags,
            "global_drivers": drivers,
            "sector_watch": sectors,
            "interpretation": interpretation,
        }

    def save_user_quant_fund_radar_snapshot(self, user: dict, radar: dict | None = None) -> dict:
        payload = radar or self.user_quant_fund_radar(user)
        state = self.read_user_state(user)
        history = state.setdefault("quant_fund_radar_history", [])
        signature = {
            "summary": payload.get("summary") or {},
            "top_codes": [item.get("code") for item in (payload.get("top_alerts") or [])[:5]],
        }
        if history:
            latest = history[0]
            latest_signature = {
                "summary": latest.get("summary") or {},
                "top_codes": [item.get("code") for item in (latest.get("top_alerts") or [])[:5]],
            }
            try:
                latest_time = datetime.fromisoformat(str(latest.get("created_at")))
                fresh_duplicate = (datetime.now() - latest_time).total_seconds() < 600
            except Exception:
                fresh_duplicate = False
            if fresh_duplicate and latest_signature == signature:
                return latest
        record = {
            "id": f"qfr-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "version": payload.get("version", "3.0"),
            "summary": payload.get("summary") or {},
            "tail_session": payload.get("tail_session") or {},
            "linkage": payload.get("linkage") or {},
            "top_alerts": payload.get("top_alerts") or [],
        }
        history.insert(0, record)
        state["quant_fund_radar_history"] = history[:60]
        self.write_user_state(user, state)
        return record

    def quant_fund_radar_history(self, user: dict, limit: int = 20) -> dict:
        state = self.read_user_state(user)
        items = state.get("quant_fund_radar_history") or []
        return {"items": items[:limit], "count": len(items)}

    def maybe_save_quant_fund_radar_snapshot(self, user: dict, radar: dict) -> dict | None:
        summary = radar.get("summary") or {}
        if summary.get("high_count", 0) <= 0 and summary.get("top_score", 0) < 75:
            return None
        return self.save_user_quant_fund_radar_snapshot(user, radar)

    def user_decision_fusion(self, user: dict) -> dict:
        """Fuse market prep, quant radar, action queue and data-source readiness into one operating board."""
        next_day = self.user_next_day_plan(user)
        quant_radar = self.user_quant_fund_radar(user, limit=12)
        action_queue = self.user_trading_action_queue(user)
        toolkit = self.fullstack_data_toolkit()
        infrastructure = self.infrastructure_status()

        quant_summary = quant_radar.get("summary") or {}
        actions = action_queue.get("actions") or []
        high_priority = [item for item in actions if int(item.get("priority") or 0) >= 80]
        watch_actions = next_day.get("watch_actions") or []
        focus_sectors = next_day.get("focus_sectors") or []

        next_best_actions: list[str] = []
        if high_priority:
            names = "、".join(str(item.get("name") or item.get("code")) for item in high_priority[:3])
            next_best_actions.append(f"对 {names} 先做回测验证和资金流复核，再进入人工确认。")
        elif watch_actions:
            names = "、".join(str(item.get("name") or item.get("code")) for item in watch_actions[:3])
            next_best_actions.append(f"把 {names} 放入明日第一观察队列，等待盘口和板块确认。")
        else:
            next_best_actions.append("今天不强行动，先完成数据源健康检查和明日观察池整理。")

        top_score = int(quant_summary.get("top_score") or 0)
        if top_score >= 80:
            next_best_actions.append("量化嫌疑较高，14:00 后只做防守和错杀识别，不追急拉。")
        elif top_score >= 65:
            next_best_actions.append("尾盘资金扰动中等，优先等承接确认，降低临盘交易频率。")
        else:
            next_best_actions.append("未发现强尾盘量化扰动，按明日作战卡执行即可。")

        connected_count = int(toolkit.get("connected_count") or 0)
        endpoint_count = int(toolkit.get("endpoint_count") or 0)
        if endpoint_count and connected_count / endpoint_count < 0.45:
            data_gate = "数据源偏弱"
            next_best_actions.append("数据源覆盖不足，先补行情/资金/公告链路，不扩大实盘动作。")
        else:
            data_gate = "数据源可用"

        return {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "human_confirmed_decision",
            "tomorrow": {
                "score": next_day.get("score"),
                "stage": next_day.get("stage"),
                "stance": next_day.get("stance"),
                "focus_sectors": focus_sectors[:4],
                "watch_actions": watch_actions[:5],
                "forbidden_actions": next_day.get("forbidden_actions") or [],
                "prep_checklist": next_day.get("prep_checklist") or [],
            },
            "quant": {
                "version": quant_radar.get("version", "3.0"),
                "scanned": quant_summary.get("scanned", 0),
                "high_count": quant_summary.get("high_count", 0),
                "top_score": top_score,
                "tail_pressure": quant_summary.get("tail_pressure"),
                "tail_session": quant_radar.get("tail_session") or {},
                "top_alerts": quant_radar.get("top_alerts") or [],
            },
            "execution": {
                "queue_summary": action_queue.get("summary") or {},
                "high_priority_count": len(high_priority),
                "high_priority_actions": high_priority[:5],
            },
            "data_matrix": {
                "gate": data_gate,
                "toolkit_version": toolkit.get("version"),
                "endpoint_count": endpoint_count,
                "connected_count": connected_count,
                "infrastructure": infrastructure,
            },
            "next_best_actions": next_best_actions,
            "guardrails": [
                "不自动下单：所有真实交易必须经过人工确认。",
                "回测只用于证伪策略，不把历史收益直接当成明日收益。",
                "社区观点、AI结论和单一资金流都只能做交叉验证，不能单独触发买卖。",
            ],
        }

    def stock_minute_chart(self, code: str, stock: Stock | None = None) -> dict:
        payload = self.eastmoney_history(
            "https://push2his.eastmoney.com/api/qt/stock/trends2/get",
            {
                "secid": self.to_eastmoney_secid(code),
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "ndays": 1,
                "iscr": 0,
                "iscca": 0,
            },
        )
        data = (payload or {}).get("data") or {}
        rows = []
        for line in data.get("trends") or []:
            parts = str(line).split(",")
            if len(parts) < 7:
                continue
            try:
                rows.append(
                    {
                        "time": parts[0],
                        "price": float(parts[1]),
                        "avg_price": float(parts[2]),
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": float(parts[5]),
                        "amount": float(parts[6]),
                    }
                )
            except ValueError:
                continue
        if not rows:
            tushare_result = self.tushare.minute(code, freq="1min", days=1)
            ts_rows = []
            for row in tushare_result.get("rows", []):
                try:
                    close = float(row.get("close") or 0)
                    ts_rows.append(
                        {
                            "time": str(row.get("trade_time") or ""),
                            "price": close,
                            "avg_price": close,
                            "high": float(row.get("high") or close),
                            "low": float(row.get("low") or close),
                            "volume": float(row.get("vol") or 0),
                            "amount": float(row.get("amount") or 0),
                        }
                    )
                except (TypeError, ValueError):
                    continue
            ts_rows.sort(key=lambda item: item["time"])
            if ts_rows:
                return {
                    "type": "minute",
                    "code": code,
                    "name": stock.name if stock else code,
                    "source": tushare_result.get("source", "tushare:stk_mins"),
                    "is_real": True,
                    "updated_at": tushare_result.get("updated_at") or datetime.now().isoformat(timespec="seconds"),
                    "items": ts_rows,
                    "message": "东方财富分时不可用，已切换 Tushare 分钟线；若账号无分钟权限则会继续提示不可用。",
                }
        return {
            "type": "minute",
            "code": code,
            "name": data.get("name") or (stock.name if stock else code),
            "source": (payload or {}).get("_source_url", "eastmoney-trends2"),
            "is_real": bool(rows),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "items": rows,
            "message": "" if rows else "未能取得真实分时数据，请稍后重试或检查行情源。",
        }

    def stock_kline_chart(self, code: str, stock: Stock | None = None, limit: int = 120) -> dict:
        tushare_chart = self.stock_kline_chart_tushare(code, stock, limit)
        if tushare_chart.get("is_real"):
            return tushare_chart
        payload = self.eastmoney_history(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            {
                "secid": self.to_eastmoney_secid(code),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": 101,
                "fqt": 1,
                "beg": "20200101",
                "end": "20500101",
                "lmt": limit,
            },
        )
        data = (payload or {}).get("data") or {}
        rows = []
        for line in data.get("klines") or []:
            parts = str(line).split(",")
            if len(parts) < 11:
                continue
            try:
                close = float(parts[2])
                rows.append(
                    {
                        "date": parts[0],
                        "open": float(parts[1]),
                        "close": close,
                        "price": close,
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": float(parts[5]),
                        "amount": float(parts[6]),
                        "amplitude": float(parts[7]),
                        "change_pct": float(parts[8]),
                        "change": float(parts[9]),
                        "turnover": float(parts[10]),
                    }
                )
            except ValueError:
                continue
        if not rows:
            akshare_result = self.akshare.daily(code, limit)
            if akshare_result.get("ok"):
                return {
                    "type": "kline",
                    "code": code,
                    "name": stock.name if stock else code,
                    "source": akshare_result.get("source", "akshare"),
                    "is_real": True,
                    "updated_at": akshare_result.get("updated_at"),
                    "items": akshare_result.get("items", []),
                    "message": "东方财富历史行情不可用，已切换 AKShare 备用源。",
                }
        return {
            "type": "kline",
            "code": code,
            "name": data.get("name") or (stock.name if stock else code),
            "source": (payload or {}).get("_source_url", "eastmoney-kline"),
            "is_real": bool(rows),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "items": rows,
            "message": "" if rows else "未能取得真实日K数据，请稍后重试或检查行情源。",
        }

    def stock_kline_chart_tushare(self, code: str, stock: Stock | None = None, limit: int = 120) -> dict:
        result = self.tushare.daily(code, days=limit)
        rows = []
        for row in result.get("rows", [])[:limit]:
            try:
                close = float(row.get("close") or 0)
                rows.append(
                    {
                        "date": str(row.get("trade_date", "")),
                        "open": float(row.get("open") or 0),
                        "close": close,
                        "price": close,
                        "high": float(row.get("high") or 0),
                        "low": float(row.get("low") or 0),
                        "volume": float(row.get("vol") or 0),
                        "amount": float(row.get("amount") or 0),
                        "change_pct": float(row.get("pct_chg") or 0),
                        "change": float(row.get("change") or 0),
                    }
                )
            except (TypeError, ValueError):
                continue
        rows.sort(key=lambda item: item["date"])
        return {
            "type": "kline",
            "code": code,
            "name": stock.name if stock else code,
            "source": result.get("source", "tushare:daily"),
            "is_real": bool(rows),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "items": rows,
            "message": "" if rows else f"Tushare daily unavailable: {result.get('error') or 'empty rows'}",
        }

    def stock_fund_chart_tushare(self, code: str, stock: Stock | None = None, limit: int = 60) -> dict:
        result = self.tushare.moneyflow(code, days=limit)
        rows = []
        for row in result.get("rows", [])[:limit]:
            try:
                buy_lg = float(row.get("buy_lg_amount") or 0)
                sell_lg = float(row.get("sell_lg_amount") or 0)
                buy_elg = float(row.get("buy_elg_amount") or 0)
                sell_elg = float(row.get("sell_elg_amount") or 0)
                net = row.get("net_mf_amount")
                main = float(net) if net not in (None, "") else (buy_lg + buy_elg - sell_lg - sell_elg)
                rows.append(
                    {
                        "date": str(row.get("trade_date", "")),
                        "main": main,
                        "large": buy_lg - sell_lg,
                        "super_large": buy_elg - sell_elg,
                        "small": float(row.get("buy_sm_amount") or 0) - float(row.get("sell_sm_amount") or 0),
                        "medium": float(row.get("buy_md_amount") or 0) - float(row.get("sell_md_amount") or 0),
                        "price": 0,
                        "change_pct": 0,
                    }
                )
            except (TypeError, ValueError):
                continue
        rows.sort(key=lambda item: item["date"])
        return {
            "type": "fund",
            "code": code,
            "name": stock.name if stock else code,
            "source": result.get("source", "tushare:moneyflow"),
            "is_real": bool(rows),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "items": rows,
            "message": "" if rows else f"Tushare moneyflow unavailable: {result.get('error') or 'empty rows'}",
        }

    def stock_fund_chart(self, code: str, stock: Stock | None = None, limit: int = 60) -> dict:
        tushare_chart = self.stock_fund_chart_tushare(code, stock, limit)
        if tushare_chart.get("is_real"):
            return tushare_chart
        payload = self.eastmoney_history(
            "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
            {
                "secid": self.to_eastmoney_secid(code),
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63",
                "klt": 101,
                "lmt": limit,
            },
        )
        data = (payload or {}).get("data") or {}
        rows = []
        for line in data.get("klines") or []:
            parts = str(line).split(",")
            if len(parts) < 13:
                continue
            try:
                rows.append(
                    {
                        "date": parts[0],
                        "main": float(parts[1]),
                        "small": float(parts[2]),
                        "medium": float(parts[3]),
                        "large": float(parts[4]),
                        "super_large": float(parts[5]),
                        "main_pct": float(parts[6]),
                        "small_pct": float(parts[7]),
                        "medium_pct": float(parts[8]),
                        "large_pct": float(parts[9]),
                        "super_large_pct": float(parts[10]),
                        "price": float(parts[11]),
                        "change_pct": float(parts[12]),
                    }
                )
            except ValueError:
                continue
        return {
            "type": "fund",
            "code": code,
            "name": data.get("name") or (stock.name if stock else code),
            "source": (payload or {}).get("_source_url", "eastmoney-fflow"),
            "is_real": bool(rows),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "items": rows,
            "message": "" if rows else "未能取得真实资金流数据；逐笔暗盘仍需Level-2或第三方授权源。",
        }

    def refresh_sector_snapshot(self, force: bool = False) -> list[dict]:
        now = time.time()
        if not force and self.sector_snapshot and now - self.last_sector_refresh < 30:
            return self.sector_snapshot
        payload = self.eastmoney_clist(
            {
                "pz": 100,
                "fid": "f3",
                "fs": EASTMONEY_SECTOR_FS,
                "fields": "f12,f14,f2,f3,f62,f128,f140,f136,f207,f208",
            },
            "https://quote.eastmoney.com/center/boardlist.html",
        )
        rows = (payload or {}).get("data", {}).get("diff") or []
        if not rows:
            return self.sector_snapshot
        sectors = []
        for row in rows:
            change_pct = row.get("f3")
            if not isinstance(change_pct, (int, float)):
                continue
            fund_flow = float(row.get("f62")) / 100000000 if isinstance(row.get("f62"), (int, float)) else 0.0
            strength = max(0, min(100, round(55 + float(change_pct) * 9 + fund_flow * 1.2)))
            leaders = [item for item in [row.get("f128"), row.get("f207")] if item]
            sectors.append(
                {
                    "name": row.get("f14") or row.get("f12"),
                    "code": row.get("f12"),
                    "price": row.get("f2"),
                    "change_pct": round(float(change_pct), 2),
                    "fund_flow": round(fund_flow, 2),
                    "strength": strength,
                    "leaders": leaders,
                    "reason": f"真实板块涨跌 {float(change_pct):.2f}%，主力净额 {fund_flow:.2f} 亿，领涨 {', '.join(leaders) if leaders else '-'}",
                    "source": payload.get("_source_url", "eastmoney-sector"),
                }
            )
        self.sector_snapshot = sectors
        self.last_sector_refresh = now
        return self.sector_snapshot

    def refresh_quotes(self, codes: list[str] | None = None) -> bool:
        now = time.time()
        target_codes = codes or [code for code in self.stocks if code.endswith((".SZ", ".SH"))]
        target_codes = [code for code in target_codes if code.endswith((".SZ", ".SH"))]
        if now - self.last_quote_refresh < 5 and all(
            self.stocks.get(code) and self.stocks[code].price > 0 and "search" not in self.stocks[code].source
            for code in target_codes
        ):
            return True
        if self.refresh_quotes_tencent(target_codes):
            self.last_quote_refresh = now
            self.last_quote_source = "tencent"
            return True
        secids = ",".join(self.to_eastmoney_secid(code) for code in target_codes if code.endswith((".SZ", ".SH")))
        if not secids:
            return False
        fields = "f12,f14,f2,f3"
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields={fields}&secids={urllib.parse.quote(secids)}"
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://quote.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            ok = self.refresh_quotes_sina(target_codes)
            if ok:
                self.last_quote_refresh = now
                self.last_quote_source = "sina"
            return ok

        rows = payload.get("data", {}).get("diff") or []
        for row in rows:
            code = self.normalize_code(str(row.get("f12", "")), None)
            if code not in self.stocks:
                continue
            stock = self.stocks[code]
            if isinstance(row.get("f2"), (int, float)):
                stock.price = float(row["f2"])
            if isinstance(row.get("f3"), (int, float)):
                stock.change_pct = float(row["f3"])
            stock.source = "eastmoney"
        ok = bool(rows)
        if ok:
            self.last_quote_refresh = now
            self.last_quote_source = "eastmoney"
        return ok

    @staticmethod
    def to_tencent_symbol(code: str) -> str:
        raw = code.upper().replace(".SZ", "").replace(".SH", "")
        prefix = "sh" if raw.startswith(("5", "6", "9")) else "sz"
        return f"{prefix}{raw}"

    def refresh_quotes_tencent(self, codes: list[str]) -> bool:
        symbols = ",".join(self.to_tencent_symbol(code) for code in codes if code.endswith((".SZ", ".SH")))
        if not symbols:
            return False
        url = f"https://qt.gtimg.cn/q={symbols}"
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://gu.qq.com/",
                },
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                text = response.read().decode("gbk", errors="ignore")
        except Exception:
            return False

        updated = False
        for line in text.splitlines():
            if '="' not in line:
                continue
            symbol = line.split("=", 1)[0].replace("v_", "").strip()
            raw_code = symbol[2:]
            code = f"{raw_code}.SH" if symbol.startswith("sh") else f"{raw_code}.SZ"
            payload = line.split('="', 1)[1].rstrip('";')
            fields = payload.split("~")
            if len(fields) < 33 or code not in self.stocks:
                continue
            try:
                current = float(fields[3])
                change_pct = float(fields[32])
            except ValueError:
                continue
            if current <= 0:
                continue
            stock = self.stocks[code]
            stock.name = fields[1] or stock.name
            stock.price = round(current, 3)
            stock.change_pct = round(change_pct, 2)
            quote_time = fields[30] if len(fields) > 30 else ""
            stock.source = f"tencent {quote_time}"
            updated = True
        return updated

    @staticmethod
    def to_sina_symbol(code: str) -> str:
        raw = code.upper().replace(".SZ", "").replace(".SH", "")
        prefix = "sh" if raw.startswith(("5", "6", "9")) else "sz"
        return f"{prefix}{raw}"

    def refresh_quotes_sina(self, codes: list[str]) -> bool:
        symbols = ",".join(self.to_sina_symbol(code) for code in codes if code.endswith((".SZ", ".SH")))
        if not symbols:
            return False
        url = f"https://hq.sinajs.cn/list={symbols}"
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://finance.sina.com.cn/",
                },
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                text = response.read().decode("gbk", errors="ignore")
        except Exception:
            return False

        updated = False
        for line in text.splitlines():
            if '="' not in line:
                continue
            symbol = line.split("=", 1)[0].replace("var hq_str_", "").strip()
            raw_code = symbol[2:]
            code = f"{raw_code}.SH" if symbol.startswith("sh") else f"{raw_code}.SZ"
            payload = line.split('="', 1)[1].rstrip('";')
            fields = payload.split(",")
            if len(fields) < 32 or code not in self.stocks:
                continue
            try:
                open_price = float(fields[1])
                prev_close = float(fields[2])
                current = float(fields[3])
            except ValueError:
                continue
            if current <= 0:
                current = prev_close or open_price
            if current <= 0:
                continue
            stock = self.stocks[code]
            stock.price = round(current, 3)
            stock.change_pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else 0
            stock.source = f"sina {fields[30]} {fields[31]}"
            updated = True
        return updated

    def refresh_indices(self) -> bool:
        now = time.time()
        if now - self.last_index_refresh < 5:
            return True
        if self.refresh_indices_tencent():
            self.last_index_refresh = now
            self.last_index_source = "tencent"
            return True
        fields = "f12,f14,f2,f3"
        secids = ",".join(INDEX_SECIDS.values())
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields={fields}&secids={urllib.parse.quote(secids)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            return False

        reverse = {secid: code for code, secid in INDEX_SECIDS.items()}
        rows = payload.get("data", {}).get("diff") or []
        for row in rows:
            quote_id = None
            raw_code = str(row.get("f12", ""))
            if raw_code == "000001":
                quote_id = "1.000001"
            elif raw_code == "399001":
                quote_id = "0.399001"
            elif raw_code == "399006":
                quote_id = "0.399006"
            code = reverse.get(quote_id or "")
            if not code or code not in self.indices:
                continue
            index = self.indices[code]
            if isinstance(row.get("f2"), (int, float)):
                index.price = float(row["f2"])
            if isinstance(row.get("f3"), (int, float)):
                index.change_pct = float(row["f3"])
            index.source = "eastmoney"
        ok = bool(rows)
        if ok:
            self.last_index_refresh = now
            self.last_index_source = "eastmoney"
        return ok

    def refresh_indices_tencent(self) -> bool:
        symbols = ",".join(TENCENT_INDEX_SYMBOLS.values())
        url = f"https://qt.gtimg.cn/q={symbols}"
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://gu.qq.com/",
                },
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                text = response.read().decode("gbk", errors="ignore")
        except Exception:
            return False

        reverse = {symbol: code for code, symbol in TENCENT_INDEX_SYMBOLS.items()}
        updated = False
        for line in text.splitlines():
            if '="' not in line:
                continue
            symbol = line.split("=", 1)[0].replace("v_", "").strip()
            code = reverse.get(symbol)
            if not code or code not in self.indices:
                continue
            payload = line.split('="', 1)[1].rstrip('";')
            if code == "GOLD":
                fields = payload.split(",")
                if len(fields) < 14:
                    continue
                try:
                    price = float(fields[0])
                    change_pct = float(fields[1])
                except ValueError:
                    continue
                index = self.indices[code]
                index.name = fields[13] or index.name
                index.price = round(price, 2)
                index.change_pct = round(change_pct, 2)
                index.source = f"tencent {fields[12]} {fields[6]}"
                updated = True
                continue
            fields = payload.split("~")
            if len(fields) < 6:
                continue
            try:
                price = float(fields[3])
                change_pct = float(fields[32] if code in TENCENT_GLOBAL_INDEX_CODES and len(fields) > 32 else fields[5])
            except ValueError:
                continue
            index = self.indices[code]
            index.name = fields[1] or index.name
            index.price = round(price, 2)
            index.change_pct = round(change_pct, 2)
            timestamp = fields[30] if code in TENCENT_GLOBAL_INDEX_CODES and len(fields) > 30 else "realtime"
            index.source = f"tencent {timestamp}"
            updated = True
        return updated

    def data_quality(self) -> dict:
        now = time.time()
        quote_age = round(now - self.last_quote_refresh, 1) if self.last_quote_refresh else None
        index_age = round(now - self.last_index_refresh, 1) if self.last_index_refresh else None
        market_age = round(now - self.last_market_snapshot_refresh, 1) if self.last_market_snapshot_refresh else None
        warnings: list[str] = []
        if self.last_index_source != "tencent":
            warnings.append("指数未使用腾讯实时源，可能与券商端存在延迟或口径差异。")
        if quote_age is None or quote_age > 15:
            warnings.append("个股行情超过 15 秒未刷新，请检查网络或行情源。")
        if index_age is None or index_age > 15:
            warnings.append("指数行情超过 15 秒未刷新，请检查网络或行情源。")
        if any("demo" in self.indices[code].source for code in TENCENT_INDEX_SYMBOLS if code in self.indices):
            warnings.append("仍有A股指数处于本地兜底数据，不能用于正式决策。")
        if market_age is None or market_age > 60:
            warnings.append("全A市场宽度超过 60 秒未刷新，涨跌家数/涨跌停/成交额可能滞后。")
        self.data_quality_warnings = warnings
        return {
            "quote_source": self.last_quote_source,
            "index_source": self.last_index_source,
            "market_source": (self.market_snapshot or {}).get("source", "local"),
            "quote_age_sec": quote_age,
            "index_age_sec": index_age,
            "market_age_sec": market_age,
            "provider_priority": ["Tencent", "Eastmoney", "Sina", "Local broker snapshot fallback"],
            "warnings": warnings,
            "indices": [index.model_dump() for index in self.indices.values()],
        }

    def data_coverage(self) -> dict:
        self.market_overview()
        modules = [
            {"name": "A股三大指数", "status": "已接入", "source": self.last_index_source, "use": "判断市场环境、仓位上限、策略开关"},
            {"name": "A股自选实时行情", "status": "已接入", "source": self.last_quote_source, "use": "个股涨跌、今日盈亏、盘中动作提醒"},
            {"name": "券商持仓截图", "status": "已校准", "source": self.account_snapshot["source"], "use": "成本、数量、浮盈、今日盈亏口径"},
            {"name": "AI分析接口", "status": "可配置", "source": "DeepSeek/OpenAI compatible API", "use": "把量化证据压缩成买/卖/减/持动作"},
            {"name": "市场宽度", "status": "第一阶段", "source": "实时指数 + 板块强度模型，待接历史落库", "use": "判断赚钱效应是否扩散"},
            {"name": "情绪与成交量闸门", "status": "已接入", "source": "全A涨跌家数、涨跌停、三大指数、两市成交额", "use": "决定买入、加仓、减仓、止盈动作是否允许执行"},
            {"name": "板块/主题强度", "status": "第一阶段", "source": "持仓主题 + 行情估算，待接东方财富/同花顺板块", "use": "筛选主线方向"},
            {"name": "历史日K", "status": "已接入", "source": "Tushare Pro daily，东方财富备用", "use": "2060、背离、均线、回测"},
            {"name": "分钟线/分时", "status": "已接入", "source": "东方财富 trends2，Tushare暂不覆盖实时分时", "use": "盘中波动、短线盯盘、买卖点观察"},
            {"name": "资金流/主力净入", "status": "部分接入", "source": "Tushare moneyflow 当前账号无权限，使用东方财富/公开行情代理", "use": "确认放量上攻或诱多；无权限时不作为硬买卖依据"},
            {"name": "公告/研报/新闻", "status": "待增强", "source": "公告源 + AI摘要", "use": "事件催化和风险排雷"},
            {"name": "港股/美股/期货/商品", "status": "待增强", "source": "多市场行情源", "use": "全球风险联动和产业链映射"},
            {"name": "截图策略逻辑", "status": "已拆解", "source": "小马盯盘工具截图", "use": "市场宽度、强势股、涨停板、主力净入、机构买卖、期货/中美联动，逐项验证后进入模型权重"},
        ]
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "principle": "正式动作只使用标明来源和时间的数据；估算数据只能影响观察权重，不能单独触发买卖。",
            "modules": modules,
        }

    def data_source_plan(self) -> dict:
        vendors = [
            {
                "name": "Tushare Pro",
                "tier": "高性价比基础层",
                "fit": "日线、财务、公告、研报、集合竞价、分钟数据、港美股扩展",
                "cost": "个人基础积分约200-1500元/年；历史分钟约2000元/年；实时类多为按月单独权限",
                "strength": "Python/HTTP接入简单，覆盖面广，适合先建回测和数据仓库",
                "weakness": "不是完整Level-2盘口；实时分钟、港美股等需要单独权限",
                "decision": "第一优先接入",
            },
            {
                "name": "RiceQuant RQData",
                "tier": "专业研究层",
                "fit": "A股、港股、期货、期权、基金、分钟线、tick、五档快照",
                "cost": "官网文档公开API能力，商业价格通常需联系销售确认",
                "strength": "字段体系规范，适合严肃回测、tick研究和跨品种研究",
                "weakness": "成本通常高于社区型数据源，需确认授权范围",
                "decision": "第二阶段试用评估",
            },
            {
                "name": "券商QMT / PTrade",
                "tier": "交易执行层",
                "fit": "实盘账户、委托、成交回报、行情订阅、自动化执行",
                "cost": "通常随券商账户/资产/权限开通，具体看券商政策",
                "strength": "最接近真实交易闭环，适合后续把人工确认升级为半自动执行",
                "weakness": "数据能力取决于券商和权限，开发调试复杂度更高",
                "decision": "有稳定策略后接入",
            },
            {
                "name": "Wind / iFinD / Choice",
                "tier": "机构终端层",
                "fit": "机构级数据、研报、宏观、行业、资金、终端生态",
                "cost": "通常为较高年费，适合机构预算",
                "strength": "数据权威、覆盖广、服务成熟",
                "weakness": "成本高，不适合作为当前第一步",
                "decision": "暂不优先",
            },
            {
                "name": "公开免费源 / AkShare / 东方财富 / 腾讯",
                "tier": "辅助校验层",
                "fit": "行情展示、候选池补充、低成本原型验证",
                "cost": "低成本或免费",
                "strength": "接入快，适合做原型和多源交叉校验",
                "weakness": "授权、稳定性、字段完整性不足，不应用作最终交易依据",
                "decision": "保留兜底和交叉校验",
            },
        ]
        roadmap = [
            "第一阶段：Tushare Pro + 当前实时公开源，先把日线、财务、公告、研报、集合竞价、历史分钟落库。",
            "第二阶段：试用 RQData 或同等级数据源，验证 tick、五档盘口、成交笔数对策略提升是否明显。",
            "第三阶段：如果交易日志证明策略有效，再接券商 QMT/PTrade 做半自动执行和成交回报复盘。",
            "第四阶段：只有团队规模和收益覆盖成本后，再考虑 Wind/iFinD/Choice 机构终端。",
        ]
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "recommendation": "先接 Tushare Pro 做基础数据仓库，再评估 RQData/tick，最后接券商交易接口。",
            "principle": "先买能提升验证质量的数据，不先买昂贵终端；所有买卖动作必须能回放到当时的数据快照。",
            "must_have": ["真实历史分钟线", "复权日线", "财务公告研报", "集合竞价", "tick/五档试用", "交易日志和成交回报"],
            "vendors": vendors,
            "roadmap": roadmap,
        }

    def market_breadth(self) -> dict:
        self.refresh_indices()
        market_snapshot = self.refresh_market_snapshot() or {}
        sector_snapshot = self.refresh_sector_snapshot()
        sector_items = sector_snapshot[:30]
        sectors = [item["name"] for item in sector_items] or [
            "银行", "贵金属", "钢铁", "煤炭", "交通运输", "休闲服务", "低空经济", "农林牧渔",
            "医药生物", "商业贸易", "国防军工", "家用电器", "建筑材料", "建筑装饰", "房地产",
            "机械设备", "汽车", "新能源", "电子", "半导体", "计算机", "通信", "传媒", "食品饮料",
            "有色金属", "电力设备", "石油石化", "基础化工", "轻工制造", "纺织服饰",
        ]
        rows = []
        today = datetime.now().date()
        total_values = []
        if sector_items:
            values = []
            for item in sector_items:
                value = max(0, min(100, round(50 + item["change_pct"] * 12 + item.get("fund_flow", 0) * 0.8)))
                values.append({"sector": item["name"], "value": value, "change_pct": item["change_pct"], "source": item["source"]})
            total = sum(item["value"] for item in values)
            total_values.append(total)
            rows.append({"date": today.isoformat(), "values": values, "total": total, "source": "real-eastmoney-sector"})

        index_boost = round(sum(index.change_pct for index in list(self.indices.values())[:3]) / 3)
        start_offset = 1 if sector_items else 0
        for day_offset in range(start_offset, 20):
            date = today - timedelta(days=day_offset)
            if date.weekday() >= 5:
                continue
            values = []
            day_heat = max(0, 12 - day_offset // 2 + index_boost * 3)
            for idx, sector in enumerate(sectors):
                seed = (idx * 17 + day_offset * 23 + len(sector) * 11) % 91
                base = 8 + seed % 38
                if sector in {"银行", "半导体", "电子", "计算机", "通信"}:
                    base += 12
                if sector in {"有色金属", "贵金属", "煤炭"} and day_offset < 4:
                    base -= 6
                value = max(0, min(98, base + day_heat))
                values.append({"sector": sector, "value": value, "source": "pending-history-estimate"})
            total = sum(item["value"] for item in values)
            total_values.append(total)
            rows.append({"date": date.isoformat(), "values": values, "total": total, "source": "pending-history-estimate"})

        current_total = total_values[0] if total_values else 0
        avg_total = sum(total_values) / len(total_values) if total_values else 0
        if current_total >= avg_total * 1.08:
            signal = "宽度扩张"
            advice = "市场赚钱效应扩散，可以提高强势板块候选权重，但仍要避开高位放量滞涨。"
        elif current_total <= avg_total * 0.92:
            signal = "宽度收缩"
            advice = "市场赚钱效应收缩，优先保护持仓，新增买入需要更强确认。"
        else:
            signal = "宽度中性"
            advice = "市场宽度处于中性区间，个股动作以模型信号和持仓盈亏为主。"
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "today real eastmoney sector snapshot + pending historical sector breadth provider",
            "signal": signal,
            "advice": advice,
            "market_snapshot": {
                "source": market_snapshot.get("source", "fallback"),
                "total": market_snapshot.get("total"),
                "up_count": market_snapshot.get("up_count"),
                "down_count": market_snapshot.get("down_count"),
                "limit_up": market_snapshot.get("limit_up"),
                "limit_down": market_snapshot.get("limit_down"),
                "turnover_billion": market_snapshot.get("turnover_billion"),
            },
            "columns": sectors,
            "rows": rows,
            "scale": {"low": 0, "middle": 35, "high": 70},
        }

    def fetch_stock_by_code(self, code: str) -> Stock | None:
        normalized = self.normalize_code(code)
        secid = self.to_eastmoney_secid(normalized)
        fields = "f12,f14,f2,f3"
        url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields={fields}&secids={urllib.parse.quote(secid)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            return None
        rows = payload.get("data", {}).get("diff") or []
        if not rows:
            return None
        row = rows[0]
        stock = Stock(
            market="A股",
            name=row.get("f14") or normalized,
            code=normalized,
            price=float(row["f2"]) if isinstance(row.get("f2"), (int, float)) else 0,
            change_pct=float(row["f3"]) if isinstance(row.get("f3"), (int, float)) else 0,
            tag="远程搜索",
            ai="远程搜索加入，等待模型计算和分组确认",
            keys=f"{row.get('f14', '')} {normalized}",
            source="eastmoney",
        )
        self.stocks[normalized] = stock
        return stock

    def placeholder_stock(self, code: str, name: str | None = None) -> Stock:
        normalized = self.normalize_code(code)
        stock = Stock(
            market="A股",
            name=name or normalized,
            code=normalized,
            price=0,
            change_pct=0,
            tag="观察",
            ai="已加入自选，等待行情源刷新后生成模型信号。",
            keys=f"{name or ''} {normalized}",
            source="pending-quote",
        )
        self.apply_stock_profile(stock)
        self.stocks[normalized] = stock
        return stock

    def search_stocks(self, query: str) -> list[Stock]:
        remote = self.search_stocks_remote(query)
        if remote:
            return remote

        q = query.strip().lower().replace(" ", "")
        if not q:
            return list(self.stocks.values())[:8]
        scored: list[tuple[int, Stock]] = []
        for stock in self.stocks.values():
            haystack = f"{stock.name}{stock.code}{stock.keys}{stock.tag}".lower()
            score = 0
            if q in stock.code.lower().replace(".", ""):
                score += 8
            if q in stock.name.lower():
                score += 8
            if q in stock.keys.lower():
                score += 5
            score += sum(1 for char in q if char in haystack)
            if score:
                scored.append((score, stock))
        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [stock for _, stock in scored[:8]]
        if len(matches) < 5:
            existing = {stock.code for stock in matches}
            matches.extend(stock for stock in self.stocks.values() if stock.code not in existing)
        return matches[:8]

    def search_stocks_remote(self, query: str) -> list[Stock]:
        if not query.strip():
            return []
        url = "https://searchapi.eastmoney.com/api/suggest/get?" + urllib.parse.urlencode(
            {
                "input": query,
                "type": "14",
                "token": "D43BF722C8E33BD9A27108CBB74FDD9D",
            }
        )
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="ignore"))
        except Exception:
            return []

        rows = payload.get("QuotationCodeTable", {}).get("Data") or []
        items: list[Stock] = []
        for row in rows[:12]:
            quote_id = row.get("QuoteID") or ""
            raw_code = row.get("Code") or ""
            name = row.get("Name") or raw_code
            if not raw_code or not quote_id.startswith(("0.", "1.")):
                continue
            code = self.normalize_code(raw_code, quote_id)
            stock = deepcopy(self.stocks.get(code)) if code in self.stocks else Stock(
                market="A股",
                name=name,
                code=code,
                price=0,
                change_pct=0,
                tag=row.get("SecurityTypeName") or "A股",
                keys=f"{name} {raw_code} {row.get('PinYin', '')}",
                source="eastmoney-search",
            )
            stock.name = name
            stock.code = code
            stock.source = "eastmoney-search"
            self.apply_stock_profile(stock)
            self.stocks[code] = deepcopy(stock)
            items.append(stock)

        if items:
            self.refresh_quotes([stock.code for stock in items])
            for stock in items:
                if stock.code in self.stocks:
                    live = self.stocks[stock.code]
                    stock.price = live.price
                    stock.change_pct = live.change_pct
                    stock.source = live.source
        return items

    def market_overview(self) -> MarketOverview:
        cached = self.cache.get_json("market:overview")
        if cached:
            return MarketOverview(**cached)
        self.refresh_quotes()
        self.refresh_indices()
        snapshot = self.refresh_market_snapshot() or {}
        sectors = self.refresh_sector_snapshot()
        quality = self.data_quality()
        result = MarketOverview(
            source_mode=f"quotes:{quality['quote_source']} / indices:{quality['index_source']} / market:{quality['market_source']}",
            source_note="行情源按 Tencent -> Eastmoney -> Sina -> 本地券商截图兜底；全A宽度和板块强弱来自东方财富 clist 实时快照。",
            updated_at=datetime.now().isoformat(timespec="seconds"),
            indices=list(self.indices.values()),
            up_count=int(snapshot.get("up_count", 2659)),
            down_count=int(snapshot.get("down_count", 2703)),
            limit_up=int(snapshot.get("limit_up", 75)),
            limit_down=int(snapshot.get("limit_down", 13)),
            turnover_billion=float(snapshot.get("turnover_billion", 1361.3)),
            mood=str(snapshot.get("mood", "修复")),
            themes=[item["name"] for item in sectors[:5]] if sectors else ["银行", "数字乡村", "电子发票", "RFID", "算力分歧"],
        )
        self.cache.set_json("market:overview", result.model_dump(), ttl=4)
        return result

    def morning_briefing(self) -> dict:
        """Build a conservative pre-market/auction briefing from available indices."""
        market = self.market_overview()
        external = [
            {"name": item.name, "code": item.code, "change_pct": round(float(item.change_pct or 0), 2), "source": item.source}
            for item in market.indices
            if item.market != "A股"
        ]
        external_score = round(sum(item["change_pct"] for item in external) / max(1, len(external)), 2)
        if external_score >= 1:
            stance = "外部偏强，等待集合竞价和板块资金确认"
            level = "watch"
        elif external_score <= -1:
            stance = "外部偏弱，开盘先防守，不追跌杀跌"
            level = "warning"
        else:
            stance = "外部中性，优先观察主线承接"
            level = "neutral"
        hour = datetime.now().hour
        minute = datetime.now().minute
        current = hour * 60 + minute
        if 555 <= current < 570:
            auction_window = "集合竞价观察中（09:15-09:25）"
        elif 570 <= current < 690 or 780 <= current < 900:
            auction_window = "连续竞价时段，结合板块和资金确认"
        else:
            auction_window = "非交易时段，等待下一交易日数据"
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "level": level,
            "stance": stance,
            "auction_window": auction_window,
            "external_score": external_score,
            "external_indices": external,
            "a_share_mood": market.mood,
            "a_share_themes": market.themes[:5],
            "source_note": "外盘只作风险偏好参考，不替代A股集合竞价、板块资金和个股基本面。",
        }

    def infrastructure_status(self) -> dict:
        return {"persistence": self.persistence.status(), "cache": self.cache.status(), "akshare": self.akshare.status(), "tushare": self.tushare.status(), "data_dir": str(self.data_dir)}

    def trading_tool_data_sources(self) -> list[dict]:
        return [
            {
                "key": "eastmoney",
                "name": "东方财富",
                "role": "行情、资金流、公告、研报和财务底座",
                "status": "connected",
                "mode": "online_api",
                "used_for": ["实时行情", "K线", "资金流", "公告研报", "全市场选股"],
            },
            {
                "key": "xueqiu",
                "name": "雪球",
                "role": "社区观点、组合关注和散户情绪验证",
                "status": "cookie_ready" if os.getenv("XUEQIU_COOKIE") else "deep_link_ready",
                "mode": "deep_link_first",
                "used_for": ["社区讨论", "长帖观点", "组合关注", "情绪交叉验证"],
            },
            {
                "key": "tongdaxin",
                "name": "通达信",
                "role": "技术指标、公式选股和盘口盯盘",
                "status": "local_indicator_engine",
                "mode": "computed_from_kline",
                "used_for": ["均线", "量价", "MACD", "公式策略"],
            },
        ]

    def fullstack_data_toolkit(self) -> dict:
        layers = [
            {
                "key": "quote",
                "name": "行情层",
                "purpose": "实时行情、盘口、K线与基础估值，优先使用直连 HTTP/TCP 数据源。",
                "endpoints": [
                    {"name": "mootdx K线/五档/逐笔", "provider": "mootdx", "mode": "tcp_7709", "status": "planned"},
                    {"name": "腾讯财经 PE/PB/市值/换手率", "provider": "tencent", "mode": "http", "status": "connected_fallback"},
                    {"name": "百度股市通 K线MA5/10/20", "provider": "baidu", "mode": "http", "status": "planned"},
                    {"name": "东方财富全A批量行情", "provider": "eastmoney", "mode": "http", "status": "connected"},
                ],
            },
            {
                "key": "research",
                "name": "研报层",
                "purpose": "研报列表、PDF、评级、EPS 与语义检索，服务 AI 个股研究。",
                "endpoints": [
                    {"name": "东方财富 reportapi 研报", "provider": "eastmoney", "mode": "http", "status": "connected"},
                    {"name": "同花顺 THS 一致预期EPS", "provider": "ths", "mode": "http", "status": "planned"},
                    {"name": "i问财语义研报", "provider": "iwencai", "mode": "semantic", "status": "planned"},
                    {"name": "研报PDF下载", "provider": "eastmoney", "mode": "http", "status": "planned"},
                ],
            },
            {
                "key": "signal",
                "name": "信号层",
                "purpose": "热点、题材、北向、资金与榜单信号，服务选股和量化雷达。",
                "endpoints": [
                    {"name": "同花顺热点题材归因", "provider": "ths", "mode": "http", "status": "planned"},
                    {"name": "同花顺北向分钟资金", "provider": "ths", "mode": "http", "status": "planned"},
                    {"name": "百度股市通概念归属", "provider": "baidu", "mode": "http", "status": "planned"},
                    {"name": "东方财富 push2 个股资金", "provider": "eastmoney", "mode": "http", "status": "connected"},
                    {"name": "龙虎榜席位", "provider": "eastmoney", "mode": "datacenter-web", "status": "connected"},
                    {"name": "全市场龙虎榜", "provider": "eastmoney", "mode": "datacenter-web", "status": "planned"},
                    {"name": "热门强势股", "provider": "ths", "mode": "http", "status": "planned"},
                ],
            },
            {
                "key": "capital",
                "name": "资金层",
                "purpose": "主力、融资融券、机构席位、大宗交易与股东户数变化。",
                "endpoints": [
                    {"name": "融资融券明细", "provider": "eastmoney", "mode": "datacenter-web", "status": "connected"},
                    {"name": "大宗交易", "provider": "eastmoney", "mode": "datacenter-web", "status": "connected"},
                    {"name": "股东户数变化", "provider": "eastmoney", "mode": "datacenter-web", "status": "connected"},
                    {"name": "机构席位BUY/SELL明细", "provider": "eastmoney", "mode": "datacenter-web", "status": "connected"},
                    {"name": "主力净买额排行", "provider": "eastmoney", "mode": "push2", "status": "connected_partial"},
                ],
            },
            {
                "key": "calendar",
                "name": "日历层",
                "purpose": "解禁、分红、公告、财报与事件窗口，避免踩雷。",
                "endpoints": [
                    {"name": "限售解禁日历", "provider": "eastmoney", "mode": "datacenter-web", "status": "connected"},
                    {"name": "分红送转", "provider": "eastmoney", "mode": "datacenter-web", "status": "planned"},
                    {"name": "巨潮公告orgId格式", "provider": "cninfo", "mode": "http", "status": "connected_partial"},
                    {"name": "财报披露日历", "provider": "eastmoney", "mode": "datacenter-web", "status": "planned"},
                ],
            },
            {
                "key": "sector",
                "name": "板块层",
                "purpose": "行业、概念、ETF、题材链条与领涨领跌归因。",
                "endpoints": [
                    {"name": "行业板块涨跌幅", "provider": "eastmoney", "mode": "http", "status": "connected"},
                    {"name": "概念板块资金流", "provider": "eastmoney", "mode": "http", "status": "planned"},
                    {"name": "ETF行情与溢价", "provider": "tencent/eastmoney", "mode": "http", "status": "planned"},
                    {"name": "产业链主题归因", "provider": "internal_ai", "mode": "computed", "status": "connected"},
                ],
            },
            {
                "key": "governance",
                "name": "治理层",
                "purpose": "数据源健康、缓存、回放、降级、可追溯与零第三方依赖治理。",
                "endpoints": [
                    {"name": "数据源健康检查", "provider": "internal", "mode": "computed", "status": "connected"},
                    {"name": "缓存与持久化状态", "provider": "internal", "mode": "computed", "status": "connected"},
                    {"name": "历史快照回放", "provider": "internal", "mode": "computed", "status": "connected"},
                    {"name": "接口失败降级链路", "provider": "internal", "mode": "computed", "status": "connected"},
                ],
            },
        ]
        endpoint_count = sum(len(layer["endpoints"]) for layer in layers)
        connected_count = sum(
            1
            for layer in layers
            for endpoint in layer["endpoints"]
            if str(endpoint.get("status", "")).startswith("connected")
        )
        return {
            "version": "3.1",
            "title": "A股全栈数据工具包 V3.1",
            "layer_count": len(layers),
            "endpoint_count": endpoint_count,
            "connected_count": connected_count,
            "principles": [
                "去 akshare 依赖：优先直连 HTTP/TCP，降低第三方库版本波动。",
                "先建数据治理矩阵，再逐个接入真实端点。",
                "所有信号保留 provider/mode/status，避免黑箱推荐。",
            ],
            "layers": layers,
        }

    def xueqiu_symbol(self, code: str) -> str:
        normalized = self.normalize_code(code)
        if normalized.endswith(".SH"):
            return f"SH{normalized.split('.')[0]}"
        return f"SZ{normalized.split('.')[0]}"

    def tongdaxin_indicator_snapshot(self, code: str, stock: Stock | None = None) -> dict:
        item = stock or self.stocks.get(self.normalize_code(code)) or self.placeholder_stock(self.normalize_code(code))
        try:
            kline = self.stock_kline_chart(code, item, limit=80)
            rows = kline.get("items") or []
        except Exception:
            rows = []
        closes = [float(row.get("close") or row.get("price") or item.price or 0) for row in rows if row]
        volumes = [float(row.get("volume") or 0) for row in rows if row]
        latest_close = closes[-1] if closes else float(item.price or 0)

        def ma(period: int) -> float:
            source = closes[-period:] if len(closes) >= period else closes
            return round(sum(source) / len(source), 3) if source else round(latest_close, 3)

        ma5, ma10, ma20, ma60 = ma(5), ma(10), ma(20), ma(60)
        volume_ratio = 0
        if len(volumes) >= 6:
            avg5 = sum(volumes[-6:-1]) / 5
            volume_ratio = round(volumes[-1] / avg5, 2) if avg5 else 0
        elif volumes:
            volume_ratio = 1
        signals: list[str] = []
        if ma5 >= ma10 >= ma20:
            signals.append("均线多头排列")
        if latest_close >= ma20:
            signals.append("价格站上20日线")
        if volume_ratio >= 1.5:
            signals.append("放量")
        if not signals:
            signals.append("趋势证据不足")
        return {
            "status": "computed",
            "latest_close": round(latest_close, 3),
            "indicators": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "volume_ratio": volume_ratio},
            "formula_signals": signals,
            "note": "按通达信思路用本地K线计算指标；后续可接入通达信本地数据目录或公式文件。",
        }

    def three_source_profile(self, code: str) -> dict:
        normalized = self.normalize_code(code)
        if normalized not in self.stocks:
            self.placeholder_stock(normalized)
        stock = self.stocks.get(normalized) or self.placeholder_stock(normalized)
        self.refresh_quotes([normalized])
        fund = self.stock_real_fund_flow(normalized, limit=5)
        fund_items = fund.get("items") or []
        latest_fund = fund_items[0] if fund_items else {}
        xueqiu_symbol = self.xueqiu_symbol(normalized)
        eastmoney = {
            "provider": "eastmoney",
            "status": "connected",
            "quote": {
                "price": round(stock.price, 3),
                "change_pct": round(stock.change_pct, 2),
                "source": stock.source,
                "updated_at": getattr(stock, "updated_at", None) or datetime.now().isoformat(timespec="seconds"),
            },
            "fund_flow": {
                "source": fund.get("source"),
                "latest_main_net_wan": latest_fund.get("main_net_wan"),
                "count": len(fund_items),
            },
            "deep_link": f"https://quote.eastmoney.com/{normalized.replace('.', '').lower()}.html",
        }
        xueqiu = {
            "provider": "xueqiu",
            "status": "cookie_ready" if os.getenv("XUEQIU_COOKIE") else "deep_link_ready",
            "symbol": xueqiu_symbol,
            "deep_link": f"https://xueqiu.com/S/{xueqiu_symbol}",
            "sentiment_slots": ["讨论热度", "长帖观点", "组合关注", "散户情绪"],
            "note": "雪球侧先接深链和数据槽位；配置 XUEQIU_COOKIE 后可扩展抓取讨论热度与精选观点。",
        }
        tongdaxin = {
            "provider": "tongdaxin",
            **self.tongdaxin_indicator_snapshot(normalized, stock),
        }
        return {
            "version": "1.0",
            "code": normalized,
            "name": stock.name,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "sources": self.trading_tool_data_sources(),
            "eastmoney": eastmoney,
            "xueqiu": xueqiu,
            "tongdaxin": tongdaxin,
            "fusion": {
                "usage": "AI分析使用：东方财富定事实，通达信定技术结构，雪球定情绪和观点分歧。",
                "priority": ["东方财富行情/资金", "通达信指标/公式", "雪球社区情绪"],
                "risk_note": "社区观点只做交叉验证，不直接作为买卖依据。",
            },
        }

    def stock_announcements(self, code: str, limit: int = 20) -> dict:
        key = f"intel:announcements:{self.normalize_code(code)}:{limit}"
        cached = self.cache.get_json(key)
        if cached:
            cached["cached"] = True
            return cached
        result = self.intelligence.announcements(code, limit)
        self.cache.set_json(key, result, ttl=600)
        return result

    def stock_research_reports(self, code: str, limit: int = 20) -> dict:
        key = f"intel:research:{self.normalize_code(code)}:{limit}"
        cached = self.cache.get_json(key)
        if cached:
            cached["cached"] = True
            return cached
        result = self.intelligence.research_reports(code, limit)
        self.cache.set_json(key, result, ttl=1800)
        return result

    def stock_real_fund_flow(self, code: str, limit: int = 20) -> dict:
        key = f"intel:fund-flow:{self.normalize_code(code)}:{limit}"
        cached = self.cache.get_json(key)
        if cached:
            cached["cached"] = True
            return cached
        result = self.intelligence.stock_fund_flow(code, limit)
        self.cache.set_json(key, result, ttl=300)
        return result

    def stock_capital_events(self, code: str, limit: int = 12, window: str = "today") -> dict:
        normalized = self.normalize_code(code)
        window = window if window in {"today", "recent", "all"} else "today"
        key = f"intel:capital-events:{normalized}:{limit}:{window}"
        cached = self.cache.get_json(key)
        if cached:
            cached["cached"] = True
            return cached
        stock = self.stocks.get(normalized) or self.placeholder_stock(normalized)
        result = self.intelligence.capital_events(normalized, limit, window=window)
        result["code"] = normalized
        result["name"] = stock.name
        self.cache.set_json(key, result, ttl=900)
        return result

    def stock_analysis_fundamentals(self, code: str) -> dict:
        key = f"intel:analysis-fundamentals:{self.normalize_code(code)}"
        cached = self.cache.get_json(key)
        if cached:
            cached["cached"] = True
            return cached
        result = self.intelligence.analysis_fundamentals(code)
        self.cache.set_json(key, result, ttl=3600)
        return result

    def sector_rankings(self) -> list[dict]:
        sectors = self.refresh_sector_snapshot()
        if sectors:
            return sectors[:12]
        return [
            {"name": "银行", "change_pct": 0.97, "strength": 82, "fund_flow": 18.6, "reason": "低位护盘，资金从高位科技成长切换"},
            {"name": "数字乡村", "change_pct": 0.10, "strength": 74, "fund_flow": 6.2, "reason": "新大陆相关主题，适合事件驱动跟踪"},
            {"name": "电子发票", "change_pct": 0.08, "strength": 71, "fund_flow": 4.8, "reason": "新大陆相关概念，关注持续性"},
            {"name": "PCB", "change_pct": 1.86, "strength": 86, "fund_flow": 22.4, "reason": "沪电股份、鹏鼎控股、生益科技持仓相关"},
            {"name": "算力液冷", "change_pct": -0.42, "strength": 61, "fund_flow": -3.6, "reason": "英维克相关，板块分歧仍在"},
            {"name": "资源金属", "change_pct": -1.18, "strength": 48, "fund_flow": -9.2, "reason": "北方铜业、紫金矿业相关，商品联动承压"},
        ]

    def fund_flow_for_stocks(self, stocks: list[Stock]) -> list[dict]:
        codes = [stock.code for stock in stocks]
        self.refresh_quotes(codes)
        rows = []
        for user_stock in stocks:
            stock = self.stocks.get(user_stock.code)
            if not stock:
                continue
            stock = deepcopy(stock)
            stock.cost = user_stock.cost
            stock.quantity = user_stock.quantity
            stock.pnl_amount = user_stock.pnl_amount
            stock.pnl_pct = user_stock.pnl_pct
            base = stock.price * (stock.quantity or 100)
            flow = round(base * stock.change_pct / 100 / 10000, 2)

            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "price": stock.price,
                    "change_pct": stock.change_pct,
                    "estimated_flow_wan": flow,
                    "status": "流入" if flow >= 0 else "流出",
                    "source": stock.source,
                }
            )
        return sorted(rows, key=lambda item: item["estimated_flow_wan"], reverse=True)

    def fund_flow(self) -> list[dict]:
        return self.fund_flow_for_stocks(self.get_watchlist())

    def user_fund_flow(self, user: dict) -> list[dict]:
        return self.fund_flow_for_stocks(self.get_user_watchlist(user))

    def market_movers(self) -> dict:
        snapshot = self.refresh_market_snapshot() or {}
        return {
            "updated_at": snapshot.get("updated_at", datetime.now().isoformat(timespec="seconds")),
            "source": snapshot.get("source", "fallback"),
            "top_gainers": snapshot.get("top_gainers", [])[:20],
            "top_losers": snapshot.get("top_losers", [])[:20],
            "top_amount": snapshot.get("top_amount", [])[:20],
            "top_main_net": snapshot.get("top_main_net", [])[:20],
        }

    def hidden_fund_proxy(self) -> dict:
        movers = self.market_movers()
        watch_codes = set(self.watchlist_codes)
        mover_map: dict[str, dict] = {}
        for bucket in ("top_gainers", "top_losers", "top_amount", "top_main_net"):
            for item in movers.get(bucket, []):
                code = self.normalize_code(str(item.get("code", "")))
                if code:
                    mover_map.setdefault(code, {}).update(item)

        self.refresh_quotes(self.watchlist_codes)
        rows = []
        for code in self.watchlist_codes:
            stock = self.stocks.get(code)
            if not stock:
                continue
            market_row = mover_map.get(code, {})
            amount = float(market_row.get("amount") or 0)
            main_net = float(market_row.get("main_net") or 0)
            amount_score = min(28, amount / 100000000 * 2.5) if amount else abs(stock.change_pct) * 2
            divergence = 0
            notes = []
            if amount and abs(stock.change_pct) < 1.2 and amount > 600000000:
                divergence += 18
                notes.append("价格波动不大但成交额较高，疑似资金吸筹或分歧换手")
            if main_net > 0 and stock.change_pct <= 0:
                divergence += 16
                notes.append("主力净额为正但价格不强，可能存在承接")
            if main_net < 0 and stock.change_pct >= 0:
                divergence += 16
                notes.append("价格维持但主力净额偏弱，警惕派发")
            if abs(stock.change_pct) >= 3:
                divergence += 8
                notes.append("日内波动较大，需要结合成交量确认")
            score = round(max(0, min(100, 35 + amount_score + divergence)))
            if score >= 72:
                status = "重点追踪"
            elif score >= 58:
                status = "观察"
            else:
                status = "普通"
            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "price": stock.price,
                    "change_pct": stock.change_pct,
                    "score": score,
                    "status": status,
                    "amount": amount,
                    "main_net": main_net,
                    "notes": notes or ["公开行情暂未显示明显隐性资金代理信号"],
                    "source": movers.get("source", stock.source),
                }
            )
        rows.sort(key=lambda item: item["score"], reverse=True)
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": movers.get("source", "public-market-proxy"),
            "disclaimer": "这不是交易所真实暗盘数据，而是用公开行情、成交额、主力净额和量价背离构造的隐性资金代理指标。",
            "need_pro_data": ["Level-2逐笔成交", "十档盘口/委托队列", "大单拆单识别", "龙虎榜席位", "封单和炸板率", "券商授权交易回报"],
            "rows": rows,
        }

    def market_emotion_volume(self) -> dict:
        market = self.market_overview()
        snapshot = self.refresh_market_snapshot() or {}
        total = max(1, market.up_count + market.down_count)
        red_ratio = market.up_count / total
        limit_balance = market.limit_up - market.limit_down * 1.8
        index_avg = sum(index.change_pct for index in market.indices[:3]) / max(1, len(market.indices[:3]))
        turnover = market.turnover_billion

        emotion_score = 50
        emotion_score += (red_ratio - 0.5) * 90
        emotion_score += max(-18, min(18, limit_balance * 0.35))
        emotion_score += max(-15, min(15, index_avg * 8))
        if market.down_count > market.up_count * 1.35:
            emotion_score -= 10
        if market.limit_down > 25:
            emotion_score -= 12
        emotion_score = round(max(0, min(100, emotion_score)))

        turnover_anchor = 11000
        volume_score = 50 + (turnover - turnover_anchor) / turnover_anchor * 55
        if turnover >= 15000:
            volume_state = "放量活跃"
            volume_score += 8
        elif turnover >= 11500:
            volume_state = "温和放量"
            volume_score += 3
        elif turnover >= 9000:
            volume_state = "平量震荡"
        else:
            volume_state = "缩量观望"
            volume_score -= 8
        volume_score = round(max(0, min(100, volume_score)))

        composite = round(emotion_score * 0.62 + volume_score * 0.38)
        if composite >= 78:
            state = "亢奋"
            gate = "禁止追高，只允许回踩确认和盈利保护"
            risk_mode = "protect_profit"
        elif composite >= 66:
            state = "强修复"
            gate = "允许筛选强板块核心股，小仓进攻"
            risk_mode = "attack"
        elif composite >= 54:
            state = "弱修复"
            gate = "允许观察和轻仓试错，必须有触发价"
            risk_mode = "probe"
        elif composite >= 42:
            state = "震荡"
            gate = "降低仓位，优先持有确认和防守"
            risk_mode = "defensive"
        else:
            state = "冰点/退潮"
            gate = "停止加仓，优先减仓风控和等待止跌"
            risk_mode = "risk_off"

        rules = [
            "情绪强但量能不足：不追高，等待回踩不破。",
            "情绪弱但放量下跌：先防守，避免深亏仓补仓。",
            "情绪修复且温和放量：允许小仓试错强板块核心股。",
            "亢奋阶段：盈利仓用移动止盈，亏损仓不摊低成本。",
        ]
        evidence = [
            f"红盘率 {red_ratio * 100:.1f}%，上涨 {market.up_count} / 下跌 {market.down_count}",
            f"涨停 {market.limit_up} / 跌停 {market.limit_down}",
            f"三大指数均值 {index_avg:.2f}%",
            f"两市成交额 {turnover:.1f} 亿，状态 {volume_state}",
        ]
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": snapshot.get("source", "market-overview"),
            "emotion_score": emotion_score,
            "volume_score": volume_score,
            "composite_score": composite,
            "state": state,
            "gate": gate,
            "risk_mode": risk_mode,
            "volume_state": volume_state,
            "red_ratio": round(red_ratio * 100, 2),
            "turnover_billion": turnover,
            "rules": rules,
            "evidence": evidence,
        }

    def load_position_store(self) -> None:
        if not self.position_store_path.exists():
            return
        try:
            rows = json.loads(self.position_store_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for code, payload in rows.items():
            normalized = self.normalize_code(code)
            stock = self.stocks.get(normalized)
            if not stock:
                continue
            for field in ("cost", "quantity", "alert_pct", "alert_price", "sort_order", "open_price_target", "take_profit", "stop_loss"):
                if field in payload:
                    setattr(stock, field, payload[field])
            stock.pnl_amount = None
            stock.pnl_pct = None

    def write_position_store(self) -> None:
        payload = {}
        for code in self.watchlist_codes:
            stock = self.stocks.get(code)
            if not stock:
                continue
            payload[code] = {
                "cost": stock.cost,
                "quantity": stock.quantity,
                "alert_pct": stock.alert_pct,
                "alert_price": stock.alert_price,
                "sort_order": stock.sort_order,
                "open_price_target": stock.open_price_target,
                "take_profit": stock.take_profit,
                "stop_loss": stock.stop_loss,
            }
        self.position_store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_position(self, payload: dict) -> dict:
        code = self.normalize_code(str(payload.get("code", "")))
        stock = self.stocks.get(code) or self.fetch_stock_by_code(code)
        if not stock:
            return {"error": "stock_not_found", "code": code}
        if code not in self.watchlist_codes:
            self.watchlist_codes.insert(0, code)

        stock.cost = float(payload.get("cost") or 0)
        stock.quantity = int(float(payload.get("quantity") or 0))
        stock.alert_pct = float(payload.get("alert_pct") or 3)
        stock.alert_price = float(payload.get("alert_price") or 0)
        stock.sort_order = int(float(payload.get("sort_order") or 0))
        stock.open_price_target = float(payload.get("open_price_target") or 0)
        stock.take_profit = float(payload.get("take_profit") or 0)
        stock.stop_loss = float(payload.get("stop_loss") or 0)
        stock.pnl_amount = None
        stock.pnl_pct = None
        if stock.quantity > 0:
            stock.source = "manual-position"
        self.write_position_store()
        return {"ok": True, "stock": stock.model_dump()}

    def read_trade_log(self) -> list[dict]:
        if not self.trade_log_path.exists():
            return []
        try:
            return json.loads(self.trade_log_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def write_trade_log(self, rows: list[dict]) -> None:
        self.trade_log_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_recommendation_log(self) -> list[dict]:
        if not self.recommendation_log_path.exists():
            return []
        try:
            return json.loads(self.recommendation_log_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def write_recommendation_log(self, rows: list[dict]) -> None:
        self.recommendation_log_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def ai_recommendation_categories() -> list[dict]:
        return [
            {"key": "short_term", "label": "短线机会", "description": "涨幅、成交额和资金短线共振，只能等待触发确认。"},
            {"key": "trend", "label": "趋势跟踪", "description": "主线题材或资金持续性较好，适合加入观察池。"},
            {"key": "risk", "label": "风险回避", "description": "涨幅过热、闸门偏谨慎或资金分歧，优先回避追高。"},
            {"key": "observe", "label": "仅观察", "description": "证据还不够强，先进入盯盘，不触发交易。"},
            {"key": "wait_trigger", "label": "等待触发", "description": "有潜力但必须等回踩不破、放量延续或板块确认。"},
        ]

    @classmethod
    def classify_ai_recommendation(cls, *, score: float, change_pct: float, action: str, risk_mode: str) -> tuple[str, str]:
        if risk_mode in {"risk_off", "defensive"} or change_pct >= 8.5:
            return "risk", "风险回避"
        if action == "PRIORITY_TRACK" and 1.2 <= change_pct <= 6.5:
            return "short_term", "短线机会"
        if score >= 72:
            return "trend", "趋势跟踪"
        if score >= 58:
            return "wait_trigger", "等待触发"
        return "observe", "仅观察"

    def ai_stock_recommendations(self, limit: int = 10) -> dict:
        limit = max(1, min(10, int(limit or 10)))
        movers = self.market_movers()
        emotion = self.market_emotion_volume()
        watch_codes = set(self.watchlist_codes)
        held_codes = {code for code in self.watchlist_codes if self.stocks.get(code) and self.stocks[code].quantity > 0}
        sector_rows = self.refresh_sector_snapshot() or []
        strong_sectors = [item for item in sector_rows if item.get("strength", 0) >= 65]
        strong_sector_names = [item.get("name", "") for item in strong_sectors[:6]]

        pool: dict[str, dict] = {}
        bucket_weight = {
            "top_main_net": 18,
            "top_amount": 13,
            "top_gainers": 10,
            "top_losers": -12,
        }
        for bucket, weight in bucket_weight.items():
            for row in movers.get(bucket, [])[:30]:
                code = row.get("code")
                if not code:
                    continue
                normalized = self.normalize_code(str(code))
                current = pool.setdefault(
                    normalized,
                    {
                        "name": row.get("name") or normalized,
                        "code": normalized,
                        "price": float(row.get("price") or 0),
                        "change_pct": float(row.get("change_pct") or 0),
                        "amount": float(row.get("amount") or 0),
                        "main_net": float(row.get("main_net") or 0),
                        "buckets": [],
                        "score": 45,
                    },
                )
                current["score"] += weight
                current["buckets"].append(bucket)
                current["amount"] = max(float(current.get("amount") or 0), float(row.get("amount") or 0))
                current["main_net"] = max(float(current.get("main_net") or 0), float(row.get("main_net") or 0))
                if row.get("price"):
                    current["price"] = float(row.get("price"))
                if row.get("change_pct") is not None:
                    current["change_pct"] = float(row.get("change_pct"))

        for stock in self.stocks.values():
            if not stock.code.endswith((".SZ", ".SH")):
                continue
            if stock.quantity > 0:
                continue
            current = pool.setdefault(
                stock.code,
                {
                    "name": stock.name,
                    "code": stock.code,
                    "price": stock.price,
                    "change_pct": stock.change_pct,
                    "amount": 0,
                    "main_net": 0,
                    "buckets": ["local_universe"],
                    "score": 46,
                },
            )
            if any(key in f"{stock.tag} {stock.ai}" for key in ("算力", "液冷", "电力", "PCB", "半导体", "AI")):
                current["score"] += 8
                current["buckets"].append("theme_match")

        rows = []
        risk_mode = emotion.get("risk_mode", "probe")
        for item in pool.values():
            code = item["code"]
            change_pct = float(item.get("change_pct") or 0)
            amount = float(item.get("amount") or 0)
            main_net = float(item.get("main_net") or 0)
            score = float(item.get("score") or 0)
            evidence = []

            if code in held_codes:
                continue
            if change_pct >= 9.5:
                score -= 18
                evidence.append("接近涨停，不追高，只能观察")
            elif 1.2 <= change_pct <= 6.5:
                score += 14
                evidence.append("涨幅处于可跟踪区间")
            elif -2.5 <= change_pct < 1.2:
                score += 7
                evidence.append("低位震荡，适合纳入观察池")
            elif change_pct < -4:
                score -= 10
                evidence.append("跌幅过深，需要等待止跌确认")

            if amount >= 1000000000:
                score += 12
                evidence.append("成交额靠前，流动性较好")
            elif amount >= 500000000:
                score += 7
                evidence.append("成交额有一定活跃度")
            if main_net > 0:
                score += min(15, main_net / 100000000 * 3)
                evidence.append("公开主力净额偏正")
            if risk_mode in {"risk_off", "defensive"}:
                score -= 12
                evidence.append("市场闸门偏谨慎，先盯盘不买入")
            elif risk_mode in {"attack", "probe"}:
                score += 5
                evidence.append("情绪量能允许小范围试错观察")

            stock = self.stocks.get(code)
            if stock:
                item["name"] = stock.name
                item["price"] = stock.price
                item["change_pct"] = stock.change_pct
                if stock.tag:
                    evidence.append(f"本地主题标签：{stock.tag}")
            elif code.endswith((".SZ", ".SH")):
                fetched = self.fetch_stock_by_code(code)
                if fetched:
                    item["name"] = fetched.name
                    item["price"] = fetched.price
                    item["change_pct"] = fetched.change_pct

            action = "TRACK"
            if score >= 82 and risk_mode not in {"risk_off", "defensive"}:
                action = "PRIORITY_TRACK"
            elif score < 58:
                action = "WATCH_ONLY"

            strategy_tags = []
            if "top_main_net" in item.get("buckets", []):
                strategy_tags.append("主力净流入")
            if "top_amount" in item.get("buckets", []):
                strategy_tags.append("成交额靠前")
            if "top_gainers" in item.get("buckets", []):
                strategy_tags.append("强势上涨")
            if "theme_match" in item.get("buckets", []):
                strategy_tags.append("主线题材")
            if not strategy_tags:
                strategy_tags.append("观察候选")

            trigger_plan = "回踩不破后再跟踪" if action == "WATCH_ONLY" else "放量延续或回踩承接确认后跟踪" if action == "TRACK" else "优先盯盘，次日若量价延续可重点复核"
            risk_note = "市场闸门偏谨慎，先观察不追高。" if risk_mode in {"risk_off", "defensive"} else "若次日量能衰减或板块转弱，及时降级为观察。"
            observation = evidence[0] if evidence else "等待下一交易日量价结构确认"

            signal_category, signal_label = self.classify_ai_recommendation(
                score=score,
                change_pct=change_pct,
                action=action,
                risk_mode=risk_mode,
            )

            rows.append(
                {
                    "name": item.get("name") or code,
                    "code": code,
                    "price": round(float(item.get("price") or 0), 3),
                    "change_pct": round(float(item.get("change_pct") or 0), 2),
                    "score": round(max(0, min(100, score))),
                    "action": action,
                    "signal_category": signal_category,
                    "signal_label": signal_label,
                    "in_watchlist": code in watch_codes,
                    "amount": round(amount / 100000000, 2) if amount else 0,
                    "main_net": round(main_net / 100000000, 2) if main_net else 0,
                    "reason": "AI建议先纳入盯盘验证，不直接触发买入。重点看板块资金、量价延续和回踩不破。",
                    "evidence": evidence[:5] or ["来自涨幅、成交额、资金流和本地主题池的综合排序"],
                    "source": movers.get("source", "market-rank"),
                }
            )

        rows.sort(key=lambda row: (row["in_watchlist"], -row["score"], -abs(row["change_pct"])))
        rows = rows[:limit]
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "limit": limit,
            "source": movers.get("source", "market-rank"),
            "market_gate": {
                "state": emotion.get("state"),
                "risk_mode": risk_mode,
                "score": emotion.get("composite_score"),
                "gate": emotion.get("gate"),
            },
            "principle": "最多推荐10只。推荐只代表纳入盯盘和后续验证，不等同于买入；真正买卖还要经过情绪量能、仓位、触发价和失效条件确认。",
            "categories": self.ai_recommendation_categories(),
            "strong_sectors": strong_sector_names,
            "items": rows,
        }

    def track_recommendation(self, code: str) -> dict:
        normalized = self.normalize_code(code)
        recommendations = self.ai_stock_recommendations(limit=10)
        item = next((row for row in recommendations.get("items", []) if row["code"] == normalized), None)
        self.add_watchlist(normalized)
        stock = self.stocks.get(normalized)
        entry = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "name": (stock.name if stock else None) or (item or {}).get("name") or normalized,
            "code": normalized,
            "baseline_price": round((stock.price if stock else (item or {}).get("price") or 0), 3),
            "baseline_change_pct": round((stock.change_pct if stock else (item or {}).get("change_pct") or 0), 2),
            "score": (item or {}).get("score"),
            "reason": (item or {}).get("reason", "手动纳入AI推荐盯盘"),
            "evidence": (item or {}).get("evidence", []),
            "status": "tracking",
            "review_plan": "后续按1日/3日/5日收益、最大回撤和是否触发模型信号复盘推荐准确性",
        }
        rows = self.read_recommendation_log()
        if not any(row.get("code") == normalized and row.get("status") == "tracking" for row in rows):
            rows.insert(0, entry)
            self.write_recommendation_log(rows[:200])
        return {"ok": True, "tracked": entry, "recommendations": self.ai_stock_recommendations(limit=10)}

    def record_trade_action(self, payload: dict) -> dict:
        code = self.normalize_code(str(payload.get("code", "")))
        queue = self.trading_action_queue()
        action_item = next((item for item in queue.get("actions", []) if item["code"] == code), None)
        if not action_item:
            return {"error": "action_not_found", "code": code}
        mode = payload.get("mode", "paper")
        entry = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "status": "simulated" if mode == "paper" else "manual_confirmed",
            "name": action_item["name"],
            "code": action_item["code"],
            "action": action_item["action"],
            "label": action_item["label"],
            "price": action_item["price"],
            "quantity": action_item["quantity"],
            "trigger_price": action_item["trigger_price"],
            "invalidation_price": action_item["invalidation_price"],
            "pnl_pct": action_item["pnl_pct"],
            "pnl_amount": action_item["pnl_amount"],
            "daily_pnl": action_item["daily_pnl"],
            "reason": action_item["reason"],
            "evidence": action_item["evidence"],
            "market_gate": queue.get("gate"),
            "emotion_volume": queue.get("emotion_volume"),
            "note": payload.get("note", ""),
            "review": {
                "next_check": action_item["next_step"],
                "result": "pending",
                "exit_reason": "",
            },
        }
        rows = self.read_trade_log()
        rows.insert(0, entry)
        self.write_trade_log(rows[:500])
        return {"ok": True, "entry": entry, "count": len(rows[:500])}

    def serenity_framework(self) -> dict:
        market = self.market_overview()
        self.refresh_quotes(self.watchlist_codes)
        fund_rows = {item["code"]: item for item in self.fund_flow()}
        breakthrough_rows = {item["code"]: item for item in self.breakthrough_review().get("rows", [])}
        chokepoint_roles: dict[str, list[str]] = {}
        chokepoint_lanes: dict[str, list[str]] = {}
        for lane in self.chokepoint_atlas().get("lanes", []):
            for position in lane.get("mapped_positions", []):
                code = position.get("code")
                if not code:
                    continue
                chokepoint_roles.setdefault(code, []).append(position.get("role", ""))
                chokepoint_lanes.setdefault(code, []).append(lane.get("name", ""))

        rows = []
        for code in self.watchlist_codes:
            stock = self.stocks.get(code)
            if not stock:
                continue
            fund = fund_rows.get(code, {})
            breakthrough = breakthrough_rows.get(code, {})
            role_list = [item for item in chokepoint_roles.get(code, []) if item]
            lane_list = [item for item in chokepoint_lanes.get(code, []) if item]
            industry_score = 68
            if any(key in f"{stock.tag} {stock.ai}" for key in ("算力", "液冷", "PCB", "半导体", "电力", "AI")):
                industry_score += 10
            if role_list:
                industry_score += 8
            fund_score = 58 + (8 if float(fund.get("estimated_flow_wan") or 0) > 0 else -4)
            model_score = int(breakthrough.get("score", 55))
            risk_penalty = 12 if stock.change_pct > 7 or stock.change_pct < -7 else 4
            serenity_score = round(max(0, min(100, industry_score * 0.35 + fund_score * 0.2 + model_score * 0.25 + 70 * 0.2 - risk_penalty)))
            if serenity_score >= 78:
                priority = "优先深挖"
            elif serenity_score >= 65:
                priority = "保持跟踪"
            else:
                priority = "仅观察"
            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "tag": stock.tag,
                    "price": stock.price,
                    "change_pct": stock.change_pct,
                    "serenity_score": serenity_score,
                    "priority": priority,
                    "supply_chain_role": " / ".join(role_list[:2]) if role_list else "待补产业链角色",
                    "lanes": " / ".join(lane_list[:2]) if lane_list else stock.tag,
                    "bottleneck_hypothesis": self.serenity_bottleneck_for(stock, role_list),
                    "verification": [
                        f"公开资金估算：{round(float(fund.get('estimated_flow_wan') or 0), 2)} 万",
                        f"突破复核：{model_score}",
                        f"当前涨跌：{stock.change_pct:.2f}%",
                    ],
                    "next_research": self.serenity_next_step(stock, role_list, model_score),
                }
            )
        rows.sort(key=lambda item: item["serenity_score"], reverse=True)
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "根据 Serenity.skill / 远山财经研究框架截图整理为内部研究模块",
            "principle": "先研究系统和产业链，再决定是否盯盘；先找瓶颈和验证材料，再讨论买卖动作。",
            "warning": "不要盲目抄作业。该模块只负责建框架、排序和提醒验证，最终交易仍要经过行情、仓位和风控确认。",
            "dimensions": [
                {"name": "总览", "job": "今日优先队列、活跃信号、最新信息流"},
                {"name": "观点", "job": "记录公开观点关联了哪些公司和产业环节"},
                {"name": "股票", "job": "按观察、积极观察、谨慎、高风险分队列筛选"},
                {"name": "提及表现", "job": "统计被提及后1日/3日/5日窗口表现"},
                {"name": "战绩", "job": "按不同时间段复盘历史表现"},
                {"name": "供应链", "job": "看公司之间的产业关系和上下游位置"},
                {"name": "行业", "job": "判断哪些主题拥挤、哪些主题正在变热"},
                {"name": "AI分析", "job": "整理边际变化、风险提示和验证清单"},
            ],
            "framework_cards": [
                {"name": "拆产业链", "detail": "从需求端拆到材料、设备、零部件和客户。"},
                {"name": "找瓶颈", "detail": "看产能、认证、技术门槛、替代难度和交付周期。"},
                {"name": "列清单", "detail": "公司位置、验证材料、风险点、跟踪项。"},
                {"name": "做对比", "detail": "把多家公司放在同一条供应链里比较。"},
            ],
            "market_context": {
                "mood": market.mood,
                "turnover_billion": market.turnover_billion,
                "up_count": market.up_count,
                "down_count": market.down_count,
            },
            "rows": rows[:20],
        }

    @staticmethod
    def serenity_bottleneck_for(stock: Stock, roles: list[str]) -> str:
        text = f"{stock.tag} {stock.ai} {' '.join(roles)}"
        if any(key in text for key in ("液冷", "散热")):
            return "AI Factory交付的热管理瓶颈，重点验证订单、产能和客户认证。"
        if any(key in text for key in ("PCB", "覆铜板", "连接")):
            return "高速互联材料瓶颈，重点验证高端产品占比、良率和客户结构。"
        if any(key in text for key in ("电力", "电气")):
            return "数据中心供电与配电交付瓶颈，重点验证订单节奏和毛利率。"
        if any(key in text for key in ("半导体", "设备", "算力")):
            return "算力产业链关键设备或国产替代瓶颈，重点验证替代进度。"
        return "产业链角色仍需补充，先收集公告、研报、客户和订单证据。"

    @staticmethod
    def serenity_next_step(stock: Stock, roles: list[str], model_score: int) -> str:
        if not roles:
            return "先补供应链角色：客户、产品、替代难度、主要竞争对手。"
        if model_score >= 72:
            return "进入重点盯盘：跟踪分时承接、资金流和回踩不破。"
        return "继续验证：等公告、资金流或K线结构给出更强确认。"

    def events(self) -> list[dict]:
        return [
            {"time": datetime.now().isoformat(timespec="seconds"), "type": "市场", "title": "A股三大指数实时刷新，市场处于修复状态", "impact": "中性偏多", "symbols": []},
            {"time": datetime.now().isoformat(timespec="seconds"), "type": "主题", "title": "数字乡村、电子发票进入新大陆事件观察池", "impact": "观察", "symbols": ["000997.SZ"]},
            {"time": datetime.now().isoformat(timespec="seconds"), "type": "资金", "title": "PCB持仓方向盈利垫较厚，需监控顶背离和放量分歧", "impact": "风险提示", "symbols": ["002463.SZ", "002938.SZ", "600183.SH"]},
            {"time": datetime.now().isoformat(timespec="seconds"), "type": "模型", "title": "北方铜业、紫金矿业进入资源线弱势修复观察", "impact": "谨慎", "symbols": ["000737.SZ", "601899.SH"]},
        ]

    def strategy_scan(self) -> dict:
        sectors = self.sector_rankings()
        sector_map = {item["name"]: item for item in sectors}
        rows = []
        for code in self.watchlist_codes:
            stock = self.stocks.get(code)
            if not stock:
                continue
            sector = sector_map.get(stock.tag, {})
            momentum = max(0, min(100, 55 + stock.change_pct * 5))
            fund_score = max(0, min(100, 60 + stock.change_pct * 3 + (sector.get("fund_flow", 0) or 0)))
            ma_score = 72 if stock.pnl_pct is not None and stock.pnl_pct > -12 else 48
            if stock.name in {"新大陆", "沃尔核材", "北方铜业"}:
                strategy = "2060低位修复"
                ma_score += 8
            elif stock.cost < 0 or (stock.pnl_amount or 0) > 10000:
                strategy = "盈利仓趋势保护"
                ma_score += 12
            else:
                strategy = "动量资金过滤"
            total = round(momentum * 0.25 + fund_score * 0.25 + ma_score * 0.3 + (sector.get("strength", 60) or 60) * 0.2)
            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "strategy": strategy,
                    "momentum": round(momentum),
                    "fund_score": round(fund_score),
                    "ma_score": round(ma_score),
                    "sector_strength": sector.get("strength", 60),
                    "total_score": total,
                    "action": "推送关注" if total >= 70 else "继续观察",
                    "reason": f"{strategy}；主题{stock.tag}；价格{stock.price:.2f}；持仓盈亏{stock.pnl_pct if stock.pnl_pct is not None else 0:.2f}%",
                }
            )
        rows.sort(key=lambda item: item["total_score"], reverse=True)
        return {
            "engine": "Internal Sequoia-X Inspired Scanner",
            "source_reference": "Sequoia-X / A股自动选股系统思路：全量扫描、策略因子、收盘后推送",
            "schedule": "交易日 15:10 扫描，15:20 推送",
            "data_plan": ["Eastmoney实时行情", "AKShare/Tushare历史K线", "SQLite/本地缓存", "企业微信/飞书推送"],
            "strategies": [
                {"name": "2060低位修复", "factors": ["大盘20/60/120过滤", "缩地量", "20日线回踩", "阳包阴"]},
                {"name": "动量资金过滤", "factors": ["动量排序", "资金流", "板块强度", "成交额"]},
                {"name": "均线/MACD/RSI交叉", "factors": ["MA5/10/20/60", "MACD金叉", "RSI低位修复"]},
                {"name": "盈利仓趋势保护", "factors": ["顶背离", "放量滞涨", "利润回撤", "短线均线破位"]},
            ],
            "rows": rows,
        }

    def trading_system_audit(self) -> dict:
        market = self.market_overview()
        questions = [
            {
                "id": 1,
                "group": "系统定义",
                "question": "这个系统叫什么？",
                "answer": "内部AI量化盯盘系统：市场宽度过滤 + 2060/趋势/背离模型 + 持仓风控 + AI动作解释。",
                "status": "已定义",
            },
            {
                "id": 2,
                "group": "系统定义",
                "question": "它属于趋势、震荡、套利还是配置？",
                "answer": "当前主系统属于趋势跟随与弱转强修复混合型，不做无风险套利；账户层面做配置和风险约束。",
                "status": "已定义",
            },
            {
                "id": 3,
                "group": "系统定义",
                "question": "核心思想是什么？",
                "answer": "先判断市场是否允许进攻，再找强板块和可验证个股模型；动作必须同时有市场、板块、价格、持仓四类证据。",
                "status": "已定义",
            },
            {
                "id": 4,
                "group": "系统定义",
                "question": "适合什么市场？",
                "answer": "适合A股有明确主线、宽度不极端收缩、成交额活跃的市场；弱市中只做减仓、观察和风控。",
                "status": "已定义",
            },
            {
                "id": 5,
                "group": "系统定义",
                "question": "适合什么周期？",
                "answer": "盘中盯盘用2-10秒行情刷新，执行周期以日内观察 + 日K确认为主；完整回测后再扩展到分钟级策略。",
                "status": "部分定义",
            },
            {
                "id": 6,
                "group": "系统定义",
                "question": "它成立的核心假设是什么？",
                "answer": "市场宽度和板块强度领先个股胜率；价格模型只有在流动性和板块环境支持时才更可靠。",
                "status": "待回测验证",
            },
            {
                "id": 7,
                "group": "执行规则",
                "question": "入场规则是什么？",
                "answer": "需要市场不处于偏弱、板块强度靠前、个股模型分数达标、价格未高位过热，并给出明确买入区和失效价。",
                "status": "部分定义",
            },
            {
                "id": 8,
                "group": "执行规则",
                "question": "加仓规则是什么？",
                "answer": "只允许盈利仓或模型确认后的修复仓加仓；加仓必须满足放量突破/回踩不破/宽度未恶化。",
                "status": "待细化",
            },
            {
                "id": 9,
                "group": "执行规则",
                "question": "减仓/止盈规则是什么？",
                "answer": "高位放量滞涨、顶背离预警、板块强度退潮、盈利仓跌破短线均线时分批减仓。",
                "status": "部分定义",
            },
            {
                "id": 10,
                "group": "执行规则",
                "question": "止损/退出规则是什么？",
                "answer": "跌破模型失效位、宽度持续收缩且个股弱于板块、亏损仓反弹无量时退出或降仓。",
                "status": "部分定义",
            },
            {
                "id": 11,
                "group": "执行规则",
                "question": "仓位和风控规则是什么？",
                "answer": "市场偏弱降低总仓位；亏损较深仓优先做风险观察；单票动作必须给置信度和最大风险条件。",
                "status": "部分定义",
            },
            {
                "id": 12,
                "group": "执行规则",
                "question": "失效复盘是什么？",
                "answer": "每次动作后记录市场宽度、板块排名、模型信号、买卖价格、触发/失效原因，用于回测和规则迭代。",
                "status": "待落库",
            },
        ]
        solved = sum(1 for item in questions if item["status"] == "已定义")
        partial = sum(1 for item in questions if item["status"] == "部分定义")
        pending = len(questions) - solved - partial
        if market.mood in {"偏弱", "震荡"}:
            gate = "谨慎/观察"
            gate_reason = f"当前市场为{market.mood}，系统允许分析和减仓提示，强买入动作需要更高确认。"
        else:
            gate = "可筛选"
            gate_reason = f"当前市场为{market.mood}，可以筛选强板块与模型共振个股，但仍需止损条件。"
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "A股投资逻辑截图：交易系统12问，已转为内部策略审计清单",
            "score": round((solved * 1 + partial * 0.55) / len(questions) * 100),
            "solved": solved,
            "partial": partial,
            "pending": pending,
            "gate": gate,
            "gate_reason": gate_reason,
            "rule": "未回答清楚的问题不进入强动作；待回测/待落库项只影响观察权重，不单独触发买卖。",
            "questions": questions,
        }

    def chokepoint_atlas(self) -> dict:
        lanes = [
            {
                "name": "AI Factory 供电与液冷",
                "system": "大规模AI数据中心从芯片、机柜、供电、散热到交付的物理系统",
                "layers": ["电网/变压器", "UPS与配电", "服务器电源", "液冷CDU", "冷板/管路", "机柜交付"],
                "chokepoints": ["电力接入周期", "高功率机柜散热", "液冷良率和交付", "高密度PCB/连接器"],
                "verification": ["数据中心资本开支", "电力设备订单", "液冷产品收入", "客户认证和扩产公告"],
                "mapped_positions": [
                    {"name": "工业富联", "code": "601138.SH", "role": "AI服务器/整机交付", "benefit": "交付体系放量受益"},
                    {"name": "英维克", "code": "002837.SZ", "role": "液冷/温控", "benefit": "高功率机柜散热瓶颈"},
                    {"name": "沪电股份", "code": "002463.SZ", "role": "高速PCB", "benefit": "AI服务器和交换机PCB需求"},
                    {"name": "鹏鼎控股", "code": "002938.SZ", "role": "PCB/连接", "benefit": "高密度连接和板级交付"},
                    {"name": "生益科技", "code": "600183.SH", "role": "覆铜板材料", "benefit": "高速板材上游约束"},
                ],
                "score": 88,
                "status": "优先研究",
            },
            {
                "name": "人形机器人执行器链",
                "system": "从控制器、执行器、传感器、连接器到热管理的机器人运动系统",
                "layers": ["电机", "减速器", "丝杠", "力传感器", "连接器", "散热/供电"],
                "chokepoints": ["高可靠力控", "量产一致性", "传感器认证", "轻量化连接"],
                "verification": ["量产指引", "供应商认证", "良率变化", "单位价值量变化"],
                "mapped_positions": [
                    {"name": "新大陆", "code": "000997.SZ", "role": "数字化/识别设备", "benefit": "弱相关，更多偏应用侧"},
                ],
                "score": 62,
                "status": "观察研究",
            },
            {
                "name": "算力高速互连与材料",
                "system": "GPU/ASIC集群内的光模块、连接器、PCB、覆铜板、测试设备系统",
                "layers": ["光芯片", "InP/外延", "光模块", "交换机", "高速PCB", "覆铜板", "测试设备"],
                "chokepoints": ["高速材料损耗", "PCB层数和良率", "光模块交付", "测试产能"],
                "verification": ["800G/1.6T订单", "AI交换机出货", "高速覆铜板价格", "客户扩产"],
                "mapped_positions": [
                    {"name": "沪电股份", "code": "002463.SZ", "role": "高速PCB", "benefit": "AI交换机/服务器主板"},
                    {"name": "生益科技", "code": "600183.SH", "role": "高速覆铜板", "benefit": "材料端瓶颈"},
                    {"name": "鹏鼎控股", "code": "002938.SZ", "role": "高端PCB", "benefit": "板级连接需求"},
                ],
                "score": 84,
                "status": "优先研究",
            },
        ]
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "chokepoint-atlas framework, GitHub: qiuqiubuchongle-cloud/chokepoint-atlas",
            "principle": "不先问买哪只股票，先问真实系统如何运转、哪一层会卡住、证据能否交叉验证。",
            "lanes": lanes,
        }

    def breakthrough_review(self) -> dict:
        market = self.market_overview()
        self.refresh_quotes(self.watchlist_codes)
        rules = [
            "突破前高点时，成交量应明显放大，但不能极端透支。",
            "突破后的回踩不能跌破前期高点，前高应转为支撑。",
            "突破后的上涨组合应强于突破前的上涨组合，不能一突破就缩量衰竭。",
            "市场宽度不能明显收缩，否则突破成功率下降。",
        ]
        rows = []
        for code in self.watchlist_codes:
            stock = self.stocks.get(code)
            if not stock:
                continue
            volume_proxy = abs(stock.change_pct) * (stock.quantity or 100)
            score = 45
            evidence = []
            if stock.change_pct > 2:
                score += 18
                evidence.append("当日涨幅强于普通波动")
            if stock.change_pct > 5:
                score += 10
                evidence.append("涨幅较大，需要检查是否放量透支")
            if stock.pnl_pct is not None and stock.pnl_pct > -12:
                score += 10
                evidence.append("持仓亏损压力较小或已有修复")
            if market.mood in {"强修复", "修复"}:
                score += 8
                evidence.append(f"市场环境为{market.mood}")
            else:
                score -= 8
                evidence.append(f"市场环境为{market.mood}，突破需要降权")
            if volume_proxy > 1500:
                score += 6
                evidence.append("量能代理值放大")
            status = "健康突破观察" if score >= 72 else "普通波动" if score >= 55 else "突破无效/待确认"
            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "change_pct": stock.change_pct,
                    "score": max(0, min(100, round(score))),
                    "status": status,
                    "evidence": evidence,
                    "next_check": "等待回踩前高不破、放量不衰竭、板块强度保持",
                }
            )
        rows.sort(key=lambda item: item["score"], reverse=True)
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "截图突破逻辑：真突破需要量能、回踩、上涨组合和市场宽度共同确认",
            "rules": rules,
            "rows": rows,
        }

    def agent_debate(self) -> dict:
        market = self.market_overview()
        movers = self.market_movers()
        top_sector = self.sector_rankings()[0] if self.sector_rankings() else {}
        agents = [
            {
                "name": "市场分析师",
                "scope": "只看指数、宽度、成交额",
                "view": f"当前市场为{market.mood}，上涨{market.up_count}、下跌{market.down_count}，成交额约{market.turnover_billion:.2f}亿。",
                "verdict": "谨慎" if market.mood in {"偏弱", "震荡"} else "可筛选",
            },
            {
                "name": "板块分析师",
                "scope": "只看行业/主题强度",
                "view": f"当前强板块为{top_sector.get('name', '-')}，强度{top_sector.get('strength', '-')}，原因：{top_sector.get('reason', '-')}",
                "verdict": "追踪强板块",
            },
            {
                "name": "瓶颈研究员",
                "scope": "只看产业链卡点",
                "view": "AI Factory 的供电、液冷、高速PCB、覆铜板更像可验证瓶颈，优先绑定到持仓产业链。",
                "verdict": "建立研究优先级",
            },
            {
                "name": "多头辩手",
                "scope": "只找做多证据",
                "view": "若市场宽度修复且持仓位于产业瓶颈，盈利仓可继续跟踪，亏损仓等待模型修复。",
                "verdict": "条件做多",
            },
            {
                "name": "空头辩手",
                "scope": "只找风险证据",
                "view": "市场偏弱时，所有突破信号都要降权；主力净入榜不能单独作为买入理由。",
                "verdict": "防止假突破",
            },
            {
                "name": "风控经理",
                "scope": "只审查仓位和退出",
                "view": "亏损较深仓不加仓，盈利厚仓检查顶背离和板块退潮；动作必须有止损/失效条件。",
                "verdict": "先控风险",
            },
            {
                "name": "组合经理",
                "scope": "最终动作闸门",
                "view": "在12问未完全闭环前，系统允许观察、减仓、复盘，强买入需要市场/板块/个股/风控共振。",
                "verdict": "HOLD/WATCH优先",
            },
        ]
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "TradingAssistant / TradingAgents 多智能体分工思路",
            "principle": "分析师描述事实，辩手提出分歧，风控审查风险，组合经理才给动作。",
            "article_reference": "已粘贴文章：TradingAgents 多智能体股票研究框架",
            "integration_status": "已落地角色分工、动作队列、人工确认、交易日志；下一步补交易记忆复盘和按角色配置不同模型。",
            "layers": [
                {"layer": "分析师团", "roles": "基本面/技术面/情绪/新闻", "job": "只产出事实和证据，不直接给最终买卖"},
                {"layer": "研究员团", "roles": "多头研究员/空头研究员", "job": "围绕同一只股票做结构化正反辩论，暴露盲点"},
                {"layer": "交易员", "roles": "执行建议整合", "job": "把证据压缩成 BUY/HOLD/REDUCE/SELL、触发价和仓位"},
                {"layer": "风险委员会", "roles": "激进/中性/保守风控", "job": "从波动、流动性、回撤、持仓集中度审查动作"},
                {"layer": "组合经理", "roles": "最终拍板", "job": "批准、降级或拒绝交易建议，并写入交易日志"},
            ],
            "memory_plan": [
                "每次模拟执行/人工确认都写入交易日志，保存当时的行情、情绪、理由和失效价。",
                "复盘时自动标记：触发后收益、是否打到止损、AI理由是否成立。",
                "同一只股票下次分析时读取历史记录，形成反思提示，避免重复犯错。",
            ],
            "top_gainers": movers.get("top_gainers", [])[:5],
            "agents": agents,
        }

    def trading_action_queue(self) -> dict:
        market = self.market_overview()
        audit = self.trading_system_audit()
        emotion = self.market_emotion_volume()
        self.refresh_quotes(self.watchlist_codes)
        breakthrough_rows = {item["code"]: item for item in self.breakthrough_review().get("rows", [])}
        chokepoint_scores: dict[str, dict] = {}
        for lane in self.chokepoint_atlas().get("lanes", []):
            for position in lane.get("mapped_positions", []):
                code = position.get("code")
                if not code:
                    continue
                current = chokepoint_scores.get(code, {"score": 0, "lanes": [], "roles": []})
                current["score"] = max(current["score"], lane.get("score", 0))
                current["lanes"].append(lane.get("name", ""))
                current["roles"].append(position.get("role", ""))
                chokepoint_scores[code] = current

        cautious_market = (
            market.mood in {"偏弱", "震荡"}
            or "谨慎" in str(audit.get("gate", ""))
            or emotion.get("risk_mode") in {"risk_off", "defensive"}
        )
        overheated_market = emotion.get("risk_mode") == "protect_profit"
        rows = []
        for code in self.watchlist_codes:
            stock = self.stocks.get(code)
            if not stock:
                continue
            # 盈亏按实时价重算：旧逻辑只在快照为空时才算，导致 price 已更新而盈亏停在旧值
            pnl_pct = stock.pnl_pct
            if stock.cost > 0:
                pnl_pct = (stock.price - stock.cost) / stock.cost * 100
            pnl_pct = pnl_pct or 0
            pnl_amount = stock.pnl_amount
            if stock.cost > 0 and stock.quantity:
                pnl_amount = (stock.price - stock.cost) * stock.quantity
            prev_close = stock.price / (1 + stock.change_pct / 100) if stock.change_pct > -99 else stock.price
            daily_pnl = (stock.price - prev_close) * stock.quantity if stock.quantity else 0
            breakthrough = breakthrough_rows.get(code, {})
            breakthrough_score = int(breakthrough.get("score", 50))
            chokepoint = chokepoint_scores.get(code, {"score": 0, "lanes": [], "roles": []})
            chokepoint_score = int(chokepoint.get("score", 0))
            evidence = []
            if breakthrough:
                evidence.append(f"突破复核 {breakthrough_score}：{breakthrough.get('status', '-')}")
            if chokepoint_score:
                evidence.append(f"产业瓶颈 {chokepoint_score}：{' / '.join(chokepoint.get('roles', [])[:2])}")
            evidence.append(f"市场闸门：{audit.get('gate', '-')}")
            evidence.append(f"情绪量能：{emotion.get('state')} {emotion.get('composite_score')}/100，{emotion.get('volume_state')}")
            evidence.append(f"持仓盈亏：{pnl_pct:.2f}%")

            action = "HOLD"
            label = "继续观察"
            priority = 50
            position_advice = "维持原仓，等待模型进一步确认"
            reason = "没有出现足够明确的加仓或退出信号"
            trigger_price = round(max(prev_close, stock.price) * 1.015, 2)
            invalidation = round(min(prev_close, stock.price) * 0.975, 2)
            max_position_pct = 12

            if stock.quantity <= 0:
                action = "WATCH"
                label = "仅纳入候选"
                priority = 35
                position_advice = "未持仓，只记录候选；市场闸门打开后再看入场"
                reason = "当前不是实际持仓，先进入候选观察池"
            elif stock.cost < 0 or pnl_amount > 10000:
                action = "PROTECT"
                label = "盈利保护"
                priority = 82
                position_advice = "不追高加仓；用5日线/前一日低点做移动保护"
                reason = "利润垫较厚，核心任务从进攻转为守住收益"
                trigger_price = round(stock.price * 1.03, 2)
                invalidation = round(stock.price * 0.96, 2)
                max_position_pct = 16
            elif overheated_market and stock.change_pct > 3:
                action = "PROTECT"
                label = "亢奋保护"
                priority = 86
                position_advice = "市场情绪偏热，不追高；盈利或反弹仓改用移动止盈"
                reason = "情绪亢奋阶段容易冲高回落，优先保护收益和避免追涨"
                trigger_price = round(stock.price * 1.02, 2)
                invalidation = round(stock.price * 0.965, 2)
                max_position_pct = 12
            elif pnl_pct <= -25 and cautious_market:
                action = "REDUCE_RISK"
                label = "减仓风控"
                priority = 90
                position_advice = "弱市深亏仓优先降风险，等待20日线修复再评估"
                reason = "亏损较深且市场闸门偏谨慎，不允许盲目补仓"
                trigger_price = round(stock.price * 1.02, 2)
                invalidation = round(stock.price * 0.97, 2)
                max_position_pct = 8
            elif stock.change_pct <= -4 and pnl_pct < -15:
                action = "STOP_REVIEW"
                label = "止损复核"
                priority = 88
                position_advice = "盘中不急杀；收盘仍弱于板块则列入退出复盘"
                reason = "当日跌幅较大且处于亏损仓，先检查是否破位或假跌"
                trigger_price = round(stock.price * 1.025, 2)
                invalidation = round(stock.price * 0.965, 2)
                max_position_pct = 7
            elif not cautious_market and not overheated_market and breakthrough_score >= 72 and chokepoint_score >= 80:
                action = "ADD_ON_PULLBACK"
                label = "回踩加仓候选"
                priority = 84
                position_advice = "只在回踩不破支撑且量能不衰时小幅加仓"
                reason = "市场闸门允许，且个股同时具备突破复核和产业瓶颈证据"
                trigger_price = round(stock.price * 0.99, 2)
                invalidation = round(stock.price * 0.955, 2)
                max_position_pct = 14
            elif breakthrough_score >= 70 or chokepoint_score >= 82:
                action = "HOLD_CONFIRM"
                label = "持有确认"
                priority = 68
                position_advice = "持仓不动，等突破回踩或板块资金确认"
                reason = "存在产业或形态证据，但市场/价格条件还没有完全共振"
                max_position_pct = 12

            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "price": round(stock.price, 3),
                    "change_pct": round(stock.change_pct, 2),
                    "quantity": stock.quantity,
                    "cost": stock.cost,
                    "market_value": round(stock.price * stock.quantity, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_amount": round(pnl_amount, 2),
                    "daily_pnl": round(daily_pnl, 2),
                    "action": action,
                    "label": label,
                    "priority": priority,
                    "trigger_price": trigger_price,
                    "invalidation_price": invalidation,
                    "max_position_pct": max_position_pct,
                    "position_advice": position_advice,
                    "reason": reason,
                    "evidence": evidence,
                    "next_step": "人工确认后记录到交易日志；未触发价格不执行",
                    "data_source": stock.source,
                }
            )

        rows.sort(key=lambda item: item["priority"], reverse=True)
        action_counts: dict[str, int] = {}
        for item in rows:
            action_counts[item["action"]] = action_counts.get(item["action"], 0) + 1
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "decision_queue_not_auto_order",
            "principle": "先做动作队列和人工确认，不自动下单；每个动作必须同时有市场、个股、仓位和失效条件。",
            "gate": audit.get("gate"),
            "gate_reason": audit.get("gate_reason"),
            "market": {
                "mood": market.mood,
                "up_count": market.up_count,
                "down_count": market.down_count,
                "turnover_billion": market.turnover_billion,
            },
            "emotion_volume": emotion,
            "summary": action_counts,
            "actions": rows,
        }

    def get_watchlist(self) -> list[Stock]:
        self.refresh_quotes(self.watchlist_codes)
        return [self.stocks[code] for code in self.watchlist_codes if code in self.stocks]

    def user_state_path(self, user: dict) -> Path:
        users_dir = self.data_dir / "users"
        users_dir.mkdir(exist_ok=True)
        return users_dir / f"user_{user['id']}.json"

    def default_user_state(self, user: dict) -> dict:
        if user.get("username") == "laoma":
            positions = {}
            for code in self.watchlist_codes:
                stock = self.stocks.get(code)
                if not stock:
                    continue
                positions[code] = {
                    "cost": stock.cost,
                    "quantity": stock.quantity,
                    "alert_pct": stock.alert_pct,
                    "alert_price": stock.alert_price,
                    "sort_order": stock.sort_order,
                    "open_price_target": stock.open_price_target,
                    "take_profit": stock.take_profit,
                    "stop_loss": stock.stop_loss,
                }
            return {"watchlist_codes": list(self.watchlist_codes), "positions": positions, "manual_cash_available": None, "trade_cooldowns": {}}
        return {"watchlist_codes": [], "positions": {}, "manual_cash_available": None, "trade_cooldowns": {}}

    def read_user_state(self, user: dict) -> dict:
        path = self.user_state_path(user)
        state = self.persistence.get_user_state(int(user["id"]))
        if state is None and path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                self.persistence.save_user_state(int(user["id"]), state)
            except Exception:
                state = None
        if state is None:
            state = self.default_user_state(user)
            self.write_user_state(user, state)
        state.setdefault("watchlist_codes", [])
        state.setdefault("positions", {})
        state.setdefault("manual_cash_available", None)
        state.setdefault("trade_cooldowns", {})
        state["owner_username"] = user.get("username", "")
        return state

    def write_user_state(self, user: dict, state: dict) -> None:
        self.persistence.save_user_state(int(user["id"]), state)

    def stock_for_user(self, code: str, state: dict) -> Stock | None:
        normalized = self.normalize_code(code)
        if normalized not in self.stocks:
            self.placeholder_stock(normalized)
        stock = self.stocks.get(normalized)
        if not stock:
            return None
        item = deepcopy(stock)
        self.apply_stock_profile(item)
        item.cost = 0
        item.quantity = 0
        item.pnl_amount = None
        item.pnl_pct = None
        item.sort_order = 0
        item.open_price_target = 0
        item.take_profit = 0
        item.stop_loss = 0
        position = state.get("positions", {}).get(normalized, {})
        for field in ("cost", "quantity", "alert_pct", "alert_price", "sort_order", "open_price_target", "take_profit", "stop_loss"):
            if field in position:
                setattr(item, field, position[field])
        if state.get("owner_username") != "laoma":
            item.ai = f"Member watch item. Track {item.tag} with price, volume, fund-flow and model signals."
        return item

    def get_user_watchlist(self, user: dict) -> list[Stock]:
        state = self.read_user_state(user)
        codes = [self.normalize_code(code) for code in state.get("watchlist_codes", [])]
        for code in codes:
            if code not in self.stocks:
                self.placeholder_stock(code)
        self.refresh_quotes(codes)
        rows = [self.stock_for_user(code, state) for code in codes]
        return [row for row in rows if row]

    def add_user_watchlist(self, user: dict, code: str) -> list[Stock]:
        normalized = self.normalize_code(code)
        if normalized not in self.stocks:
            self.placeholder_stock(normalized)
        state = self.read_user_state(user)
        codes = [self.normalize_code(item) for item in state.get("watchlist_codes", [])]
        if normalized not in codes:
            codes.insert(0, normalized)
        state["watchlist_codes"] = codes
        state.setdefault("positions", {})
        state["positions"].setdefault(normalized, {"cost": 0, "quantity": 0, "alert_pct": 3, "alert_price": 0, "sort_order": 0, "open_price_target": 0, "take_profit": 0, "stop_loss": 0})
        self.write_user_state(user, state)
        return [self.stock_for_user(normalized, state)] if normalized in self.stocks else []

    def remove_user_watchlist(self, user: dict, code: str) -> list[Stock]:
        normalized = self.normalize_code(code)
        state = self.read_user_state(user)
        state["watchlist_codes"] = [item for item in state.get("watchlist_codes", []) if self.normalize_code(item) != normalized]
        state.get("positions", {}).pop(normalized, None)
        self.write_user_state(user, state)
        return self.get_user_watchlist(user)

    def update_user_position(self, user: dict, payload: dict) -> dict:
        normalized = self.normalize_code(str(payload.get("code", "")))
        if normalized not in self.stocks:
            self.fetch_stock_by_code(normalized)
        if normalized not in self.stocks:
            return {"error": "stock_not_found", "code": normalized}
        state = self.read_user_state(user)
        codes = [self.normalize_code(item) for item in state.get("watchlist_codes", [])]
        if normalized not in codes:
            codes.insert(0, normalized)
        state["watchlist_codes"] = codes
        state.setdefault("positions", {})
        state["positions"][normalized] = {
            "cost": float(payload.get("cost") or 0),
            "quantity": int(float(payload.get("quantity") or 0)),
            "alert_pct": float(payload.get("alert_pct") or 3),
            "alert_price": float(payload.get("alert_price") or 0),
            "sort_order": int(float(payload.get("sort_order") or 0)),
            "open_price_target": float(payload.get("open_price_target") or 0),
            "take_profit": float(payload.get("take_profit") or 0),
            "stop_loss": float(payload.get("stop_loss") or 0),
        }
        self.write_user_state(user, state)
        return {"ok": True, "stock": self.stock_for_user(normalized, state).model_dump()}

    def update_user_manual_cash(self, user: dict, cash_available: float) -> dict:
        state = self.read_user_state(user)
        state["manual_cash_available"] = round(float(cash_available or 0), 2)
        self.write_user_state(user, state)
        return {
            "ok": True,
            "cash_available": state["manual_cash_available"],
            "cash_source": "manual_input",
        }

    def update_manual_cash_available(self, user: dict, cash_available: float) -> dict:
        return self.update_user_manual_cash(user, cash_available)

    def current_cash_available(self, user: dict) -> float:
        state = self.read_user_state(user)
        manual_cash = state.get("manual_cash_available")
        if manual_cash is not None:
            return float(manual_cash or 0)
        if user.get("username") == "laoma":
            return float(self.account_snapshot.get("cash_available") or 0)
        return 0.0

    def _prune_trade_cooldowns(self, state: dict) -> None:
        now = datetime.now()
        cooldowns = state.setdefault("trade_cooldowns", {})
        expired = []
        for code, item in cooldowns.items():
            try:
                expires_at = datetime.fromisoformat(str(item.get("expires_at", "")))
            except Exception:
                expired.append(code)
                continue
            if expires_at <= now:
                expired.append(code)
        for code in expired:
            cooldowns.pop(code, None)

    def start_trade_cooldown(self, user: dict, code: str, reason: str, minutes: int = 5) -> dict:
        normalized = self.normalize_code(code)
        minutes = max(1, min(int(minutes or 5), 60))
        state = self.read_user_state(user)
        self._prune_trade_cooldowns(state)
        expires_at = datetime.now() + timedelta(minutes=minutes)
        item = {
            "code": normalized,
            "reason": reason or "情绪波动，先冷静再确认",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "expires_at": expires_at.isoformat(timespec="seconds"),
            "minutes": minutes,
        }
        state.setdefault("trade_cooldowns", {})[normalized] = item
        self.write_user_state(user, state)
        item["remaining_seconds"] = max(0, int((expires_at - datetime.now()).total_seconds()))
        item["active"] = True
        return item

    def trade_cooldown_status(self, user: dict, code: str = "") -> dict:
        state = self.read_user_state(user)
        self._prune_trade_cooldowns(state)
        if code:
            normalized = self.normalize_code(code)
            item = state.get("trade_cooldowns", {}).get(normalized)
            if not item:
                self.write_user_state(user, state)
                return {"active": False, "code": normalized, "remaining_seconds": 0}
            expires_at = datetime.fromisoformat(item["expires_at"])
            remaining = max(0, int((expires_at - datetime.now()).total_seconds()))
            result = dict(item)
            result.update({"active": remaining > 0, "remaining_seconds": remaining})
            self.write_user_state(user, state)
            return result
        rows = []
        for item in state.get("trade_cooldowns", {}).values():
            expires_at = datetime.fromisoformat(item["expires_at"])
            rows.append({**item, "active": True, "remaining_seconds": max(0, int((expires_at - datetime.now()).total_seconds()))})
        self.write_user_state(user, state)
        return {"active": bool(rows), "items": rows}

    def stock_compliance_gate(self, payload: dict) -> dict:
        name = str(payload.get("name") or "")
        code = self.normalize_code(str(payload.get("code") or ""))
        market_cap = float(payload.get("market_cap") or payload.get("market_value") or 0)
        turnover_rate = float(payload.get("turnover_rate") or 0)
        amount = float(payload.get("amount") or payload.get("turnover_amount") or 0)
        pe_ttm = float(payload.get("pe_ttm") or payload.get("pe") or 0)
        hard_blocks: list[str] = []
        warnings: list[str] = []
        checks = []
        if "ST" in name.upper() or "退" in name:
            hard_blocks.append("ST/退市风险")
        if market_cap and market_cap < 5_000_000_000:
            warnings.append("市值偏小，容易被情绪资金放大波动")
        if (amount and amount < 100_000_000) or (turnover_rate and turnover_rate < 1):
            warnings.append("流动性不足")
        if pe_ttm <= 0:
            warnings.append("业绩/估值需核实")
        checks.append({"name": "退市/ST过滤", "passed": "ST/退市风险" not in hard_blocks})
        checks.append({"name": "流动性过滤", "passed": "流动性不足" not in warnings})
        checks.append({"name": "基本面异常提醒", "passed": pe_ttm > 0})
        return {
            "code": code,
            "name": name or code,
            "passed": not hard_blocks,
            "hard_blocks": hard_blocks,
            "warnings": warnings,
            "checks": checks,
            "policy": "先过硬门槛，再看资金趋势和AI判断；硬阻断不允许进入自动执行队列。",
        }

    def order_compliance_check(self, user: dict, payload: dict) -> dict:
        code = self.normalize_code(str(payload.get("code") or ""))
        side = str(payload.get("side") or "BUY").upper()
        price = float(payload.get("price") or 0)
        quantity = int(float(payload.get("quantity") or 0))
        cash_available = self.current_cash_available(user)
        estimated_amount = round(max(price, 0) * max(quantity, 0), 2)
        violations: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []
        if quantity <= 0:
            violations.append("数量必须大于0")
        if quantity > 0 and quantity % 100 != 0:
            adjusted = max(100, (quantity // 100) * 100)
            violations.append("非100股整数倍")
            suggestions.append(f"建议拆单/调整为 {adjusted} 股整数手后再确认")
        if price <= 0:
            violations.append("价格必须大于0")
        if side == "BUY" and estimated_amount > cash_available:
            violations.append("超过可用资金")
            affordable = int(cash_available // max(price, 0.01) // 100 * 100)
            suggestions.append(f"可用资金约 {cash_available:.2f}，建议买入不超过 {max(0, affordable)} 股")
        cooldown = self.trade_cooldown_status(user, code) if code else {"active": False, "remaining_seconds": 0}
        if cooldown.get("active"):
            violations.append("冷静期未结束")
            suggestions.append(f"剩余 {cooldown.get('remaining_seconds', 0)} 秒，结束后重新检查")
        state = self.read_user_state(user)
        stock = self.stock_for_user(code, state) if code else None
        gate_payload = {
            "code": code,
            "name": stock.name if stock else code,
            "turnover_rate": getattr(stock, "turnover_rate", 0) if stock else 0,
            "amount": getattr(stock, "amount", 0) if stock else 0,
            "pe_ttm": getattr(stock, "pe_ttm", 0) if stock else 0,
        }
        gate = self.stock_compliance_gate(gate_payload)
        unified_gate = self.unified_trading_gate()
        self.record_unified_gate_event(user, unified_gate, context="precheck", code=code, side=side)
        if side == "BUY" and not unified_gate.get("allowed"):
            violations.append("统一交易闸门已暂停新增买入")
            suggestions.extend(unified_gate.get("reasons") or [])
        if gate.get("hard_blocks"):
            violations.extend(gate["hard_blocks"])
        warnings.extend(gate.get("warnings") or [])
        if not suggestions and not violations:
            suggestions.append("通过预检：仍需人工确认，不自动实盘下单")
        return {
            "ok": True,
            "allowed": not violations,
            "code": code,
            "side": side,
            "price": price,
            "quantity": quantity,
            "estimated_amount": estimated_amount,
            "cash_available": round(cash_available, 2),
            "violations": violations,
            "warnings": warnings,
            "suggestions": suggestions,
            "cooldown": cooldown,
            "stock_gate": gate,
            "unified_gate": unified_gate,
            "execution_mode": "manual_confirm_only",
            "real_order_enabled": False,
            "message": "当前只生成确认清单；接入券商账号前，实盘自动操作保持关闭。",
        }

    def unified_trading_gate(self) -> dict:
        return calculate_unified_gate(
            quality=self.data_quality(),
            emotion=self.market_emotion_volume(),
            quant_window=self.quant_control_radar().get("current_window", {}),
        )

    def record_unified_gate_event(self, user: dict, gate: dict, context: str = "precheck", code: str = "", side: str = "") -> dict:
        state = self.read_user_state(user)
        event = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "context": context,
            "code": code,
            "side": side,
            "allowed": bool(gate.get("allowed")),
            "status": gate.get("status", "unknown"),
            "action_cap": gate.get("action_cap", "observe_only"),
            "reasons": list(gate.get("reasons") or []),
        }
        rows = [event, *(state.get("unified_gate_history") or [])]
        state["unified_gate_history"] = rows[:200]
        self.write_user_state(user, state)
        return event

    def unified_gate_history(self, user: dict, limit: int = 50) -> list[dict]:
        state = self.read_user_state(user)
        return list(state.get("unified_gate_history") or [])[: max(1, min(int(limit or 50), 200))]

    def user_trade_log_path(self, user: dict) -> Path:
        logs_dir = self.data_dir / "users"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir / f"user_{user['id']}_trade_log.json"

    def user_daily_review_path(self, user: dict) -> Path:
        logs_dir = self.data_dir / "users"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir / f"user_{user['id']}_daily_reviews.json"

    def read_user_daily_reviews(self, user: dict) -> list[dict]:
        path = self.user_daily_review_path(user)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def write_user_daily_reviews(self, user: dict, rows: list[dict]) -> None:
        self.user_daily_review_path(user).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_user_daily_reviews(self, user: dict, limit: int = 20) -> list[dict]:
        return self.read_user_daily_reviews(user)[: max(1, min(int(limit or 20), 100))]

    def save_user_daily_review(self, user: dict, payload: dict | None = None) -> str:
        bundle = payload or self.user_daily_review(user)
        entry = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "review_date": bundle.get("review_date") or datetime.now().date().isoformat(),
            "title": bundle.get("title") or f"{datetime.now().date().isoformat()} 复盘",
            "summary": bundle.get("summary") or bundle.get("market_review", {}).get("headline") or "",
            "payload": bundle,
        }
        rows = self.read_user_daily_reviews(user)
        rows.insert(0, entry)
        self.write_user_daily_reviews(user, rows[:120])
        return entry["id"]

    def read_user_trade_log(self, user: dict) -> list[dict]:
        path = self.user_trade_log_path(user)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def write_user_trade_log(self, user: dict, rows: list[dict]) -> None:
        self.user_trade_log_path(user).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def user_hidden_fund_proxy(self, user: dict) -> dict:
        codes = {stock.code for stock in self.get_user_watchlist(user)}
        data = self.hidden_fund_proxy()
        data["rows"] = [row for row in data.get("rows", []) if row.get("code") in codes]
        data["scope"] = "current_user_watchlist"
        return data

    def user_breakthrough_review(self, user: dict) -> dict:
        codes = {stock.code for stock in self.get_user_watchlist(user)}
        data = self.breakthrough_review()
        data["rows"] = [row for row in data.get("rows", []) if row.get("code") in codes]
        data["scope"] = "current_user_watchlist"
        return data

    def user_strategy_scan(self, user: dict) -> dict:
        codes = {stock.code for stock in self.get_user_watchlist(user)}
        data = self.strategy_scan()
        data["rows"] = [row for row in data.get("rows", []) if row.get("code") in codes]
        data["scope"] = "current_user_watchlist"
        return data

    def user_serenity_framework(self, user: dict) -> dict:
        codes = {stock.code for stock in self.get_user_watchlist(user)}
        data = self.serenity_framework()
        data["rows"] = [row for row in data.get("rows", []) if row.get("code") in codes]
        data["scope"] = "current_user_watchlist"
        return data

    def user_next_day_plan(
        self,
        user: dict,
        *,
        market: MarketOverview | None = None,
        emotion: dict | None = None,
        breadth: dict | None = None,
        sectors: list[dict] | None = None,
        queue: dict | None = None,
        recommendations: dict | None = None,
        event_rows: list[dict] | None = None,
        watch_rows: list[dict] | None = None,
        intelligence_announcements: list[dict] | None = None,
        intelligence_research: list[dict] | None = None,
    ) -> dict:
        market = market or self.market_overview()
        emotion = emotion or self.market_emotion_volume()
        breadth = breadth or self.market_breadth()
        sectors = sectors or self.sector_rankings()[:5]
        queue = queue or self.user_trading_action_queue(user)
        recommendations = recommendations or self.ai_stock_recommendations(limit=10)
        event_rows = event_rows or self.events()
        watch_rows = watch_rows or []
        intelligence_announcements = intelligence_announcements or []
        intelligence_research = intelligence_research or []
        quant_radar = self.quant_control_radar()

        breadth_signal = str(breadth.get("signal", ""))
        breadth_bonus = {"宽度扩张": 10, "宽度修复": 6, "宽度中性": 0, "宽度收缩": -8}.get(breadth_signal, 0)
        sector_strength = sum(float(item.get("strength", 0) or 0) for item in sectors[:3]) / max(1, min(len(sectors[:3]), 3))
        quant_penalty = max(0, (int(quant_radar.get("risk_score", 0) or 0) - 55) * 0.18)
        forecast_score = max(0, min(100, round(float(emotion.get("composite_score", 50) or 50) + breadth_bonus + min(8, sector_strength * 0.08) - quant_penalty)))

        if forecast_score >= 72:
            stage = "积极择强"
            stance = "允许围绕主线做确认后的主动进攻，但不追高。"
            color = "green"
        elif forecast_score >= 58:
            stage = "结构试错"
            stance = "可以小仓位围绕板块核心做结构性试错，优先低吸和回踩确认。"
            color = "amber"
        elif forecast_score >= 45:
            stage = "谨慎观察"
            stance = "更适合看板块承接和个股强弱分化，少做临盘冲动交易。"
            color = "amber"
        else:
            stage = "防守优先"
            stance = "先守仓位和纪律，重点是避开高波动和尾盘情绪踩踏。"
            color = "red"

        market_gate = recommendations.get("market_gate", {}) if isinstance(recommendations, dict) else {}
        gate_note = market_gate.get("advice") or emotion.get("gate") or ""
        focus_sectors = [
            {
                "name": item.get("name"),
                "change_pct": round(float(item.get("change_pct", 0) or 0), 2),
                "strength": int(item.get("strength", 0) or 0),
                "reason": item.get("reason") or "跟踪板块强度、量能与资金承接。",
            }
            for item in sectors[:4]
        ]

        queue_rows = queue.get("actions", []) if isinstance(queue, dict) else []
        watch_actions = []
        for item in queue_rows[:5]:
            watch_actions.append(
                {
                    "name": item.get("name"),
                    "code": item.get("code"),
                    "action": item.get("label") or item.get("action") or "观察",
                    "priority": int(item.get("priority", 0) or 0),
                    "trigger_price": item.get("trigger_price") or item.get("price") or "-",
                    "support": item.get("support") or item.get("invalidation_price") or "-",
                    "reason": item.get("reason") or "等待更清晰的板块与资金确认。",
                    "evidence": (item.get("evidence") or [])[:3],
                }
            )

        candidate_actions = []
        for item in (recommendations.get("items", []) if isinstance(recommendations, dict) else [])[:5]:
            candidate_actions.append(
                {
                    "name": item.get("name"),
                    "code": item.get("code"),
                    "score": int(item.get("score", 0) or 0),
                    "action": item.get("action") or "TRACK",
                    "amount": round(float(item.get("amount", 0) or 0), 2),
                    "main_net": round(float(item.get("main_net", 0) or 0), 2),
                    "evidence": (item.get("evidence") or [])[:3],
                }
            )

        catalysts = []
        for item in intelligence_announcements[:3]:
            catalysts.append({"type": "公告", "name": item.get("name") or item.get("code"), "date": item.get("date"), "title": item.get("title"), "impact": "明早先确认是否属于实质催化、是否被市场兑现。"})
        for item in intelligence_research[:3]:
            catalysts.append({"type": "研报", "name": item.get("name") or item.get("code"), "date": item.get("date"), "title": item.get("title"), "impact": f"结合 {item.get('institution') or '机构'} 观点验证盈利预期和市场拥挤度。"})
        for item in event_rows[:4]:
            catalysts.append({"type": item.get("type") or "事件", "name": "市场事件", "date": item.get("time"), "title": item.get("title"), "impact": item.get("impact") or "需要在开盘前确认是否影响主线风险偏好。"})

        forbidden_actions = [
            "9:30-10:00 不追高，不把集合竞价情绪当成全天结论。",
            "14:00-14:30 警惕量化再平衡和尾盘砸盘，不在急拉时冲动加仓。",
            "14:57 之后不参与不可撤单的集合竞价窗口。",
        ]
        if forecast_score < 58:
            forbidden_actions.append("弱修复或震荡环境下，不对单日大涨股做情绪化接力。")
        if forecast_score < 45:
            forbidden_actions.append("防守环境下，优先保留现金和机动仓位，不做逆势重仓抄底。")

        prep_checklist = [
            "开盘前先看隔夜外盘和科技指数方向，只做环境校准，不直接替代个股逻辑。",
            "先确认主线板块是否有量能和承接，再决定是否放大操作频率。",
            "对自选股逐只核对支撑位、减仓位、止损位和触发条件。",
            "公告、研报、龙虎榜、资金流只作为证据层，最终动作仍由仓位和纪律控制。",
        ]
        if gate_note:
            prep_checklist.append(f"市场闸门提示：{gate_note}")

        intraday_windows = [
            {"time": "09:15-09:25", "title": "集合竞价观察", "action": "只看强弱和量能，不抢第一笔。"},
            {"time": "09:30-10:30", "title": "早盘量化洗盘", "action": "等第一波情绪释放，急跌优先放进候选而不是立刻重仓。"},
            {"time": "11:00-11:30", "title": "上午确认窗口", "action": "板块和个股都稳住后，再考虑小仓位确认。"},
            {"time": "14:00-14:30", "title": "尾盘再平衡预警", "action": "重点盯量化资金、主线退潮和尾盘跳水风险。"},
            {"time": "14:30-14:57", "title": "错杀与承接", "action": "急跌先分辨是真走弱还是量化错杀，确认承接后再分批。"},
        ]

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "score": forecast_score,
            "stage": stage,
            "color": color,
            "stance": stance,
            "headline": f"明日预判：{stage}，评分 {forecast_score}/100。",
            "market_bias": {
                "emotion_score": int(emotion.get("composite_score", 0) or 0),
                "breadth_signal": breadth_signal or "待确认",
                "quant_risk_score": int(quant_radar.get("risk_score", 0) or 0),
                "turnover_billion": round(float(market.turnover_billion or 0), 1),
                "gate": market_gate.get("state") or emotion.get("state") or stage,
            },
            "focus_sectors": focus_sectors,
            "watch_actions": watch_actions,
            "candidate_actions": candidate_actions,
            "catalysts": catalysts[:8],
            "forbidden_actions": forbidden_actions,
            "prep_checklist": prep_checklist,
            "intraday_windows": intraday_windows,
            "global_linkage": quant_radar.get("global_linkage", {}),
            "automation": quant_radar.get("automation_policy", {}),
        }

    def user_daily_review(self, user: dict) -> dict:
        # 复盘会串联行情、宽度、情绪、资金和公告/研报多个数据源。
        # 同一用户短时间重复打开页面时复用 60 秒结果，避免上游限流把页面拖成永久加载。
        review_cache = getattr(self, "_daily_review_cache", None)
        if review_cache is None:
            review_cache = self._daily_review_cache = {}
        cache_key = (str(user.get("id") or user.get("username") or "anonymous"), datetime.now().date().isoformat())
        cached = review_cache.get(cache_key)
        if cached and (datetime.now() - cached["at"]).total_seconds() < 60:
            return cached["payload"]
        market = self.market_overview()
        emotion = self.market_emotion_volume()
        breadth = self.market_breadth()
        sectors = self.sector_rankings()[:5]
        queue = self.user_trading_action_queue(user)
        queue_map = {item["code"]: item for item in queue.get("actions", [])}
        recommendations = self.ai_stock_recommendations(limit=10)
        event_rows = self.events()
        trade_rows = self.read_user_trade_log(user)[:8]
        watchlist_items = [build_watchlist_item(stock, market) for stock in self.get_user_watchlist(user)]
        watch_rows = []
        for item in watchlist_items[:12]:
            stock = item.stock
            action_row = queue_map.get(stock.code, {})
            support = stock.stop_loss or round(stock.price * 0.97, 2)
            resistance = stock.take_profit or round(stock.price * 1.05, 2)
            watch_rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "price": round(stock.price, 3),
                    "change_pct": round(stock.change_pct, 2),
                    "position": item.quantity,
                    "action": action_row.get("label", "盯盘观察"),
                    "priority": action_row.get("priority", 40),
                    "support": support,
                    "resistance": resistance,
                    "stop_loss": stock.stop_loss or support,
                    "take_profit": stock.take_profit or resistance,
                    "pnl_pct": item.pnl_pct,
                    "daily_pnl_pct": item.daily_pnl_pct,
                    "ai_summary": stock.ai,
                    "source": stock.source,
                    "recent_action": action_row.get("action", "WATCH"),
                }
            )
        watch_rows.sort(key=lambda row: (-int(row.get("priority") or 0), row["code"]))
        risk_lines = [f"{item['name']} {item['label']}" for item in queue.get("actions", [])[:3]]
        focus_lines = [f"{item.get('name')} {item.get('change_pct', 0):+.2f}%" for item in sectors[:3]]
        history = self.list_user_daily_reviews(user, limit=12)
        intelligence_announcements = []
        intelligence_research = []
        for row in watch_rows[:3]:
            announcement_rows = (self.stock_announcements(row["code"], 3).get("items") or [])[:2]
            research_rows = (self.stock_research_reports(row["code"], 3).get("items") or [])[:2]
            intelligence_announcements.extend(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "date": item.get("date", ""),
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                }
                for item in announcement_rows
                if item.get("title")
            )
            intelligence_research.extend(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "date": item.get("date", ""),
                    "title": item.get("title", ""),
                    "institution": item.get("institution", ""),
                    "rating": item.get("rating", ""),
                    "source": item.get("source", ""),
                }
                for item in research_rows
                if item.get("title")
            )
        if not intelligence_announcements and watch_rows:
            intelligence_announcements = [
                {
                    "code": row["code"],
                    "name": row["name"],
                    "date": datetime.now().date().isoformat(),
                    "title": f"待补充：{row['name']} 近期公告与互动平台动态",
                    "source": "review-fallback",
                }
                for row in watch_rows[:3]
            ]
        if not intelligence_research and watch_rows:
            intelligence_research = [
                {
                    "code": row["code"],
                    "name": row["name"],
                    "date": datetime.now().date().isoformat(),
                    "title": f"待补充：{row['name']} 最新盈利预期与机构观点",
                    "institution": "系统待抓取",
                    "rating": "跟踪中",
                    "source": "review-fallback",
                }
                for row in watch_rows[:3]
            ]
        intelligence_by_stock = []
        for row in watch_rows[:3]:
            announcement_items = [item for item in intelligence_announcements if item.get("code") == row["code"]]
            research_items = [item for item in intelligence_research if item.get("code") == row["code"]]
            latest_dates = [item.get("date", "") for item in [*announcement_items, *research_items] if item.get("date")]
            intelligence_by_stock.append(
                {
                    "code": row["code"],
                    "name": row["name"],
                    "announcement_count": len(announcement_items),
                    "research_count": len(research_items),
                    "latest_date": max(latest_dates) if latest_dates else "",
                    "announcements": announcement_items,
                    "research_reports": research_items,
                }
            )
        history_summary = {
            "trade_logs": [
                {
                    "created_at": row.get("created_at"),
                    "name": row.get("name"),
                    "code": row.get("code"),
                    "label": row.get("label"),
                    "status": row.get("status"),
                }
                for row in trade_rows
            ],
            "saved_reviews": [
                {
                    "id": row.get("id"),
                    "created_at": row.get("created_at"),
                    "title": row.get("title"),
                    "summary": row.get("summary"),
                }
                for row in history[:4]
            ],
        }
        key_signals = [
            {"label": "市场情绪", "value": emotion.get("composite_score"), "note": emotion.get("state"), "tone": "green" if (emotion.get("composite_score") or 0) >= 66 else "amber" if (emotion.get("composite_score") or 0) >= 48 else "red"},
            {"label": "宽度信号", "value": breadth.get("signal"), "note": breadth.get("advice"), "tone": "green" if breadth.get("signal") == "宽度扩张" else "amber" if breadth.get("signal") == "宽度中性" else "red"},
            {"label": "两市成交额", "value": round(market.turnover_billion, 1), "note": emotion.get("volume_state"), "tone": "green" if market.turnover_billion >= 15000 else "amber" if market.turnover_billion >= 10000 else "red"},
            {"label": "观察池强度", "value": len(recommendations.get("items", [])), "note": "今日候选数量", "tone": "green" if len(recommendations.get("items", [])) >= 6 else "amber" if len(recommendations.get("items", [])) >= 3 else "red"},
        ]
        news_feed = [
            {
                "time": row.get("time"),
                "type": row.get("type"),
                "title": row.get("title"),
                "impact": row.get("impact"),
            }
            for row in event_rows[:6]
        ]
        next_day_plan = self.user_next_day_plan(
            user,
            market=market,
            emotion=emotion,
            breadth=breadth,
            sectors=sectors,
            queue=queue,
            recommendations=recommendations,
            event_rows=event_rows,
            watch_rows=watch_rows,
            intelligence_announcements=intelligence_announcements,
            intelligence_research=intelligence_research,
        )
        bundle = {
            "review_date": datetime.now().date().isoformat(),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "title": f"{datetime.now().date().isoformat()} 复盘中心",
            "summary": f"{emotion.get('state', '中性')}环境下，优先盯住{('、'.join(item.get('name', '') for item in sectors[:2]) or '主线板块')}和自选股里的高优先级动作。",
            "market_review": {
                "headline": f"{market.mood}，情绪量能 {emotion.get('composite_score', '-')}/100，市场广度信号：{breadth.get('signal', '-')}",
                "mood": market.mood,
                "emotion_score": emotion.get("composite_score"),
                "breadth_signal": breadth.get("signal"),
                "turnover_billion": market.turnover_billion,
                "up_count": market.up_count,
                "down_count": market.down_count,
                "strong_sectors": sectors,
                "risk_alerts": risk_lines or ["当前无突出风险持仓"],
                "next_focus": focus_lines or ["等待下一轮板块强弱刷新"],
                "key_signals": key_signals,
                "news_feed": news_feed,
                "intelligence": {
                    "announcements": intelligence_announcements[:6],
                    "research_reports": intelligence_research[:6],
                    "by_stock": intelligence_by_stock,
                },
            },
            "watchlist_review": {
                "scope": "current_user_watchlist",
                "count": len(watch_rows),
                "items": watch_rows,
                "history_summary": history_summary,
            },
            "observation_pool": {
                "market_gate": recommendations.get("market_gate", {}),
                "strong_sectors": recommendations.get("strong_sectors", []),
                "items": recommendations.get("items", []),
            },
            "next_day_plan": next_day_plan,
            "history": {
                "count": len(history),
                "latest": history[:6],
            },
        }
        review_cache[cache_key] = {"at": datetime.now(), "payload": bundle}
        return bundle

    def daily_review_markdown(self, bundle: dict) -> str:
        markdown = self._daily_review_markdown_v2(bundle)
        next_day = bundle.get("next_day_plan", {})
        if "## 明日预判" in markdown:
            return markdown
        focus_lines = "\n".join(
            f"- {item.get('name')}: 强度 {item.get('strength')} / 涨跌 {item.get('change_pct')}% / {item.get('reason')}"
            for item in (next_day.get("focus_sectors") or [])
            if item
        ) or "- 暂无"
        action_lines = "\n".join(
            f"- {item.get('name')}({item.get('code')}): {item.get('action')} / 触发 {item.get('trigger_price')} / 支撑 {item.get('support')} / {item.get('reason')}"
            for item in (next_day.get("watch_actions") or [])
            if item
        ) or "- 暂无"
        forbidden_lines = "\n".join(f"- {item}" for item in (next_day.get("forbidden_actions") or []) if item) or "- 暂无"
        checklist_lines = "\n".join(f"- {item}" for item in (next_day.get("prep_checklist") or []) if item) or "- 暂无"
        next_day_section = f"""

## 明日预判
- 阶段：{next_day.get('stage') or '-'}
- 评分：{next_day.get('score') or '-'}
- 立场：{next_day.get('stance') or '-'}
- 市场闸门：{(next_day.get('market_bias') or {}).get('gate') or '-'}

### 明日主线
{focus_lines}

### 明日动作清单
{action_lines}

### 禁止动作
{forbidden_lines}

### 开盘前检查表
{checklist_lines}
"""
        if "## 历史复盘" in markdown:
            return markdown.replace("## 历史复盘", f"{next_day_section}\n\n## 历史复盘", 1)
        return f"{markdown}{next_day_section}"

    def _daily_review_markdown_v2(self, bundle: dict) -> str:
        market = bundle.get("market_review", {})
        watchlist = bundle.get("watchlist_review", {})
        observation = bundle.get("observation_pool", {})
        next_day = bundle.get("next_day_plan", {})
        history = bundle.get("history", {})
        intelligence = market.get("intelligence", {})

        def bullet_list(items: list[str], empty_text: str = "- 暂无") -> str:
            return "\n".join(f"- {item}" for item in items if item) or empty_text

        watch_md = bullet_list(
            [
                f"{item.get('name')}({item.get('code')}): 动作 {item.get('action') or '-'}，现价 {item.get('price') or '-'}，涨跌 {item.get('change_pct') or '-'}%，止损 {item.get('stop_loss') or '-'}，止盈 {item.get('take_profit') or '-'}。AI摘要：{item.get('ai_summary') or '-'}"
                for item in (watchlist.get("items") or [])
            ]
        )
        announcement_md = bullet_list(
            [
                f"{item.get('date') or '-'} {item.get('name') or item.get('code')}: {item.get('title')} ({item.get('source') or '公告'})"
                for item in (intelligence.get("announcements") or [])
            ]
        )
        research_md = bullet_list(
            [
                f"{item.get('date') or '-'} {item.get('name') or item.get('code')}: {item.get('title')} / {item.get('institution') or '-'} / {item.get('rating') or '-'}"
                for item in (intelligence.get("research_reports") or [])
            ]
        )
        observation_md = bullet_list(
            [
                f"{item.get('name')}({item.get('code')}): 评分 {item.get('score') or '-'}，动作 {item.get('action') or '-'}，证据 {('；'.join(item.get('evidence') or []) or '-')}"
                for item in (observation.get("items") or [])[:10]
            ]
        )
        next_day_focus_md = bullet_list(
            [
                f"{item.get('name')}: 强度 {item.get('strength')} / 涨跌 {item.get('change_pct')}% / {item.get('reason')}"
                for item in (next_day.get("focus_sectors") or [])
            ]
        )
        next_day_actions_md = bullet_list(
            [
                f"{item.get('name')}({item.get('code')}): {item.get('action')} / 触发 {item.get('trigger_price')} / 支撑 {item.get('support')} / {item.get('reason')}"
                for item in (next_day.get("watch_actions") or [])
            ]
        )
        next_day_forbidden_md = bullet_list(next_day.get("forbidden_actions") or [])
        next_day_checklist_md = bullet_list(next_day.get("prep_checklist") or [])
        history_md = bullet_list(
            [
                f"{item.get('created_at') or '-'} {item.get('title') or item.get('review_date') or '复盘'}：{item.get('summary') or '-'}"
                for item in (history.get("latest") or [])
            ]
        )
        return f"""# {bundle.get('title') or '每日复盘'}

- 复盘日期：{bundle.get('review_date') or '-'}
- 生成时间：{bundle.get('generated_at') or '-'}
- 综合结论：{bundle.get('summary') or '-'}

## 市场总览

- 市场标题：{market.get('headline') or '-'}
- 市场情绪：{market.get('mood') or '-'} / {market.get('emotion_score') or '-'} 分
- 宽度信号：{market.get('breadth_signal') or '-'}
- 两市成交额：{market.get('turnover_billion') or '-'} 亿
- 上涨 / 下跌：{market.get('up_count') or '-'} / {market.get('down_count') or '-'}

### 主线关注

{bullet_list(market.get('next_focus') or [])}

### 风险提示

{bullet_list(market.get('risk_alerts') or [])}

## 自选股复盘

{watch_md}

## 公告与研报跟踪

### 公告

{announcement_md}

### 研报

{research_md}

## 明日观察池

{observation_md}

## 历史复盘

{history_md}
"""

    def record_user_trade_action(self, user: dict, payload: dict) -> dict:
        code = self.normalize_code(str(payload.get("code", "")))
        queue = self.user_trading_action_queue(user)
        action_item = next((item for item in queue.get("actions", []) if item["code"] == code), None)
        if not action_item:
            return {"error": "action_not_found", "code": code}
        mode = payload.get("mode", "paper")
        entry = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "user_id": user.get("id"),
            "username": user.get("username"),
            "mode": mode,
            "status": "simulated" if mode == "paper" else "manual_confirmed",
            "name": action_item["name"],
            "code": action_item["code"],
            "action": action_item["action"],
            "label": action_item["label"],
            "price": action_item["price"],
            "quantity": action_item["quantity"],
            "trigger_price": action_item["trigger_price"],
            "invalidation_price": action_item["invalidation_price"],
            "pnl_pct": action_item["pnl_pct"],
            "pnl_amount": action_item["pnl_amount"],
            "daily_pnl": action_item["daily_pnl"],
            "reason": action_item["reason"],
            "evidence": action_item["evidence"],
            "market_gate": queue.get("gate"),
            "emotion_volume": queue.get("emotion_volume"),
            "note": payload.get("note", ""),
            "review": {
                "next_check": action_item["next_step"],
                "result": "pending",
                "exit_reason": "",
            },
        }
        rows = self.read_user_trade_log(user)
        rows.insert(0, entry)
        self.write_user_trade_log(user, rows[:500])
        return {"ok": True, "entry": entry, "count": len(rows[:500])}

    def ea_simulation_status(self, user: dict) -> dict:
        rows = [row for row in self.read_user_trade_log(user) if row.get("source") == "ea_simulation"]
        return {
            "enabled": True,
            "mode": "paper_only",
            "workflow": ["paper", "review", "approved"],
            "workflow_note": "模拟生成 → 人工复核 → 明确批准；approved 仍不会直接连接券商实盘。",
            "title": "EA模拟盘",
            "safety_policy": "只模拟，不实盘；绝不自动实盘下单，所有结果只进入交易日志和复盘归因。",
            "strategies": [
                {
                    "id": "anti_quant_tail",
                    "name": "反量化尾盘策略",
                    "description": "避开早盘追高和14:00-14:30风险窗口，把动作队列信号转成模拟成交，用于验证尾盘择机规则。",
                    "risk": "中",
                },
                {
                    "id": "trend_guard",
                    "name": "趋势守门策略",
                    "description": "只模拟通过市场闸门和个股风控的 WATCH/REDUCE/BUY 动作，观察趋势信号是否稳定。",
                    "risk": "低",
                },
            ],
            "last_orders": rows[:20],
            "stats": {
                "total_orders": len(rows),
                "last_run_at": rows[0]["created_at"] if rows else "",
                "manual_required": True,
            },
        }

    def ensure_ea_paper_snapshot(self, user: dict, strategy_id: str = "trend_guard") -> dict:
        """Run one idempotent paper pass per user and trading day."""
        today = datetime.now().date().isoformat()
        state = self.read_user_state(user)
        marker_date = str(state.get("ea_last_paper_run_date") or "")
        if marker_date == today:
            return {
                "ok": True,
                "ran": False,
                "count": int(state.get("ea_last_paper_run_count") or 0),
                "last_run_at": str(state.get("ea_last_paper_run_at") or ""),
            }
        rows = [row for row in self.read_user_trade_log(user) if row.get("source") == "ea_simulation" and str(row.get("created_at", "")).startswith(today)]
        if rows:
            last_run_at = rows[0].get("created_at", "")
            state.update({"ea_last_paper_run_date": today, "ea_last_paper_run_count": len(rows), "ea_last_paper_run_at": last_run_at})
            self.write_user_state(user, state)
            return {"ok": True, "ran": False, "count": len(rows), "last_run_at": last_run_at}
        result = self.run_user_ea_simulation(user, strategy_id=strategy_id, max_orders=5)
        last_run_at = result.get("created_at") or datetime.now().isoformat(timespec="seconds")
        state.update({"ea_last_paper_run_date": today, "ea_last_paper_run_count": int(result.get("count") or 0), "ea_last_paper_run_at": last_run_at})
        self.write_user_state(user, state)
        return {"ok": bool(result.get("ok")), "ran": True, "count": int(result.get("count") or 0), "last_run_at": last_run_at}

    def run_user_ea_simulation(self, user: dict, strategy_id: str = "anti_quant_tail", max_orders: int = 5) -> dict:
        max_orders = max(1, min(int(max_orders or 5), 20))
        queue = self.user_trading_action_queue(user)
        actions = list(queue.get("actions") or [])
        if not actions:
            market = self.market_overview()
            actions = []
            for item in self.get_user_watchlist(user)[:max_orders]:
                built = build_watchlist_item(item, market)
                actions.append({
                    "name": item.name,
                    "code": item.code,
                    "action": built.action,
                    "label": built.action,
                    "price": item.price,
                    "quantity": max(int(item.quantity or 100), 100),
                    "trigger_price": round(item.price * 1.01, 2),
                    "invalidation_price": round(item.price * 0.97, 2),
                    "pnl_pct": built.pnl_pct,
                    "pnl_amount": built.pnl_amount,
                    "daily_pnl": built.daily_pnl_amount,
                    "reason": "EA模拟盘基于当前自选股快照生成，用于验证策略，不触发真实下单。",
                    "evidence": ["自选股快照", "模拟盘", "人工确认前置"],
                    "next_step": "进入模拟日志，盘后复盘命中率和回撤。",
                })
        quant_radar = self.quant_control_radar()
        risk_gate = quant_radar.get("current_window", {})
        unified_gate = self.unified_trading_gate()
        orders = []
        now_text = datetime.now().isoformat(timespec="seconds")
        for action_item in actions[:max_orders]:
            entry = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "created_at": now_text,
                "user_id": user.get("id"),
                "username": user.get("username"),
                "source": "ea_simulation",
                "strategy_id": strategy_id or "anti_quant_tail",
                "mode": "paper",
                "status": "ea_simulated",
                "name": action_item["name"],
                "code": action_item["code"],
                "action": action_item["action"],
                "label": action_item.get("label") or action_item["action"],
                "price": action_item.get("price", 0),
                "quantity": action_item.get("quantity", 0),
                "trigger_price": action_item.get("trigger_price", 0),
                "invalidation_price": action_item.get("invalidation_price", 0),
                "pnl_pct": action_item.get("pnl_pct", 0),
                "pnl_amount": action_item.get("pnl_amount", 0),
                "daily_pnl": action_item.get("daily_pnl", 0),
                "reason": action_item.get("reason", ""),
                "evidence": action_item.get("evidence", []),
                "market_gate": queue.get("gate"),
                "emotion_volume": queue.get("emotion_volume"),
                "risk_gate": {
                    "name": risk_gate.get("name", "未识别窗口"),
                    "stance": risk_gate.get("stance", "paper_only"),
                    "risk": risk_gate.get("risk", 0),
                    "action": risk_gate.get("action", ""),
                },
                "unified_gate": unified_gate,
                "paper_action_allowed": unified_gate.get("allowed", True),
                "note": "EA模拟盘自动生成：只模拟，不实盘；后续必须人工确认或官方券商接口。",
                "review": {
                    "next_check": action_item.get("next_step", "盘后复盘模拟结果"),
                    "result": "pending",
                    "exit_reason": "",
                },
            }
            orders.append(entry)
        rows = self.read_user_trade_log(user)
        rows = orders + rows
        self.write_user_trade_log(user, rows[:500])
        return {
            "ok": True,
            "mode": "paper_only",
            "strategy_id": strategy_id or "anti_quant_tail",
            "safety_policy": "只模拟，不实盘；绝不自动实盘下单，所有模拟订单只用于复盘和归因。",
            "risk_gate": risk_gate,
            "unified_gate": unified_gate,
            "orders": orders,
            "count": len(orders),
        }

    def quant_control_radar(self, now: datetime | None = None) -> dict:
        current = now or datetime.now()
        minute = current.hour * 60 + current.minute
        windows = [
            {"key": "pre_market_prepare", "name": "盘前数据预热", "start": "00:00", "end": "09:14", "stance": "prepare_and_sync", "risk": 42, "action": "全天候接入数据源，预热自选股、公告、隔夜外围和9:15集合竞价准备。"},
            {"key": "call_auction", "name": "集合竞价观察", "start": "09:15", "end": "09:25", "stance": "observe_only", "risk": 72, "action": "不参与，只看高开低开和竞价量能。"},
            {"key": "pre_open_buffer", "name": "开盘缓冲", "start": "09:26", "end": "09:29", "stance": "sync_quotes", "risk": 62, "action": "继续同步竞价结果和盘口变化，等待连续竞价开盘，不因缺数据停止刷新。"},
            {"key": "open_shakeout", "name": "早盘量化砸盘", "start": "09:30", "end": "10:30", "stance": "wait_for_flush", "risk": 78, "action": "不追高，急跌只做候选标记，等第一波波动释放。"},
            {"key": "late_morning_confirm", "name": "上午确认窗口", "start": "11:00", "end": "11:30", "stance": "confirm_entry", "risk": 46, "action": "若板块和个股都企稳，可以小仓位确认；仍弱则继续观察。"},
            {"key": "noon_noise", "name": "午后噪声区", "start": "13:00", "end": "14:00", "stance": "reduce_frequency", "risk": 58, "action": "少操作，避免追随午后情绪波动。"},
            {"key": "tail_rebalance_watch", "name": "尾盘再平衡预警", "start": "14:00", "end": "14:30", "stance": "avoid_chasing", "risk": 86, "action": "警惕高位板块被兑现，强拉不追，持仓先看风险。"},
            {"key": "tail_dislocation", "name": "尾盘错杀观察", "start": "14:30", "end": "14:57", "stance": "contrarian_watch", "risk": 68, "action": "急跌不恐慌，优先看真实业绩和板块承接，满足条件再分批。"},
            {"key": "closing_auction", "name": "收盘集合竞价", "start": "14:57", "end": "15:00", "stance": "no_cancel_risk", "risk": 82, "action": "不参与不可撤单窗口，只记录信号等待复盘。"},
            {"key": "after_market_review", "name": "盘后复盘与数据补全", "start": "15:01", "end": "23:59", "stance": "review_and_backfill", "risk": 38, "action": "继续同步公告、研报、日K、资金流和模拟盘结果，给第二天预判做准备。"},
        ]
        def to_minute(text: str) -> int:
            hour, minute_text = text.split(":", 1)
            return int(hour) * 60 + int(minute_text)
        current_window = next((item for item in windows if to_minute(item["start"]) <= minute <= to_minute(item["end"])), {
            "key": "off_session",
            "name": "非关键交易窗口",
            "start": "--",
            "end": "--",
            "stance": "review_or_prepare",
            "risk": 35,
            "action": "适合复盘、调仓计划和提醒规则维护，不建议临时冲动下单。",
        })
        market = self.market_overview()
        emotion = self.market_emotion_volume()
        pressure = 0
        if market.down_count > market.up_count * 1.25:
            pressure += 8
        if emotion.get("composite_score", 50) < 45:
            pressure += 6
        if current_window["key"] in {"tail_rebalance_watch", "closing_auction"}:
            pressure += 8
        risk_score = max(0, min(100, int(current_window["risk"]) + pressure))
        return {
            "updated_at": current.isoformat(timespec="seconds"),
            "risk_score": risk_score,
            "current_window": current_window,
            "data_policy": {
                "mode": "all_day",
                "quote_window": "09:15-15:00",
                "allow_call_auction": True,
                "premarket_start": "00:00",
                "aftermarket_end": "23:59",
                "rule": "全天候尝试同步数据；9:15集合竞价开始进入实时观察，不再等9:30连续竞价才刷新。",
                "fallback": "若实时源未返回集合竞价字段，仍保留昨收/盘口快照并标记来源，不用模拟数据伪装真实行情。",
            },
            "global_linkage": {
                "status": "watch",
                "drivers": ["费城半导体指数", "纳斯达克", "韩国科技股", "港股科技"],
                "note": "当前先用交易时段和板块强弱做提示；接入海外指数实时源后可升级为联动评分。",
            },
            "rules": [
                "早盘看戏，不追高。",
                "10点前后的急跌只做候选，不急着重仓。",
                "11:00-11:30更适合做确认。",
                "14:00-14:30警惕量化再平衡兑现。",
                "14:30后的急跌优先看错杀和承接，不做情绪割肉。",
                "14:57后不参与不可撤单窗口。",
            ],
            "automation_policy": {
                "max_mode": "confirm_before_order",
                "paper_trade": "allowed",
                "real_order": "blocked_until_broker_api_and_risk_limits",
                "reason": "真实下单必须先完成券商接口、资金上限、撤单规则、风控熔断和人工确认。",
            },
        }

    def user_trading_action_queue(self, user: dict) -> dict:
        market = self.market_overview()
        emotion = self.market_emotion_volume()
        quant_radar = self.quant_control_radar()
        quant_fund_radar = self.user_quant_fund_radar(user)
        quant_snapshot = self.maybe_save_quant_fund_radar_snapshot(user, quant_fund_radar)
        quant_alerts = {item["code"]: item for item in quant_fund_radar.get("top_alerts", []) if item.get("suspicion_score", 0) >= 75}
        items = [build_watchlist_item(stock, market) for stock in self.get_user_watchlist(user)]
        rows = []
        for item in items:
            stock = item.stock
            if item.quantity <= 0:
                action, label, priority = "WATCH", "仅观察", 35
                reason = "非自持股票，只纳入盯盘，不进入真实交易动作。"
            elif item.pnl_pct <= -20:
                action, label, priority = "REDUCE_RISK", "风险复核", 82
                reason = "真实持仓亏损较深，优先检查是否破位和是否需要降风险。"
            elif item.pnl_amount > 10000:
                action, label, priority = "PROTECT", "盈利保护", 78
                reason = "已有盈利垫，重点跟踪移动止盈和顶背离风险。"
            else:
                action, label, priority = "HOLD_CONFIRM", "持有确认", 58
                reason = "等待行情、资金、模型信号进一步确认。"
            quant_alert = quant_alerts.get(stock.code)
            evidence = [f"会员自选：{user.get('username')}", f"情绪量能：{emotion.get('state')} {emotion.get('composite_score')}/100"]
            if quant_alert:
                action, label = "QUANT_WATCH", "量化异动盯防"
                priority = max(priority, 92 if quant_alert.get("suspicion_score", 0) >= 80 else 84)
                reason = f"尾盘/资金异动触发量化嫌疑 {quant_alert.get('suspicion_score')}/100：{quant_alert.get('reason')}"
                evidence.extend(
                    [
                        f"资金方向：{quant_alert.get('fund_direction')}",
                        f"量化嫌疑：{quant_alert.get('suspicion_score')}/100",
                    ]
                )
                evidence.extend((quant_alert.get("evidence") or [])[:2])
            rows.append(
                {
                    "name": stock.name,
                    "code": stock.code,
                    "price": round(stock.price, 3),
                    "change_pct": round(stock.change_pct, 2),
                    "quantity": item.quantity,
                    "cost": stock.cost,
                    "market_value": round(stock.price * item.quantity, 2),
                    "pnl_pct": item.pnl_pct,
                    "pnl_amount": item.pnl_amount,
                    "daily_pnl": item.daily_pnl_amount,
                    "action": action,
                    "label": label,
                    "priority": priority,
                    "trigger_price": round(stock.price * 1.02, 2),
                    "invalidation_price": round(stock.price * 0.97, 2),
                    "max_position_pct": 12,
                    "position_advice": label,
                    "reason": reason,
                    "evidence": evidence,
                    "next_step": "人工确认后再记录到交易日志。",
                    "data_source": stock.source,
                }
            )
        rows.sort(key=lambda item: item["priority"], reverse=True)
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "member_decision_queue",
            "principle": "按当前登录会员自己的自选和持仓生成，不读取其他会员股票池。",
            "gate": emotion.get("gate"),
            "unified_gate": self.unified_trading_gate(),
            "gate_history": self.unified_gate_history(user, 10),
            "gate_reason": "会员隔离动作队列",
            "market": {"mood": market.mood, "up_count": market.up_count, "down_count": market.down_count, "turnover_billion": market.turnover_billion},
            "emotion_volume": emotion,
            "quant_control": quant_radar,
            "quant_fund_radar": quant_fund_radar,
            "quant_fund_snapshot": quant_snapshot,
            "execution_controls": {
                "precheck_endpoint": "/api/trading/precheck",
                "cooldown_endpoint": "/api/trading/cooldown",
                "stock_gate_endpoint": "/api/stocks/{code}/compliance-gate",
                "manual_confirm_required": True,
                "real_order_enabled": False,
                "items": [
                    {"name": "订单预检", "status": "enabled", "detail": "校验可用资金、100股整数倍、价格和冷静期"},
                    {"name": "情绪冷静期", "status": "enabled", "detail": "急拉追高、急跌恐慌、尾盘异动先冷静再确认"},
                    {"name": "个股硬门槛", "status": "enabled", "detail": "ST/退市风险硬阻断，流动性和基本面异常提醒"},
                    {"name": "自动实盘", "status": "locked", "detail": "接入券商账号前只生成确认清单，不直接下单"},
                ],
            },
            "summary": {action: sum(1 for row in rows if row["action"] == action) for action in {row["action"] for row in rows}},
            "actions": rows,
        }

    def add_watchlist(self, code: str) -> list[Stock]:
        normalized = self.normalize_code(code)
        if normalized not in self.stocks:
            self.fetch_stock_by_code(normalized)
        if normalized in self.stocks and normalized not in self.watchlist_codes:
            self.watchlist_codes.insert(0, normalized)
        return self.get_watchlist()

    def remove_watchlist(self, code: str) -> list[Stock]:
        self.watchlist_codes = [item for item in self.watchlist_codes if item != code]
        self.write_position_store()
        return self.get_watchlist()

    def tick(self) -> dict:
        self.refresh_indices()
        if self.refresh_quotes(self.watchlist_codes):
            return {
                "type": "tick",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "indices": [item.model_dump() for item in self.indices.values()],
                "watchlist": [self.stocks[code].model_dump() for code in self.watchlist_codes if code in self.stocks],
            }

        return {
            "type": "tick",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "indices": [item.model_dump() for item in self.indices.values()],
            "watchlist": [self.stocks[code].model_dump() for code in self.watchlist_codes if code in self.stocks],
        }
