from pathlib import Path
import unittest

from app.data_provider import DemoDataProvider


ROOT = Path(__file__).resolve().parents[1]


class EASimulationBackendTests(unittest.TestCase):
    def test_ea_simulation_runs_only_paper_orders_with_risk_gate(self):
        provider = DemoDataProvider()
        user = {"id": 9001, "username": "ea_tester", "display_name": "EA测试", "role": "member", "plan": "trial"}
        provider.add_user_watchlist(user, "002463.SZ")

        result = provider.run_user_ea_simulation(user, strategy_id="anti_quant_tail", max_orders=3)

        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "paper_only")
        self.assertIn("绝不自动实盘", result["safety_policy"])
        self.assertLessEqual(len(result["orders"]), 3)
        for order in result["orders"]:
            self.assertEqual(order["mode"], "paper")
            self.assertEqual(order["status"], "ea_simulated")
            self.assertIn("strategy_id", order)
            self.assertIn("risk_gate", order)


class EASimulationFrontendTests(unittest.TestCase):
    def test_trading_page_exposes_ea_simulation_panel(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="eaSimulationPanel"', html)
        self.assertIn("EA模拟盘", html + js)
        self.assertIn("/api/trading/ea-simulation", js)
        self.assertIn("runEaSimulation", js)
        self.assertIn("renderEaSimulation", js)
        self.assertIn("只模拟，不实盘", html + js)


if __name__ == "__main__":
    unittest.main()
