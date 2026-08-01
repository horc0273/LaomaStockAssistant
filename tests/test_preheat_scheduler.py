from pathlib import Path
import unittest


class PreheatSchedulerTests(unittest.TestCase):
    def test_read_only_cron_entry_and_script_exist(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "preheat_once.py"
        cron = root / "scripts" / "preheat_cron.example"
        self.assertTrue(script.exists())
        self.assertTrue(cron.exists())
        self.assertIn("force=True", script.read_text(encoding="utf-8"))
        self.assertIn("preheat_once.py", cron.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
