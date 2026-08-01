import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.infrastructure import Persistence
from app.market_data_gateway import MarketDataGateway, collect_paginated_batches
from app.screener_service import ScreenerService, StrategyValidationError


UNIVERSE = [
    {"code": "002463.SZ", "name": "沪电股份", "price": 48.2, "change_pct": 3.1, "amount": 1_800_000_000, "turnover_rate": 4.2, "volume_ratio": 1.8, "pe_ttm": 28.0, "market_cap": 82_000_000_000, "main_net": 160_000_000},
    {"code": "600000.SH", "name": "浦发银行", "price": 9.8, "change_pct": -0.4, "amount": 420_000_000, "turnover_rate": 0.4, "volume_ratio": 0.8, "pe_ttm": 6.2, "market_cap": 280_000_000_000, "main_net": -20_000_000},
    {"code": "300001.SZ", "name": "特锐德", "price": 22.0, "change_pct": 6.8, "amount": 960_000_000, "turnover_rate": 6.5, "volume_ratio": 2.2, "pe_ttm": 45.0, "market_cap": 23_000_000_000, "main_net": 90_000_000},
]


class MarketDataGatewayTests(unittest.TestCase):
    def test_gateway_uses_fallback_and_reports_metadata(self):
        gateway = MarketDataGateway([
            ("primary", lambda: (_ for _ in ()).throw(RuntimeError("rate limited"))),
            ("backup", lambda: UNIVERSE),
        ], stale_after_seconds=5)
        result = gateway.full_market_snapshot()
        self.assertEqual(result["source"], "backup")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(result["errors"][0]["source"], "primary")
        self.assertIn("latency_ms", result)
        self.assertFalse(result["is_stale"])

    def test_collects_full_universe_from_batched_pages(self):
        pages = {
            1: {"total": 5, "items": [{"code": "1"}, {"code": "2"}]},
            2: {"total": 5, "items": [{"code": "3"}, {"code": "4"}]},
            3: {"total": 5, "items": [{"code": "5"}]},
        }
        rows = collect_paginated_batches(lambda page, size: pages[page], page_size=2, max_workers=2)
        self.assertEqual([item["code"] for item in rows], ["1", "2", "3", "4", "5"])


class ScreenerServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ScreenerService()

    def test_rejects_unknown_fields(self):
        with self.assertRaises(StrategyValidationError):
            self.service.validate_dsl({"all": [{"field": "drop_table", "op": ">", "value": 1}]})

    def test_scans_with_whitelisted_conditions_and_sorting(self):
        dsl = {
            "all": [
                {"field": "turnover_rate", "op": ">=", "value": 3},
                {"field": "pe_ttm", "op": "between", "value": [0, 30]},
            ],
            "sort": [{"field": "main_net", "direction": "desc"}],
            "limit": 20,
        }
        result = self.service.run(UNIVERSE, dsl, source_meta={"source": "backup", "fetched_at": datetime.now().isoformat()})
        self.assertEqual([item["code"] for item in result["items"]], ["002463.SZ"])
        self.assertEqual(result["items"][0]["matched_count"], 2)
        self.assertEqual(result["source"], "backup")
        self.assertEqual(result["scanned_count"], 3)

    def test_parses_common_chinese_conditions_into_safe_dsl(self):
        parsed = self.service.parse_natural_language("换手率大于3%，市盈率低于30，主力净流入排序，最多20只")
        self.assertIn({"field": "turnover_rate", "op": ">", "value": 3.0}, parsed["all"])
        self.assertIn({"field": "pe_ttm", "op": "<", "value": 30.0}, parsed["all"])
        self.assertEqual(parsed["sort"][0], {"field": "main_net", "direction": "desc"})
        self.assertEqual(parsed["limit"], 20)

    def test_recommendation_metrics_use_only_later_prices(self):
        metrics = self.service.recommendation_metrics(
            entry_price=10.0,
            later_prices=[10.5, 9.5, 11.0, 10.8, 12.0],
        )
        self.assertEqual(metrics["return_1d_pct"], 5.0)
        self.assertEqual(metrics["return_3d_pct"], 10.0)
        self.assertEqual(metrics["return_5d_pct"], 20.0)
        self.assertEqual(metrics["max_drawdown_pct"], -9.52)


class ScreenerPersistenceTests(unittest.TestCase):
    def test_strategy_is_isolated_by_user(self):
        with TemporaryDirectory() as folder:
            persistence = Persistence(Path(folder))
            strategy_id = persistence.save_screener_strategy(1, {"name": "活跃股", "description": "测试", "dsl": {"all": [], "limit": 20}, "enabled": True})
            self.assertGreater(strategy_id, 0)
            self.assertEqual(len(persistence.list_screener_strategies(1)), 1)
            self.assertEqual(persistence.list_screener_strategies(2), [])

    def test_recommendation_keeps_entry_snapshot(self):
        with TemporaryDirectory() as folder:
            persistence = Persistence(Path(folder))
            recommendation_id = persistence.save_stock_recommendation(1, {
                "code": "002463.SZ", "stock_name": "沪电股份", "strategy_name": "动量资金共振",
                "entry_price": 48.2, "reason": "量价与资金共振", "risk_note": "跌破均线失效",
                "source": "eastmoney", "snapshot": {"price": 48.2, "change_pct": 3.1},
            })
            rows = persistence.list_stock_recommendations(1)
            self.assertEqual(rows[0]["id"], recommendation_id)
            self.assertEqual(rows[0]["entry_price"], 48.2)
            self.assertEqual(rows[0]["snapshot"]["price"], 48.2)

    def test_recommendation_daily_prices_are_upserted_once_per_day(self):
        with TemporaryDirectory() as folder:
            persistence = Persistence(Path(folder))
            recommendation_id = persistence.save_stock_recommendation(1, {"code": "002463.SZ", "stock_name": "沪电股份", "strategy_name": "测试", "entry_price": 10, "snapshot": {}})
            persistence.record_recommendation_prices(1, {"002463.SZ": 10.5}, "2026-06-23")
            persistence.record_recommendation_prices(1, {"002463.SZ": 10.8}, "2026-06-23")
            history = persistence.recommendation_price_history(1, [recommendation_id])
            self.assertEqual(history[recommendation_id], [10.8])


if __name__ == "__main__":
    unittest.main()
