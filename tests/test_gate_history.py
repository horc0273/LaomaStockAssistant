import os
import tempfile
import unittest

from app.data_provider import DemoDataProvider


class GateHistoryTests(unittest.TestCase):
    def test_gate_decision_history_is_persisted_and_capped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old = os.environ.get("LAOMA_STOCK_DATA_DIR")
            os.environ["LAOMA_STOCK_DATA_DIR"] = temp_dir
            try:
                provider = DemoDataProvider()
                user = {"id": 9, "username": "tester"}
                gate = {"allowed": False, "status": "blocked", "reasons": ["行情数据过期"], "action_cap": "observe_only"}
                provider.record_unified_gate_event(user, gate, context="test")
                rows = provider.unified_gate_history(user)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["context"], "test")
                self.assertFalse(rows[0]["allowed"])
            finally:
                if old is None:
                    os.environ.pop("LAOMA_STOCK_DATA_DIR", None)
                else:
                    os.environ["LAOMA_STOCK_DATA_DIR"] = old


if __name__ == "__main__":
    unittest.main()
