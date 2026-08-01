from pathlib import Path
import shutil
import tempfile
import unittest

from app.ai_service import AIService
from app.auth_service import AuthService


ROOT = Path(__file__).resolve().parents[1]


class MemberManagementPersonalAITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="laoma-member-tests-"))
        self.auth = AuthService(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_admin_can_update_member_role_plan_phone_status_and_password(self):
        created = self.auth.create_user("friend01", "oldpass1", display_name="朋友A", phone="18600001111")
        user_id = created["user"]["id"]

        updated = self.auth.update_user(
            user_id,
            display_name="朋友A-正式会员",
            phone="18600002222",
            role="analyst",
            plan="pro",
            days=90,
            is_active=False,
            password="newpass1",
        )

        self.assertTrue(updated["ok"])
        self.assertEqual(updated["user"]["display_name"], "朋友A-正式会员")
        self.assertEqual(updated["user"]["phone"], "18600002222")
        self.assertEqual(updated["user"]["role"], "analyst")
        self.assertEqual(updated["user"]["plan"], "pro")
        self.assertFalse(updated["user"]["is_active"])
        self.assertIsNone(self.auth.login("18600002222", "newpass1"))

        reenabled = self.auth.update_user(user_id, is_active=True)
        self.assertTrue(reenabled["user"]["is_active"])
        self.assertIsNotNone(self.auth.login("18600002222", "newpass1"))

    def test_member_ai_config_file_is_isolated_from_system_ai_config(self):
        system = AIService(self.temp_dir)
        system.save_config(
            enabled=True,
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key="admin-system-key",
            profile_id="system-deepseek",
            profile_name="系统 DeepSeek",
        )

        personal_path = self.temp_dir / "user_ai_configs" / "user_2.json"
        member = AIService.for_personal_config(personal_path)
        member.save_config(
            enabled=True,
            provider="openrouter",
            base_url="https://openrouter.ai/api/v1",
            model="deepseek/deepseek-chat-v3-0324",
            api_key="member-own-key",
            profile_id="member-openrouter",
            profile_name="会员自己的 OpenRouter",
        )

        self.assertEqual(system.public_config()["active_profile_id"], "system-deepseek")
        self.assertEqual(member.public_config()["active_profile_id"], "member-openrouter")
        self.assertIn("member-own-key", personal_path.read_text(encoding="utf-8"))
        self.assertNotIn("admin-system-key", personal_path.read_text(encoding="utf-8"))


class FrontendMemberManagementMobileTests(unittest.TestCase):
    def test_frontend_exposes_admin_member_management_and_personal_ai_copy(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-view="admin"', html)
        self.assertIn('id="adminMemberTable"', html)
        self.assertIn("/api/admin/users", js)
        self.assertIn("renderAdminMembers", js)
        self.assertIn("个人模型配置", html + js)
        self.assertIn("config_scope", js)

    def test_phone_css_has_compact_single_column_layout(self):
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("body.mobile-ready", css)
        self.assertIn(".admin-member-grid", css)
        self.assertIn("table", css)

    def test_quant_upgrade_plan_is_visible_in_research_center(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("量化升级路线图", html)
        self.assertIn('id="quantUpgradePlan"', html)
        self.assertIn("/api/research/quant-upgrade-plan", js)
        self.assertIn("renderQuantUpgradePlan", js)


if __name__ == "__main__":
    unittest.main()
