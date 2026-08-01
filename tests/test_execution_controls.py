import os
import gc
import tempfile
import unittest

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


class ExecutionControlTests(unittest.TestCase):
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
        self.user = login["user"]

    def tearDown(self):
        if hasattr(self, "client"):
            self.client.close()
        self.client = None
        self.provider = None
        self.auth_service = None
        gc.collect()
        main.provider = self.original_provider
        main.auth_service = self.original_auth_service
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        self.temp_dir.cleanup()

    def test_order_precheck_blocks_non_board_lot_and_cash_overrun(self):
        self.provider.update_manual_cash_available(self.user, 3000)

        result = self.provider.order_compliance_check(
            self.user,
            {"code": "002463.SZ", "side": "BUY", "price": 137.12, "quantity": 135},
        )

        self.assertFalse(result["allowed"])
        self.assertIn("非100股整数倍", result["violations"])
        self.assertIn("超过可用资金", result["violations"])
        self.assertIn("建议拆单/调整为", result["suggestions"][0])

    def test_cooldown_blocks_emotional_trade_until_confirmed_later(self):
        self.provider.start_trade_cooldown(self.user, "002463.SZ", "急拉追高", minutes=5)

        result = self.provider.order_compliance_check(
            self.user,
            {"code": "002463.SZ", "side": "BUY", "price": 137.12, "quantity": 100},
        )

        self.assertFalse(result["allowed"])
        self.assertIn("冷静期未结束", result["violations"])
        self.assertGreater(result["cooldown"]["remaining_seconds"], 0)

    def test_stock_gate_blocks_st_and_low_liquidity_candidates(self):
        result = self.provider.stock_compliance_gate(
            {
                "code": "000001.SZ",
                "name": "*ST测试",
                "market_cap": 20_000_000_000,
                "turnover_rate": 0.3,
                "amount": 80_000_000,
                "pe_ttm": -5,
            }
        )

        self.assertFalse(result["passed"])
        self.assertIn("ST/退市风险", result["hard_blocks"])
        self.assertIn("流动性不足", result["warnings"])

    def test_api_exposes_execution_controls(self):
        self.provider.update_manual_cash_available(self.user, 3000)

        response = self.client.post(
            "/api/trading/precheck",
            headers=self.headers,
            json={"code": "002463.SZ", "side": "BUY", "price": 137.12, "quantity": 135},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["allowed"])
        self.assertIn("violations", payload)


if __name__ == "__main__":
    unittest.main()
