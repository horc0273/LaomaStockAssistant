import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider
from app.resonance_engine import calculate_resonance


ROOT = Path(__file__).resolve().parents[1]


class ResonanceEngineTests(unittest.TestCase):
    def test_trending_rows_produce_bullish_resonance_with_category_scores(self):
        rows = [{"close": 10 + i * 0.2, "volume": 100 + i} for i in range(40)]
        result = calculate_resonance(rows)

        self.assertEqual(result["stance"], "bullish")
        self.assertIn("trend", result["categories"])
        self.assertIn("oscillation", result["categories"])
        self.assertIn("strength", result["categories"])
        self.assertGreater(result["overall_score"], 60)

    def test_disabled_indicators_are_not_counted(self):
        rows = [{"close": 10 + i * 0.1, "volume": 100} for i in range(30)]
        result = calculate_resonance(rows, enabled={"ma": False, "macd": False, "boll": False})

        keys = {signal["key"] for signal in result["signals"]}
        self.assertNotIn("ma", keys)
        self.assertNotIn("macd", keys)
        self.assertNotIn("boll", keys)
        self.assertIn("config", result)


class ResonanceApiTests(unittest.TestCase):
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

    def test_resonance_endpoint_returns_config_and_risk_gate(self):
        response = self.client.get("/api/stocks/002463.SZ/resonance", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("categories", payload)
        self.assertIn("signals", payload)
        self.assertIn("risk_gate", payload)
        self.assertIn("enabled", payload["config"])


class ResonanceFrontendTests(unittest.TestCase):
    def test_frontend_exposes_resonance_panel_controls(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("/resonance", js)
        self.assertIn("resonance-panel", js)
        self.assertIn("data-resonance-indicator", js)
        self.assertIn("resonance-panel", css)


if __name__ == "__main__":
    unittest.main()
