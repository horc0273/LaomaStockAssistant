from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MobileDashboardFrontendTests(unittest.TestCase):
    def test_mobile_dashboard_markup_exists(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="mobileDashboard"', html)
        self.assertIn('id="mobileMarketMoodCard"', html)
        self.assertIn('id="mobileAccessCard"', html)
        self.assertIn('id="mobileQuantControlCard"', html)
        self.assertIn('id="quantControlPanel"', html)
        self.assertIn('id="mobileBottomTabs"', html)

    def test_mobile_dashboard_script_uses_mobile_api(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("/api/mobile/dashboard", js)
        self.assertIn("renderMobileDashboard", js)
        self.assertIn("loadMobileDashboard", js)
        self.assertIn("mobileAccessContent", js)
        self.assertIn("data-copy-access", js)
        self.assertIn("mobileQuantControlContent", js)
        self.assertIn("renderQuantControl", js)

    def test_stock_tool_exposes_technical_fund_analysis(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("K线资金分析", html + js)
        self.assertIn("/technical-fund-analysis", js)
        self.assertIn("renderTechnicalFundAnalysis", js)
        self.assertIn("renderThreeSourceProfile", js)
        self.assertIn("/three-source-profile", js)
        self.assertIn("三源数据", html + js)
        self.assertIn("资金事件", html + js)
        self.assertIn("/capital-events", js)
        self.assertIn("renderCapitalEvents", js)
        self.assertIn("fullstack_toolkit", js)
        self.assertIn("A股全栈数据工具包", js)
        self.assertIn("renderQuantFundRadar", js)
        self.assertIn("quant_fund_radar", js)
        self.assertIn("tail_session", js)
        self.assertIn("板块联动", js)
        self.assertIn("dominant_tags", js)
        self.assertIn("量化嫌疑", js)

    def test_dashboard_exposes_decision_fusion_panel(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="decisionFusionPanel"', html)
        self.assertIn("/api/decision/fusion", js)
        self.assertIn("renderDecisionFusion", js)
        self.assertIn("决策融合", html + js)


if __name__ == "__main__":
    unittest.main()
