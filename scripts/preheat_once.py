"""Run one read-only market preheat for cron/systemd timers.

Example (server cron):
  0 8,9,13,14 * * 1-5 cd /opt/laoma && python scripts/preheat_once.py --reason=cron
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import preheat_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Laoma read-only market preheat")
    parser.add_argument("--reason", default="cron")
    args = parser.parse_args()
    result = preheat_service.run_once(reason=args.reason, force=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
