import tempfile
import unittest

from app.data_provider import DemoDataProvider


class ReviewCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = None

    def tearDown(self):
        self.temp_dir.cleanup()

    def build_provider(self):
        import os

        self.old_data_dir = os.environ.get("LAOMA_STOCK_DATA_DIR")
        os.environ["LAOMA_STOCK_DATA_DIR"] = self.temp_dir.name
        provider = DemoDataProvider()
        if self.old_data_dir is None:
            os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
        else:
            os.environ["LAOMA_STOCK_DATA_DIR"] = self.old_data_dir
        return provider

    def test_daily_review_bundle_contains_market_watchlist_and_observation_sections(self):
        provider = self.build_provider()
        user = {"id": 1, "username": "laoma"}

        review = provider.user_daily_review(user)

        self.assertIn("review_date", review)
        self.assertIn("market_review", review)
        self.assertIn("watchlist_review", review)
        self.assertIn("observation_pool", review)
        self.assertIn("next_day_plan", review)
        self.assertIn("history", review)
        self.assertTrue(review["market_review"]["headline"])
        self.assertEqual(len(review["market_review"]["key_signals"]), 4)
        self.assertTrue(review["market_review"]["news_feed"])
        self.assertIn("intelligence", review["market_review"])
        self.assertIn("announcements", review["market_review"]["intelligence"])
        self.assertIn("research_reports", review["market_review"]["intelligence"])
        self.assertIn("by_stock", review["market_review"]["intelligence"])
        self.assertTrue(review["market_review"]["intelligence"]["announcements"])
        self.assertTrue(review["market_review"]["intelligence"]["research_reports"])
        self.assertTrue(review["market_review"]["intelligence"]["by_stock"])
        first_intel = review["market_review"]["intelligence"]["by_stock"][0]
        self.assertIn("code", first_intel)
        self.assertIn("name", first_intel)
        self.assertIn("announcement_count", first_intel)
        self.assertIn("research_count", first_intel)
        self.assertIn("latest_date", first_intel)
        self.assertTrue(review["watchlist_review"]["items"])
        self.assertIn("history_summary", review["watchlist_review"])
        self.assertLessEqual(len(review["observation_pool"]["items"]), 10)
        self.assertIn("stage", review["next_day_plan"])
        self.assertIn("watch_actions", review["next_day_plan"])
        self.assertIn("focus_sectors", review["next_day_plan"])
        self.assertIn("forbidden_actions", review["next_day_plan"])
        self.assertTrue(review["next_day_plan"]["prep_checklist"])

    def test_daily_review_is_filtered_by_current_user_watchlist(self):
        provider = self.build_provider()
        user = {"id": 2, "username": "demo"}
        provider.add_user_watchlist(user, "002463.SZ")

        review = provider.user_daily_review(user)

        self.assertEqual([item["code"] for item in review["watchlist_review"]["items"]], ["002463.SZ"])
        self.assertEqual(review["watchlist_review"]["scope"], "current_user_watchlist")

    def test_review_history_is_saved_and_isolated_by_user(self):
        provider = self.build_provider()
        user_a = {"id": 1, "username": "laoma"}
        user_b = {"id": 2, "username": "demo"}

        saved_id = provider.save_user_daily_review(user_a, {"title": "2026-06-30 复盘", "summary": "AI算力主线继续活跃"})

        self.assertTrue(saved_id)
        self.assertEqual(len(provider.list_user_daily_reviews(user_a, limit=10)), 1)
        self.assertEqual(provider.list_user_daily_reviews(user_b, limit=10), [])

    def test_daily_review_can_be_exported_to_markdown(self):
        provider = self.build_provider()
        user = {"id": 1, "username": "laoma"}

        review = provider.user_daily_review(user)
        markdown = provider.daily_review_markdown(review)

        self.assertIn("# ", markdown)
        self.assertIn("## 市场总览", markdown)
        self.assertIn("## 自选股复盘", markdown)
        self.assertIn("## 公告与研报跟踪", markdown)
        self.assertIn("## 明日观察池", markdown)

        self.assertIn("## 明日预判", markdown)

if __name__ == "__main__":
    unittest.main()
