import gc
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


ROOT = Path(__file__).resolve().parents[1]


class FirstBatchFeedbackApiTests(unittest.TestCase):
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
        if hasattr(self, "client"):
            self.client.close()
        main.provider = self.original_provider
        main.auth_service = self.original_auth_service
        self.client = None
        self.provider = None
        self.auth_service = None
        gc.collect()
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        self.temp_dir.cleanup()

    def test_dashboard_bootstrap_returns_only_first_screen_payload(self):
        response = self.client.get("/api/dashboard/bootstrap", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("market", payload)
        self.assertIn("portfolio", payload)
        self.assertIn("watchlist", payload)
        self.assertIn("data_sources", payload)
        self.assertIn("ai_recommendations", payload)
        self.assertIn("membership", payload)
        self.assertNotIn("daily_review", payload)
        self.assertNotIn("quant_upgrade_plan", payload)

    def test_ai_recommendations_have_reader_friendly_signal_categories(self):
        response = self.client.get("/api/recommendations/ai?limit=10", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("categories", payload)
        self.assertTrue(payload["categories"])
        category_keys = {item["key"] for item in payload["categories"]}
        self.assertIn("short_term", category_keys)
        self.assertIn("trend", category_keys)
        for item in payload["items"]:
            self.assertIn(item["signal_category"], category_keys)
            self.assertIn("signal_label", item)

    def test_mobile_dashboard_exposes_six_core_cards_and_data_source_card(self):
        response = self.client.get("/api/mobile/dashboard", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mobile_layout"]["mode"], "six_core_cards")
        self.assertEqual(payload["mobile_layout"]["core_cards"], ["market", "portfolio", "risk", "actions", "ai", "data"])
        self.assertIn("data_source_card", payload)
        self.assertIn(payload["data_source_card"]["level"], {"green", "yellow", "red"})


class FirstBatchFeedbackFrontendTests(unittest.TestCase):
    def test_frontend_has_progressive_bootstrap_and_source_traffic_lights(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("/api/dashboard/bootstrap", js)
        self.assertIn("loadDashboardBootstrap", js)
        self.assertIn("loadDeferredDashboardData", js)
        self.assertIn("sourceTrafficLight", js)
        self.assertIn("source-badge red", css)
        self.assertIn('id="mobileDataSourceCard"', html)
        self.assertIn("ai-rec-category", css)


if __name__ == "__main__":
    unittest.main()
