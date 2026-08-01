import os
import tempfile
import unittest
import gc

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


class PortfolioCashOverrideTests(unittest.TestCase):
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

    def test_portfolio_summary_uses_manual_cash_after_confirmation(self):
        before = self.client.get("/api/portfolio/summary", headers=self.headers)
        self.assertEqual(before.status_code, 200)
        before_json = before.json()
        self.assertEqual(before_json["cash_source"], "broker_cash_snapshot")

        payload = {"cash_available": 123456.78}
        update = self.client.post("/api/portfolio/cash", json=payload, headers=self.headers)
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["cash_available"], 123456.78)
        self.assertEqual(update.json()["cash_source"], "manual_input")

        after = self.client.get("/api/portfolio/summary", headers=self.headers)
        self.assertEqual(after.status_code, 200)
        after_json = after.json()
        self.assertEqual(after_json["cash_available"], 123456.78)
        self.assertEqual(after_json["cash_source"], "manual_input")
        self.assertEqual(
            after_json["total_assets"],
            round(after_json["total_market_value"] + 123456.78, 2),
        )


if __name__ == "__main__":
    unittest.main()
