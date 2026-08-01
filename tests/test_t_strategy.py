import unittest
from pathlib import Path


class TStrategyEngineTests(unittest.TestCase):
    def test_volatile_liquid_stock_passes_enterprise_gate_and_returns_intraday_plan(self):
        from app.t_strategy_engine import calculate_t_strategy

        rows = [
            {"time": f"09:{30 + i:02d}", "price": 100 + (i % 5) * 1.2, "volume": 1000 + i * 50}
            for i in range(30)
        ]
        result = calculate_t_strategy(rows, stock_context={"pe_ttm": 18, "amount": 3_000_000_000, "change_pct": 1.2})
        self.assertIn(result["suitability"], {"适合做T", "观察"})
        self.assertTrue(result["enterprise_gate"]["passed"])
        self.assertGreaterEqual(len(result["intraday_plan"]), 2)
        self.assertIn("support", result["levels"])

    def test_weak_enterprise_context_blocks_t_strategy(self):
        from app.t_strategy_engine import calculate_t_strategy

        rows = [{"time": "09:30", "price": 100, "volume": 1_000} for _ in range(20)]
        result = calculate_t_strategy(rows, stock_context={"pe_ttm": 180, "amount": 1_000_000, "change_pct": -8})
        self.assertFalse(result["enterprise_gate"]["passed"])
        self.assertEqual(result["suitability"], "不适合做T")


class TStrategyApiFrontendTests(unittest.TestCase):
    def test_endpoint_and_frontend_panel_exist(self):
        from fastapi.testclient import TestClient
        from app.main import app

        from app import main

        login = main.auth_service.login("laoma", "maguo591034")
        response = TestClient(app).get("/api/stocks/002463.SZ/t-strategy", headers={"Authorization": f"Bearer {login['token']}"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("enterprise_gate", payload)
        self.assertIn("intraday_plan", payload)
        app_js = Path(__file__).parents[1].joinpath("static", "app.js").read_text(encoding="utf-8")
        self.assertIn("t-strategy", app_js)
        self.assertIn("t-strategy-panel", app_js)


if __name__ == "__main__":
    unittest.main()
