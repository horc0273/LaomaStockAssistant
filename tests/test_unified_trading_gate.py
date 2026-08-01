import unittest

from app.trading_gate import calculate_unified_gate


class UnifiedTradingGateTests(unittest.TestCase):
    def test_stale_data_blocks_new_buy_but_exposes_reason(self):
        gate = calculate_unified_gate(
            quality={"is_stale": True, "fallback_used": True, "quote_age_sec": 240},
            emotion={"composite_score": 55},
            quant_window={"risk": 40},
        )
        self.assertFalse(gate["allowed"])
        self.assertEqual(gate["action_cap"], "observe_only")
        self.assertTrue(any("数据" in reason for reason in gate["reasons"]))

    def test_normal_data_and_normal_emotion_stays_manual_confirm(self):
        gate = calculate_unified_gate(
            quality={"is_stale": False, "fallback_used": False, "quote_age_sec": 5},
            emotion={"composite_score": 62},
            quant_window={"risk": 44},
        )
        self.assertTrue(gate["allowed"])
        self.assertEqual(gate["action_cap"], "manual_confirm")


if __name__ == "__main__":
    unittest.main()
