import tempfile
import unittest
from pathlib import Path

from app.ai_service import AIService
from app.models import Candidate, MarketIndex, MarketOverview, ModelSignal, Stock, WatchlistItem
from app.tushare_service import TushareService


class AIResearchReportTests(unittest.TestCase):
    def test_external_prompt_keeps_fact_rules_when_style_is_selected(self):
        service = AIService(Path(tempfile.mkdtemp()))
        captured = {}

        def fake_request(base_url, api_key, body, timeout=30):
            captured.update(body)
            return {"choices": [{"message": {"content": '{"summary":"ok","data_audit":[]}'}}]}

        service._request_chat = fake_request
        result = service._call_external_ai(
            {"market_intelligence": {"tool_audit": []}},
            {"id": "deepseek", "provider": "deepseek", "base_url": "https://api.example/v1", "api_key": "secret", "model": "deepseek-chat"},
            system_prompt="重点观察短线量价",
            question="分析沪电股份",
        )
        prompt = captured["messages"][0]["content"]
        self.assertIn("绝不补写", prompt)
        self.assertIn("data_audit", prompt)
        self.assertIn("重点观察短线量价", prompt)
        self.assertEqual(captured["max_tokens"], 7000)
        self.assertEqual(result["mode"], "api")

    def test_external_prompt_includes_strategy_mode_contract(self):
        service = AIService(Path(tempfile.mkdtemp()))
        captured = {}

        def fake_request(base_url, api_key, body, timeout=30):
            captured.update(body)
            return {"choices": [{"message": {"content": '{"summary":"ok","data_audit":[],"decision_score":{"overall":78}}'}}]}

        service._request_chat = fake_request
        result = service._call_external_ai(
            {"market_intelligence": {"tool_audit": []}},
            {"id": "deepseek", "provider": "deepseek", "base_url": "https://api.example/v1", "api_key": "secret", "model": "deepseek-chat"},
            system_prompt="偏短线交易节奏",
            question="分析沪电股份",
            analysis_mode="breakout_hunter",
        )
        prompt = captured["messages"][0]["content"]
        self.assertIn("breakout_hunter", prompt)
        self.assertIn("decision_score", prompt)
        self.assertIn("execution_checklist", prompt)
        self.assertEqual(result["analysis_mode"], "breakout_hunter")

    def test_external_prompt_marks_ai_as_research_assistant_and_requires_pitfall_checks(self):
        service = AIService(Path(tempfile.mkdtemp()))
        captured = {}

        def fake_request(base_url, api_key, body, timeout=30):
            captured.update(body)
            return {"choices": [{"message": {"content": '{"summary":"ok","data_audit":[]}'}}]}

        service._request_chat = fake_request
        service._call_external_ai(
            {"market_intelligence": {"tool_audit": []}},
            {"id": "deepseek", "provider": "deepseek", "base_url": "https://api.example/v1", "api_key": "secret", "model": "deepseek-chat"},
            system_prompt="研究优先",
            question="分析沪电股份",
        )
        prompt = captured["messages"][0]["content"]
        self.assertIn("研究助手", prompt)
        self.assertIn("证据还是结论", prompt)
        self.assertIn("数据来源", prompt)
        self.assertIn("风险提示", prompt)
        self.assertIn("收益承诺", prompt)

    def test_local_analysis_returns_decision_report_fields(self):
        service = AIService(Path(tempfile.mkdtemp()))
        stock = Stock(
            market="SZ",
            code="002463.SZ",
            name="沪电股份",
            price=147.9,
            change_pct=3.2,
            cost=138.0,
            quantity=500,
            source="unit-test",
            tag="PCB",
            alert_price=150,
            alert_pct=3,
            take_profit=165,
            stop_loss=136,
            ai="测试",
        )
        item = WatchlistItem(stock=stock, quantity=500, pnl_pct=7.17, pnl_amount=4950, daily_pnl_amount=800)
        candidate = Candidate(
            stock=stock,
            market_state="偏强",
            signals=[
                ModelSignal(name="放量突破", status="触发", score=82),
                ModelSignal(name="多头排列", status="增强", score=78),
            ],
            sector_strength=78,
            fund_strength=75,
            risk_penalty=8,
            total_score=82,
            action="BUY",
            confidence=80,
            recommendation="强观察",
            reason="量价与板块共振",
        )
        market = MarketOverview(
            source_note="unit-test",
            updated_at="2026-07-02 10:30:00",
            indices=[MarketIndex(name="上证指数", code="000001.SH", price=3200, change_pct=0.8, market="CN")],
            up_count=3120,
            down_count=1680,
            limit_up=72,
            limit_down=4,
            turnover_billion=12345,
            mood="偏强",
            themes=["AI硬件", "PCB"],
        )
        result = service._local_analysis(
            item,
            candidate,
            market,
            [{"name": "PCB", "strength": 78, "fund_flow": "净流入 12 亿"}],
            [{"title": "AI 服务器订单预期升温", "symbols": ["002463.SZ"]}],
            analysis_mode="trend_following",
        )
        self.assertEqual(result["analysis_mode"], "trend_following")
        self.assertIn("decision_score", result)
        self.assertIn("execution_checklist", result)
        self.assertIn("catalyst_watch", result)
        self.assertGreaterEqual(result["decision_score"]["overall"], 70)
        self.assertTrue(result["execution_checklist"])

    def test_local_analysis_returns_role_and_pitfall_checklist(self):
        service = AIService(Path(tempfile.mkdtemp()))
        stock = Stock(
            market="SZ",
            code="002463.SZ",
            name="沪电股份",
            price=147.9,
            change_pct=3.2,
            cost=138.0,
            quantity=500,
            source="unit-test",
            tag="PCB",
            alert_price=150,
            alert_pct=3,
            take_profit=165,
            stop_loss=136,
            ai="测试",
        )
        item = WatchlistItem(stock=stock, quantity=500, pnl_pct=7.17, pnl_amount=4950, daily_pnl_amount=800)
        candidate = Candidate(
            stock=stock,
            market_state="偏强",
            signals=[ModelSignal(name="放量突破", status="触发", score=82)],
            sector_strength=78,
            fund_strength=75,
            risk_penalty=8,
            total_score=82,
            action="BUY",
            confidence=80,
            recommendation="强观察",
            reason="量价与板块共振",
        )
        market = MarketOverview(
            source_note="unit-test",
            updated_at="2026-07-02 10:30:00",
            indices=[MarketIndex(name="上证指数", code="000001.SH", price=3200, change_pct=0.8, market="CN")],
            up_count=3120,
            down_count=1680,
            limit_up=72,
            limit_down=4,
            turnover_billion=12345,
            mood="偏强",
            themes=["AI硬件", "PCB"],
        )
        result = service._local_analysis(item, candidate, market, [], [], analysis_mode="decision_report")
        self.assertIn("assistant_role", result)
        self.assertIn("pitfall_checks", result)
        self.assertTrue(result["assistant_role"]["title"].startswith("AI"))
        self.assertEqual(len(result["pitfall_checks"]), 4)
        self.assertNotIn("????", str(result["assistant_role"]))
        self.assertNotIn("????", str(result["pitfall_checks"]))
        self.assertEqual(result["assistant_role"]["title"], "AI研究助手")
        self.assertIn("数据来源清不清晰？", [item["question"] for item in result["pitfall_checks"]])

    def test_analysis_bundle_caps_rows_and_keeps_each_dataset_status(self):
        service = TushareService(Path(tempfile.mkdtemp()) / "token")

        def fake_query(api_name, params=None, fields="", ttl=600):
            return {"ok": True, "source": f"tushare:{api_name}", "rows": [{"index": i} for i in range(30)]}

        service.query = fake_query
        bundle = service.analysis_bundle("002463")
        self.assertEqual(len(bundle["company_profile"]["rows"]), 1)
        self.assertEqual(len(bundle["financial_indicators"]["rows"]), 8)
        self.assertEqual(len(bundle["holder_numbers"]["rows"]), 12)
        self.assertEqual(len(bundle["valuation"]["rows"]), 20)


if __name__ == "__main__":
    unittest.main()
