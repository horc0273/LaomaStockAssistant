import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.abnormal_service import AbnormalMonitorService
from app.industry_chain_service import IndustryChainService
from app.infrastructure import Persistence
from app.recommendation_scoring_service import RecommendationScoringService
from app.screener_service import ScreenerService


UNIVERSE = [
    {
        "code": "002463.SZ",
        "name": "沪电股份",
        "price": 147.9,
        "change_pct": 9.96,
        "amount": 3_800_000_000,
        "turnover_rate": 6.4,
        "volume_ratio": 2.4,
        "main_net": 420_000_000,
        "high": 148.0,
        "low": 135.0,
        "open": 138.0,
        "prev_close": 134.5,
        "industry": "PCB",
        "concepts": ["算力", "PCB", "AI服务器"],
        "signals": ["volume_breakout", "macd_golden_cross", "limit_up_touch"],
    },
    {
        "code": "600000.SH",
        "name": "浦发银行",
        "price": 9.4,
        "change_pct": -4.8,
        "amount": 480_000_000,
        "turnover_rate": 0.6,
        "volume_ratio": 0.7,
        "main_net": -120_000_000,
        "high": 9.9,
        "low": 9.3,
        "open": 9.8,
        "prev_close": 9.88,
        "industry": "银行",
        "concepts": ["大金融"],
        "signals": ["large_sell", "below_ma5"],
    },
]


class AbnormalMonitorServiceTests(unittest.TestCase):
    def test_catalog_separates_positive_and_negative_types(self):
        catalog = AbnormalMonitorService().catalog()
        self.assertIn("positive", catalog)
        self.assertIn("negative", catalog)
        self.assertTrue(any(item["key"] == "limit_up_touch" for item in catalog["positive"]))
        self.assertTrue(any(item["key"] == "large_sell" for item in catalog["negative"]))

    def test_detects_positive_and_negative_events(self):
        result = AbnormalMonitorService().events(UNIVERSE, selected_types=["limit_up_touch", "large_sell"], source_meta={"source": "unit-test"})
        event_types = {(item["code"], item["type_key"]) for item in result["items"]}
        self.assertIn(("002463.SZ", "limit_up_touch"), event_types)
        self.assertIn(("600000.SH", "large_sell"), event_types)
        self.assertEqual(result["source"], "unit-test")


class ExtendedScreenerCatalogTests(unittest.TestCase):
    def test_catalog_includes_expanded_models_from_reference_screenshot(self):
        signals = {item["key"] for item in ScreenerService().catalog()["signals"]}
        self.assertIn("strong_multi_bull", signals)
        self.assertIn("volume_attack", signals)
        self.assertIn("popularity_rank_up_3d", signals)
        self.assertGreaterEqual(len(signals), 25)

    def test_scanner_matches_new_signal_conditions(self):
        service = ScreenerService()
        result = service.run(UNIVERSE, {"all": [{"signal": "limit_up_touch"}], "limit": 10})
        self.assertEqual([item["code"] for item in result["items"]], ["002463.SZ"])


class IndustryChainServiceTests(unittest.TestCase):
    def test_analyzes_topic_into_chain_bottlenecks_and_candidates(self):
        report = IndustryChainService().analyze("AI算力", universe=UNIVERSE)
        self.assertEqual(report["topic"], "AI算力")
        self.assertTrue(report["chain"])
        self.assertTrue(report["bottlenecks"])
        self.assertEqual(report["candidates"][0]["code"], "002463.SZ")
        self.assertIn("需验证", report["disclaimer"])

    def test_analyzes_stock_back_to_industry_chain_role(self):
        report = IndustryChainService().analyze_stock("002463.SZ", universe=UNIVERSE)
        self.assertEqual(report["stock"]["code"], "002463.SZ")
        self.assertTrue(report["stock"]["chain_role"])


class RecommendationScoringServiceTests(unittest.TestCase):
    def test_scores_candidate_with_abnormal_and_industry_chain_evidence(self):
        abnormal = AbnormalMonitorService().events(UNIVERSE, source_meta={"source": "unit-test"})
        chain = IndustryChainService().analyze("AI算力", universe=UNIVERSE)
        score = RecommendationScoringService().score(UNIVERSE[0], abnormal["items"], chain)
        self.assertGreaterEqual(score["total_score"], 70)
        self.assertIn(score["level"], {"强观察", "观察"})
        self.assertTrue(score["components"]["abnormal"])
        self.assertTrue(score["components"]["industry_chain"])


class Hub2PersistenceTests(unittest.TestCase):
    def test_abnormal_and_industry_chain_records_are_isolated_by_user(self):
        with TemporaryDirectory() as folder:
            persistence = Persistence(Path(folder))
            event_id = persistence.save_abnormal_events(1, [{"code": "002463.SZ", "type_key": "limit_up_touch"}], {"source": "unit-test"})
            report_id = persistence.save_industry_chain_report(1, {"topic": "AI算力", "candidates": [{"code": "002463.SZ"}]})
            self.assertGreater(event_id, 0)
            self.assertGreater(report_id, 0)
            self.assertEqual(len(persistence.list_abnormal_events(1, limit=20)["items"]), 1)
            self.assertEqual(len(persistence.list_abnormal_events(2, limit=20)["items"]), 0)
            self.assertEqual(len(persistence.list_industry_chain_reports(1, limit=20)), 1)
            self.assertEqual(persistence.list_industry_chain_reports(2, limit=20), [])


if __name__ == "__main__":
    unittest.main()
