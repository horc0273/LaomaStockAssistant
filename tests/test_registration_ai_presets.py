import os
import gc
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


ROOT = Path(__file__).resolve().parents[1]


class RegistrationAndAiPresetTests(unittest.TestCase):
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

    def tearDown(self):
        if hasattr(self, "client"):
            self.client.close()
        self.client = None
        self.provider = None
        self.auth_service = None
        gc.collect()
        main.provider = self.original_provider
        main.auth_service = self.original_auth_service
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        self.temp_dir.cleanup()

    def test_public_phone_registration_creates_login_ready_trial_user(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "phone": "13800138000",
                "password": "friend123",
                "display_name": "老马朋友",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["phone"], "13800138000")
        self.assertEqual(payload["user"]["role"], "member")
        login = self.auth_service.login("13800138000", "friend123")
        self.assertIsNotNone(login)

    def test_login_page_has_phone_registration_entry(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="registerForm"', html)
        self.assertIn('id="registerPhone"', html)
        self.assertIn("/api/auth/register", js)
        self.assertIn("手机注册", html + js)

    def test_ai_config_adds_mainstream_openai_compatible_presets(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        for text in ["硅基流动", "智谱AI", "火山引擎", "阿里云百炼", "Moonshot", "腾讯混元", "MiniMax", "OpenRouter", "Ollama", "Azure OpenAI"]:
            self.assertIn(text, html + js)


if __name__ == "__main__":
    unittest.main()
