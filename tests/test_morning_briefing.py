import unittest

from app.data_provider import DemoDataProvider


class MorningBriefingTests(unittest.TestCase):
    def test_briefing_has_external_context_and_conservative_disclaimer(self):
        briefing = DemoDataProvider().morning_briefing()
        self.assertIn("external_indices", briefing)
        self.assertIn("auction_window", briefing)
        self.assertIn("A股集合竞价", briefing["source_note"])
        self.assertIn(briefing["level"], {"warning", "watch", "neutral"})


if __name__ == "__main__":
    unittest.main()
