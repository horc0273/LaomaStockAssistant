import os
import tempfile
import unittest

from app.data_provider import DemoDataProvider
from app.market_data_gateway import MarketDataGateway
from app.preheat_service import DataPreheatService


class P0PreheatTests(unittest.TestCase):
    def test_preheat_records_source_health_and_cache_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old = os.environ.get("LAOMA_STOCK_DATA_DIR")
            os.environ["LAOMA_STOCK_DATA_DIR"] = temp_dir
            try:
                provider = DemoDataProvider()
                gateway = MarketDataGateway([("demo", lambda: [{"code": "000001.SZ", "price": 1}])])
                result = DataPreheatService(provider, gateway).run_once(reason="test")
                self.assertTrue(result["ok"])
                self.assertIn("gateway", result)
                self.assertIn("quality", result)
                self.assertIn("last_run_at", result)
            finally:
                if old is None:
                    os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
                else:
                    os.environ["LAOMA_STOCK_DATA_DIR"] = old


class AutoEASimulationTests(unittest.TestCase):
    def test_auto_paper_run_is_idempotent_for_same_trading_day(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old = os.environ.get("LAOMA_STOCK_DATA_DIR")
            os.environ["LAOMA_STOCK_DATA_DIR"] = temp_dir
            try:
                provider = DemoDataProvider()
                user = {"id": 1, "username": "tester"}
                first = provider.ensure_ea_paper_snapshot(user)
                second = provider.ensure_ea_paper_snapshot(user)
                self.assertTrue(first["ok"])
                self.assertFalse(second["ran"])
                self.assertEqual(provider.ea_simulation_status(user)["stats"]["total_orders"], first["count"])
            finally:
                if old is None:
                    os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
                else:
                    os.environ["LAOMA_STOCK_DATA_DIR"] = old


if __name__ == "__main__":
    unittest.main()
