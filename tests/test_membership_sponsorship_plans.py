import gc
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main
from app.auth_service import AuthService
from app.data_provider import DemoDataProvider


ROOT = Path(__file__).resolve().parents[1]


class MembershipSponsorshipPlanTests(unittest.TestCase):
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
        if hasattr(self, "client"):
            self.client.close()
        main.provider = self.original_provider
        main.auth_service = self.original_auth_service
        self.client = None
        self.provider = None
        self.auth_service = None
        gc.collect()
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        self.temp_dir.cleanup()

    def test_membership_plan_catalog_defines_trial_paid_and_founder_tiers(self):
        response = self.client.get("/api/membership/plans", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        tier_ids = [tier["id"] for tier in payload["tiers"]]
        self.assertEqual(tier_ids, ["trial", "supporter", "pro", "sponsor", "founder"])
        self.assertEqual(payload["default_trial_days"], 14)
        self.assertIn("不承诺收益", " ".join(payload["rules"]))

        supporter = next(tier for tier in payload["tiers"] if tier["id"] == "supporter")
        pro = next(tier for tier in payload["tiers"] if tier["id"] == "pro")
        trial = next(tier for tier in payload["tiers"] if tier["id"] == "trial")
        founder = next(tier for tier in payload["tiers"] if tier["id"] == "founder")

        self.assertEqual(supporter["price_month"], 9.9)
        self.assertEqual(pro["price_year"], 199)
        self.assertTrue(supporter["features"]["personal_ai_key"])
        self.assertFalse(trial["features"]["advanced_quant_radar"])
        self.assertTrue(pro["features"]["advanced_quant_radar"])
        self.assertTrue(founder["features"]["admin_console"])

    def test_phone_registration_uses_short_trial_sponsorship_period(self):
        response = self.client.post(
            "/api/auth/register",
            json={"phone": "13900139000", "password": "friend123", "display_name": "试用朋友"},
        )

        self.assertEqual(response.status_code, 200)
        user = response.json()["user"]
        self.assertEqual(user["plan"], "trial")
        self.assertEqual(user["membership"]["tier_id"], "trial")
        self.assertLessEqual(user["membership"]["days_remaining"], 14)
        self.assertGreaterEqual(user["membership"]["days_remaining"], 13)

    def test_admin_member_payload_includes_membership_summary(self):
        created = self.auth_service.create_user(
            "friend_sponsor",
            "friend123",
            display_name="赞助朋友",
            phone="13900139001",
            plan="supporter",
            days=90,
        )

        self.assertEqual(created["user"]["membership"]["tier_id"], "supporter")
        self.assertTrue(created["user"]["membership"]["features"]["personal_ai_key"])
        self.assertFalse(created["user"]["membership"]["features"]["admin_console"])


class MembershipSponsorshipFrontendTests(unittest.TestCase):
    def test_frontend_exposes_sponsorship_plan_panel_and_admin_plan_select(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="membershipPlanPanel"', html)
        self.assertIn('id="adminNewPlan"', html)
        self.assertIn('<select id="adminNewPlan"', html)
        self.assertIn("/api/membership/plans", js)
        self.assertIn("renderMembershipPlans", js)
        self.assertIn("membershipFeatureGate", js)
        self.assertIn("membership-tier-card", css)


if __name__ == "__main__":
    unittest.main()
