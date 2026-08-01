import unittest

from fastapi.testclient import TestClient

from app import main
from app.data_provider import DemoDataProvider


class DecisionFusionTests(unittest.TestCase):
    def test_provider_builds_operational_fusion_board(self):
        provider = DemoDataProvider()
        user = {"id": 9911, "username": "fusion-user", "role": "member"}
        provider.user_next_day_plan = lambda current_user: {
            "score": 62,
            "stage": "结构试错",
            "stance": "只做确认后的低吸，不追高。",
            "focus_sectors": [{"name": "PCB", "strength": 86}],
            "watch_actions": [{"code": "002463.SZ", "name": "沪电股份", "action": "量化异动盯防", "priority": 92}],
            "forbidden_actions": ["早盘不追高"],
            "prep_checklist": ["检查公告与资金流"],
        }
        provider.user_quant_fund_radar = lambda current_user, limit=12: {
            "version": "3.0",
            "summary": {"scanned": 2, "high_count": 1, "top_score": 88, "tail_pressure": "高"},
            "tail_session": {"level": "高", "action": "14:00 后防守优先"},
            "top_alerts": [{"code": "002463.SZ", "name": "沪电股份", "suspicion_score": 88}],
        }
        provider.user_trading_action_queue = lambda current_user: {
            "summary": {"QUANT_WATCH": 1, "HOLD_CONFIRM": 1},
            "actions": [
                {"code": "002463.SZ", "name": "沪电股份", "label": "量化异动盯防", "priority": 92},
                {"code": "000997.SZ", "name": "新大陆", "label": "持有确认", "priority": 58},
            ],
        }
        provider.fullstack_data_toolkit = lambda: {"version": "3.1", "endpoint_count": 28, "connected_count": 14}

        fusion = provider.user_decision_fusion(user)

        self.assertEqual(fusion["version"], "1.0")
        self.assertEqual(fusion["mode"], "human_confirmed_decision")
        self.assertEqual(fusion["tomorrow"]["stage"], "结构试错")
        self.assertEqual(fusion["quant"]["top_score"], 88)
        self.assertEqual(fusion["data_matrix"]["toolkit_version"], "3.1")
        self.assertIn("回测验证", fusion["next_best_actions"][0])
        self.assertIn("不自动下单", fusion["guardrails"][0])

    def test_api_exposes_decision_fusion_board(self):
        client = TestClient(main.app)
        login = main.auth_service.login("laoma", "maguo591034")

        response = client.get(
            "/api/decision/fusion",
            headers={"Authorization": f"Bearer {login['token']}"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("tomorrow", payload)
        self.assertIn("quant", payload)
        self.assertIn("data_matrix", payload)
        self.assertIn("next_best_actions", payload)


if __name__ == "__main__":
    unittest.main()
