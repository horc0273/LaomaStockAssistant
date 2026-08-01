import gc
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


class MobileDashboardApiTests(unittest.TestCase):
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

    def test_mobile_dashboard_aggregates_mobile_home_sections(self):
        self.provider.add_user_watchlist({"id": 1, "username": "laoma"}, "002463.SZ")

        response = self.client.get("/api/mobile/dashboard", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("updated_at", payload)
        self.assertIn("data_state", payload)
        self.assertIn("market_mood", payload)
        self.assertIn("portfolio_summary", payload)
        self.assertIn("watchlist_summary", payload)
        self.assertIn("ai_recommendations", payload)
        self.assertIn("trade_actions", payload)
        self.assertIn("risk_alerts", payload)
        self.assertIn("access", payload)
        self.assertIn("quant_control", payload)
        self.assertIn("quant_fund_radar", payload)
        self.assertIn("quick_links", payload)
        self.assertEqual(payload["watchlist_summary"]["scope"], "current_user_watchlist")
        self.assertIn("local_url", payload["access"])
        self.assertIn("lan_url", payload["access"])
        self.assertIn("current_window", payload["quant_control"])
        self.assertIn("automation_policy", payload["quant_control"])
        self.assertIn("tail_session", payload["quant_fund_radar"])
        self.assertIn("linkage", payload["quant_fund_radar"])
        self.assertGreaterEqual(len(payload["quick_links"]), 4)


if __name__ == "__main__":
    unittest.main()
