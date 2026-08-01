import gc
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider
from app.tushare_service import TushareService


class TushareIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("LAOMA_STOCK_DATA_DIR")
        self.old_token = os.environ.get("TUSHARE_TOKEN")
        os.environ["LAOMA_STOCK_DATA_DIR"] = self.temp_dir.name
        os.environ.pop("TUSHARE_TOKEN", None)
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
        if self.old_token is None:
            os.environ.pop("TUSHARE_TOKEN", None)
        else:
            os.environ["TUSHARE_TOKEN"] = self.old_token
        self.temp_dir.cleanup()

    def test_tushare_token_is_persisted_for_server_deployments(self):
        service = TushareService(self.provider.data_dir / "tushare_token.txt")

        result = service.save_token("abc123456789")

        self.assertTrue(result["ok"])
        self.assertTrue(service.enabled())
        self.assertEqual(service.token(), "abc123456789")
        self.assertIn("abc1", service.config_status()["masked_token"])

    def test_admin_api_saves_tushare_token_without_retyping_after_restart(self):
        response = self.client.post(
            "/api/tushare/config",
            headers=self.headers,
            json={"token": "server-token-xyz"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue((self.provider.data_dir / "tushare_token.txt").exists())
        self.assertEqual((self.provider.data_dir / "tushare_token.txt").read_text(encoding="utf-8"), "server-token-xyz")

    def test_minute_chart_uses_tushare_when_realtime_source_is_unavailable(self):
        self.provider.eastmoney_history = lambda *args, **kwargs: None
        self.provider.tushare.minute = lambda code, freq="1min", days=1: {
            "ok": True,
            "source": "tushare:stk_mins",
            "rows": [
                {"trade_time": "2026-07-14 09:31:00", "close": 137.1, "open": 136.8, "high": 137.2, "low": 136.7, "vol": 1000, "amount": 1371000},
                {"trade_time": "2026-07-14 09:32:00", "close": 137.3, "open": 137.1, "high": 137.4, "low": 137.0, "vol": 1500, "amount": 2059500},
            ],
        }

        chart = self.provider.stock_minute_chart("002463.SZ")

        self.assertTrue(chart["is_real"])
        self.assertEqual(chart["source"], "tushare:stk_mins")
        self.assertEqual(len(chart["items"]), 2)
        self.assertEqual(chart["items"][0]["time"], "2026-07-14 09:31:00")


if __name__ == "__main__":
    unittest.main()
