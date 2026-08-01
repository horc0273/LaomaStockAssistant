import unittest
from datetime import datetime

from app.backtest_service import BacktestService
from app.data_provider import DemoDataProvider


class ChineseCopyQualityTests(unittest.TestCase):
    def assert_readable_chinese(self, text: str):
        self.assertNotIn("????", text)
        self.assertNotIn("锟", text)
        self.assertNotIn("鐩", text)
        self.assertNotIn("鍙", text)
        self.assertRegex(text, r"[\u4e00-\u9fff]{2,}")

    def test_quant_control_radar_uses_readable_chinese(self):
        provider = DemoDataProvider()

        radar = provider.quant_control_radar(now=datetime(2026, 7, 13, 9, 20))

        self.assert_readable_chinese(radar["current_window"]["name"])
        self.assert_readable_chinese(radar["current_window"]["action"])
        self.assertIn("不参与", radar["current_window"]["action"])
        self.assert_readable_chinese(radar["automation_policy"]["reason"])

    def test_backtest_service_user_messages_are_readable(self):
        result = BacktestService().run([{"date": "2026-01-01", "close": 10, "open": 10}])

        self.assertEqual(result["error"], "insufficient_history")
        self.assert_readable_chinese(result["message"])
        self.assertIn("历史数据不足", result["message"])


if __name__ == "__main__":
    unittest.main()
