from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiCopyIntegrityTests(unittest.TestCase):
    def test_research_center_intro_copy_has_no_placeholder_question_marks(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        research_slice = html.split('<section id="research" class="view">', 1)[1].split('<div class="panel">', 2)[1]

        self.assertNotIn("????", research_slice)
        self.assertIn("研究工作台", research_slice)

    def test_action_queue_copy_has_no_placeholder_question_marks(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        action_queue_slice = js.split("function renderActionQueue(data) {", 1)[1].split("const summary = data.summary || {};", 1)[0]

        self.assertNotIn("????", action_queue_slice)
        self.assertIn("交易前四问", action_queue_slice)

    def test_recommendation_validation_copy_has_no_placeholder_question_marks(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        validation_slice = js.split("async function loadRecommendationValidation() {", 1)[1].split("$('#recommendationValidation').innerHTML", 1)[0]

        self.assertNotIn("????", validation_slice)
        self.assertIn("推荐逻辑是否一致？", validation_slice)


if __name__ == "__main__":
    unittest.main()
