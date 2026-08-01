from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendLoadingResilienceTests(unittest.TestCase):
    def test_batch_loading_has_per_module_fallback_and_review_retry(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("async function safeApiJson", js)
        self.assertIn("safeApiJson('/api/review/daily'", js)
        self.assertIn("function safeRender", js)
        self.assertIn("data-retry-daily-review", js)


if __name__ == "__main__":
    unittest.main()
