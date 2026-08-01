import unittest
from pathlib import Path

from app.auth_service import membership_plan_catalog


class PrivateDomainMembershipTests(unittest.TestCase):
    def test_catalog_contains_private_contact_and_limited_launch_rules(self):
        catalog = membership_plan_catalog()
        self.assertIn("private_contact", catalog)
        self.assertTrue(catalog["private_contact"]["enabled"])
        self.assertIn("qr_path", catalog["private_contact"])
        self.assertTrue(catalog["admin_activation"])

    def test_membership_page_renders_qr_and_private_domain_cta(self):
        app_js = Path(__file__).parents[1].joinpath("static", "app.js").read_text(encoding="utf-8")
        self.assertIn("membership-private-contact", app_js)
        self.assertIn("private_contact", app_js)
        self.assertIn("private-contact-qr.png", app_js)


if __name__ == "__main__":
    unittest.main()
