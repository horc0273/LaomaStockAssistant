import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import main
from app.data_provider import DemoDataProvider


class CapitalEventDataTests(unittest.TestCase):
    def test_provider_returns_five_capital_event_sections(self):
        provider = DemoDataProvider()
        calls: list[str] = []

        def fake_dataset(report_name, filter_text, sort_columns, limit):
            calls.append(report_name)
            return {
                "ok": True,
                "source": f"eastmoney:{report_name}",
                "updated_at": "2026-07-13T10:00:00",
                "rows": [{"SECURITY_CODE": "002463", "SECURITY_NAME_ABBR": "沪电股份", "VALUE": 1}],
            }

        provider.intelligence._eastmoney_dataset = fake_dataset

        result = provider.stock_capital_events("002463.SZ", limit=6)

        self.assertEqual(result["code"], "002463.SZ")
        self.assertEqual(result["source"], "eastmoney-datacenter-web")
        self.assertEqual(
            set(result["sections"].keys()),
            {"dragon_tiger", "restricted_release", "margin_trading", "block_trade", "holder_change"},
        )
        self.assertTrue(all(section["ok"] for section in result["sections"].values()))
        self.assertIn("RPT_DAILYBILLBOARD_DETAILS", calls)
        self.assertIn("RPT_LIFT_STAGE", calls)
        self.assertIn("RPTA_WEB_RZRQ_GGMX", calls)
        self.assertIn("RPT_BLOCKTRADE_STA", calls)
        self.assertIn("RPT_HOLDERNUM_DET", calls)

    def test_api_exposes_capital_events(self):
        client = TestClient(main.app)
        login = main.auth_service.login("laoma", "maguo591034")

        response = client.get(
            "/api/stocks/002463.SZ/capital-events?limit=3",
            headers={"Authorization": f"Bearer {login['token']}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], "002463.SZ")
        self.assertIn("sections", payload)
        self.assertIn("dragon_tiger", payload["sections"])

    def test_frontend_requests_today_by_default(self):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("capital-events?limit=12&window=today", script)

    def test_today_window_filters_old_capital_events(self):
        provider = DemoDataProvider()

        def fake_dataset(report_name, filter_text, sort_columns, limit):
            return {
                "ok": True,
                "source": f"eastmoney:{report_name}",
                "updated_at": "2026-07-19T10:00:00",
                "rows": [
                    {"SECURITY_CODE": "002463", "SECURITY_NAME_ABBR": "测试", "TRADE_DATE": date.today().isoformat()},
                    {"SECURITY_CODE": "002463", "SECURITY_NAME_ABBR": "测试", "TRADE_DATE": (date.today() - timedelta(days=20)).isoformat()},
                ],
            }

        provider.intelligence._eastmoney_dataset = fake_dataset
        result = provider.stock_capital_events("002463.SZ", limit=6, window="today")

        self.assertEqual(result["window"], "today")
        for section in result["sections"].values():
            self.assertEqual(section["count"], 1)
            self.assertEqual(section["items"][0]["date"], date.today().isoformat())

    def test_recent_window_keeps_last_five_days_and_reports_latest_date(self):
        provider = DemoDataProvider()

        def fake_dataset(report_name, filter_text, sort_columns, limit):
            return {
                "ok": True,
                "source": "eastmoney",
                "rows": [
                    {"SECURITY_CODE": "002463", "TRADE_DATE": (date.today() - timedelta(days=2)).isoformat()},
                    {"SECURITY_CODE": "002463", "TRADE_DATE": (date.today() - timedelta(days=20)).isoformat()},
                ],
            }

        provider.intelligence._eastmoney_dataset = fake_dataset
        result = provider.stock_capital_events("002463.SZ", limit=6, window="recent")

        self.assertEqual(result["window"], "recent")
        self.assertTrue(all(section["count"] == 1 for section in result["sections"].values()))
        self.assertIn("latest_available_date", result)


if __name__ == "__main__":
    unittest.main()
