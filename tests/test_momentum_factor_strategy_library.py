import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider
from app.factor_engine import calculate_factor_snapshot, classify_momentum_regime


ROOT = Path(__file__).resolve().parents[1]


class MomentumFactorUnitTests(unittest.TestCase):
    def test_momentum_regime_flags_overheated_and_crash_risk(self):
        overheated = classify_momentum_regime(momentum_pct=12, volatility_pct=8, drawdown_pct=1)
        crashed = classify_momentum_regime(momentum_pct=-8, volatility_pct=10, drawdown_pct=-14)

        self.assertEqual(overheated["key"], "overheated")
        self.assertGreater(overheated["risk_score"], 70)
        self.assertEqual(crashed["key"], "drawdown_risk")
        self.assertEqual(crashed["position_scale"], 0.5)

    def test_factor_snapshot_exposes_weighted_score_and_explanations(self):
        result = calculate_factor_snapshot({
            "momentum": 80,
            "value": 60,
            "quality": 75,
            "risk": 35,
            "fund_flow": 70,
            "sentiment": 55,
        })
        self.assertIn("total_score", result)
        self.assertGreater(result["total_score"], 50)
        self.assertEqual(len(result["factors"]), 6)
        self.assertTrue(result["explanations"])


class MomentumFactorApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("LAOMA_STOCK_DATA_DIR")
        os.environ["LAOMA_STOCK_DATA_DIR"] = self.temp_dir.name
        self.provider = DemoDataProvider()
        self.auth_service = AuthService(self.provider.data_dir)
        self.original_provider = main.provider
        self.original_auth_service = main.auth_service
        main.provider = self.provider
        main.auth_service = self.auth_service
        self.client = TestClient(main.app)
        login = self.auth_service.login("laoma", "maguo591034")
        self.headers = {"Authorization": f"Bearer {login['token']}"}

    def tearDown(self):
        self.client.close()
        main.provider = self.original_provider
        main.auth_service = self.original_auth_service
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_factor_analysis_endpoint_returns_momentum_and_factors(self):
        response = self.client.get("/api/research/factors/002463.SZ", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("momentum_regime", payload)
        self.assertIn("factor_snapshot", payload)
        self.assertIn("total_score", payload["factor_snapshot"])
        self.assertIn("data_sources", payload)

    def test_ea_strategy_catalog_separates_safe_paper_templates(self):
        response = self.client.get("/api/trading/ea-simulation/catalog", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        keys = {item["id"] for item in items}
        self.assertIn("momentum_regime", keys)
        self.assertIn("factor_blend", keys)
        self.assertIn("t0_simulation", keys)
        for item in items:
            self.assertEqual(item["mode"], "paper_only")


class MomentumFactorFrontendTests(unittest.TestCase):
    def test_frontend_surfaces_factor_and_strategy_library(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/api/research/factors/", js)
        self.assertIn("momentum-regime", js + html)
        self.assertIn("t0_simulation", js + html)
        self.assertIn("factor-score", js + html)


if __name__ == "__main__":
    unittest.main()
