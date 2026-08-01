import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider
from app.risk_engine import calculate_dynamic_risk


ROOT = Path(__file__).resolve().parents[1]


class DynamicRiskUnitTests(unittest.TestCase):
    def test_dynamic_risk_expands_stop_and_reduces_position_when_volatility_rises(self):
        calm = calculate_dynamic_risk(price=100, volatility_pct=1.5)
        volatile = calculate_dynamic_risk(price=100, volatility_pct=8.0)

        self.assertLess(calm["stop_loss_pct"], volatile["stop_loss_pct"])
        self.assertGreater(calm["max_position_pct"], volatile["max_position_pct"])
        self.assertGreater(volatile["invalidation_price"], 0)
        self.assertIn(volatile["risk_level"], {"medium", "high"})


class SecondBatchApiTests(unittest.TestCase):
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

    def tearDown(self):
        self.client.close()
        main.provider = self.original_provider
        main.auth_service = self.original_auth_service
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        try:
            self.temp_dir.cleanup()
        except PermissionError:
            pass

    def test_dynamic_risk_endpoint_returns_explainable_thresholds(self):
        response = self.client.get("/api/risk/dynamic?code=002463.SZ", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("thresholds", payload)
        self.assertIn("stop_loss_pct", payload["thresholds"])
        self.assertIn("volatility_pct", payload["thresholds"])
        self.assertIn("source", payload)

    def test_sse_once_endpoint_returns_market_event(self):
        response = self.client.get("/api/events/stream?once=1", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        self.assertIn("event: market", response.text)
        self.assertIn("data:", response.text)
        json.loads(response.text.split("data:", 1)[1].split("\n", 1)[0].strip())

    def test_ea_simulation_state_endpoint_exposes_safe_transition(self):
        response = self.client.get("/api/trading/ea-simulation", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("workflow", payload)
        self.assertEqual(payload["workflow"], ["paper", "review", "approved"])


class SecondBatchFrontendTests(unittest.TestCase):
    def test_frontend_wires_sse_dynamic_risk_and_ea_workflow(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("/api/events/stream", js)
        self.assertIn("EventSource", js)
        self.assertIn("/api/risk/dynamic", js)
        self.assertIn("paper-review-approved", html + js)
        self.assertIn("@media (max-width: 640px)", css)


if __name__ == "__main__":
    unittest.main()
