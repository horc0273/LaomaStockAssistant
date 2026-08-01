import unittest

from fastapi.testclient import TestClient

from app import main
from app.data_provider import DemoDataProvider


class FullstackDataToolkitTests(unittest.TestCase):
    def test_provider_exposes_v31_seven_layer_data_matrix(self):
        provider = DemoDataProvider()
        toolkit = provider.fullstack_data_toolkit()

        self.assertEqual(toolkit["version"], "3.1")
        self.assertEqual(toolkit["layer_count"], 7)
        self.assertGreaterEqual(toolkit["endpoint_count"], 28)
        self.assertIn("去 akshare 依赖", toolkit["principles"][0])
        layer_keys = {layer["key"] for layer in toolkit["layers"]}
        self.assertIn("quote", layer_keys)
        self.assertIn("research", layer_keys)
        self.assertIn("signal", layer_keys)
        self.assertIn("capital", layer_keys)

    def test_toolkit_contains_video_reference_sources(self):
        provider = DemoDataProvider()
        toolkit = provider.fullstack_data_toolkit()
        endpoints = [endpoint for layer in toolkit["layers"] for endpoint in layer["endpoints"]]
        names = {endpoint["name"] for endpoint in endpoints}

        self.assertIn("mootdx K线/五档/逐笔", names)
        self.assertIn("东方财富 push2 个股资金", names)
        self.assertIn("龙虎榜席位", names)
        self.assertIn("限售解禁日历", names)
        self.assertIn("i问财语义研报", names)

    def test_health_api_includes_fullstack_toolkit(self):
        client = TestClient(main.app)
        login = main.auth_service.login("laoma", "maguo591034")

        response = client.get(
            "/api/data-sources/health",
            headers={"Authorization": f"Bearer {login['token']}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("fullstack_toolkit", payload)
        self.assertEqual(payload["fullstack_toolkit"]["version"], "3.1")
        self.assertGreaterEqual(payload["fullstack_toolkit"]["endpoint_count"], 28)


if __name__ == "__main__":
    unittest.main()
