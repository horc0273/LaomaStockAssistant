import unittest
from datetime import datetime

from app.data_provider import DemoDataProvider


class QuantControlRadarTests(unittest.TestCase):
    def test_identifies_late_day_quant_exit_window(self):
        provider = DemoDataProvider()

        radar = provider.quant_control_radar(now=datetime(2026, 7, 13, 14, 20))

        self.assertEqual(radar["current_window"]["key"], "tail_rebalance_watch")
        self.assertEqual(radar["current_window"]["stance"], "avoid_chasing")
        self.assertGreaterEqual(radar["risk_score"], 70)
        self.assertEqual(radar["automation_policy"]["max_mode"], "confirm_before_order")

    def test_recommends_observation_during_call_auction(self):
        provider = DemoDataProvider()

        radar = provider.quant_control_radar(now=datetime(2026, 7, 13, 9, 20))

        self.assertEqual(radar["current_window"]["key"], "call_auction")
        self.assertIn("不参与", radar["current_window"]["action"])


if __name__ == "__main__":
    unittest.main()
