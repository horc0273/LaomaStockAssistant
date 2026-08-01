from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import datetime

from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


ROOT = Path(__file__).resolve().parents[1]


class AdminVisibilityAndAllDayDataTests(unittest.TestCase):
    def test_default_laoma_account_is_admin_and_founder(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="laoma-admin-test-"))
        try:
            service = AuthService(temp_dir)
            users = service.list_users()
            laoma = next(user for user in users if user["username"] == "laoma")

            self.assertEqual(laoma["role"], "admin")
            self.assertEqual(laoma["plan"], "founder")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_member_management_nav_is_not_hidden_by_default(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-view="admin"', html)
        self.assertNotIn('class="nav admin-only hidden" data-view="admin"', html)
        self.assertIn("会员管理", html)

    def test_api_json_reports_internal_server_error_as_readable_message(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("response.text()", js)
        self.assertIn("HTTP ${response.status}", js)
        self.assertIn("Internal Server Error", js)

    def test_quant_radar_treats_auction_as_live_data_window(self):
        radar = DemoDataProvider().quant_control_radar(now=datetime(2026, 7, 16, 9, 20))

        self.assertEqual(radar["current_window"]["key"], "call_auction")
        self.assertEqual(radar["data_policy"]["mode"], "all_day")
        self.assertEqual(radar["data_policy"]["quote_window"], "09:15-15:00")
        self.assertTrue(radar["data_policy"]["allow_call_auction"])

    def test_quant_radar_has_premarket_and_aftermarket_data_modes(self):
        provider = DemoDataProvider()
        pre = provider.quant_control_radar(now=datetime(2026, 7, 16, 8, 55))
        after = provider.quant_control_radar(now=datetime(2026, 7, 16, 18, 0))

        self.assertEqual(pre["current_window"]["key"], "pre_market_prepare")
        self.assertEqual(after["current_window"]["key"], "after_market_review")
        self.assertEqual(pre["data_policy"]["mode"], "all_day")
        self.assertEqual(after["data_policy"]["mode"], "all_day")


if __name__ == "__main__":
    unittest.main()
