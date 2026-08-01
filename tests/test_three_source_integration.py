import unittest

from fastapi.testclient import TestClient

from app import main
from app.data_provider import DemoDataProvider


class ThreeSourceIntegrationTests(unittest.TestCase):
    def test_provider_builds_eastmoney_xueqiu_tongdaxin_profile(self):
        provider = DemoDataProvider()
        profile = provider.three_source_profile("002463.SZ")

        self.assertEqual(profile["code"], "002463.SZ")
        self.assertEqual(profile["version"], "1.0")
        self.assertEqual({item["key"] for item in profile["sources"]}, {"eastmoney", "xueqiu", "tongdaxin"})
        self.assertIn("quote", profile["eastmoney"])
        self.assertIn("deep_link", profile["xueqiu"])
        self.assertIn("indicators", profile["tongdaxin"])
        self.assertIn("AI分析使用", profile["fusion"]["usage"])

    def test_data_source_health_exposes_three_tool_roles(self):
        provider = DemoDataProvider()
        roles = provider.trading_tool_data_sources()

        self.assertEqual([item["key"] for item in roles], ["eastmoney", "xueqiu", "tongdaxin"])
        self.assertEqual(roles[0]["status"], "connected")
        self.assertIn("社区", roles[1]["role"])
        self.assertIn("公式", roles[2]["role"])

    def test_api_returns_three_source_profile(self):
        client = TestClient(main.app)
        login = main.auth_service.login("laoma", "maguo591034")
        response = client.get(
            "/api/stocks/002463.SZ/three-source-profile",
            headers={"Authorization": f"Bearer {login['token']}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], "002463.SZ")
        self.assertIn("xueqiu", payload)
        self.assertIn("tongdaxin", payload)


if __name__ == "__main__":
    unittest.main()
