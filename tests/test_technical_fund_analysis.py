import unittest

from app.data_provider import DemoDataProvider


class TechnicalFundAnalysisTests(unittest.TestCase):
    def test_detects_multi_period_fund_trend_and_tail_quant_pressure(self):
        provider = DemoDataProvider()
        provider.stock_minute_chart = lambda code, stock=None: {
            "type": "minute",
            "is_real": True,
            "source": "unit-minute",
            "items": [
                {"time": "2026-07-10 09:30", "price": 26.10, "volume": 2000, "amount": 52_000_000},
                {"time": "2026-07-10 14:30", "price": 26.08, "volume": 1000, "amount": 26_000_000},
                {"time": "2026-07-10 14:50", "price": 25.20, "volume": 18_000, "amount": 453_600_000},
                {"time": "2026-07-10 14:58", "price": 25.15, "volume": 22_000, "amount": 553_300_000},
                {"time": "2026-07-10 15:00", "price": 25.31, "volume": 7_000, "amount": 177_170_000},
            ],
        }
        provider.stock_kline_chart = lambda code, stock=None, limit=120: {
            "type": "kline",
            "is_real": True,
            "source": "unit-kline",
            "items": [
                {"date": "2026-07-06", "open": 21, "close": 22, "high": 22.5, "low": 20.8, "volume": 100, "amount": 1000, "change_pct": 2},
                {"date": "2026-07-07", "open": 22, "close": 23, "high": 23.5, "low": 21.8, "volume": 130, "amount": 1400, "change_pct": 4},
                {"date": "2026-07-08", "open": 23, "close": 24, "high": 24.5, "low": 22.8, "volume": 160, "amount": 1800, "change_pct": 4},
                {"date": "2026-07-09", "open": 24, "close": 26.1, "high": 26.1, "low": 23.8, "volume": 260, "amount": 3200, "change_pct": 8},
                {"date": "2026-07-10", "open": 26.1, "close": 25.31, "high": 26.1, "low": 25.1, "volume": 495, "amount": 12764, "change_pct": 6.66},
            ],
        }
        provider.stock_fund_chart = lambda code, stock=None, limit=60: {
            "type": "fund",
            "is_real": True,
            "source": "unit-fund",
            "items": [
                {"date": "2026-07-06", "main": 12_000, "large": 8_000, "super_large": 4_000, "price": 22},
                {"date": "2026-07-07", "main": 18_000, "large": 12_000, "super_large": 5_000, "price": 23},
                {"date": "2026-07-08", "main": 21_000, "large": 14_000, "super_large": 7_000, "price": 24},
                {"date": "2026-07-09", "main": 60_000, "large": 35_000, "super_large": 18_000, "price": 26.1},
                {"date": "2026-07-10", "main": -55_000, "large": -35_000, "super_large": -25_000, "price": 25.31},
            ],
        }

        result = provider.technical_fund_analysis("002185.SZ")

        self.assertEqual(result["code"], "002185.SZ")
        self.assertIn("multi_periods", result)
        self.assertIn("日K", result["multi_periods"])
        self.assertEqual(result["fund_trend"]["direction"], "短线流出")
        self.assertTrue(result["quant_watch"]["tail_dump_detected"])
        self.assertGreaterEqual(result["quant_watch"]["suspicion_score"], 70)
        self.assertIn("尾盘", "；".join(result["action_points"]))

    def test_quant_fund_radar_promotes_high_suspicion_stock_into_action_queue(self):
        provider = DemoDataProvider()
        user = {"id": 991, "username": "radar-user", "role": "member"}
        provider.add_user_watchlist(user, "002463.SZ")
        provider.technical_fund_analysis = lambda code: {
            "code": code,
            "name": "沪电股份",
            "stance": "警惕量化尾盘扰动",
            "fund_trend": {"direction": "短线流出"},
            "quant_watch": {
                "suspicion_score": 86,
                "tail_dump_detected": True,
                "evidence": ["14:30后出现放量急跌，疑似尾盘再平衡或量化集中兑现"],
            },
            "action_points": ["尾盘急跌先看承接和资金方向，不情绪割肉"],
            "data_sources": [{"name": "分时", "ok": True}, {"name": "日K", "ok": True}, {"name": "资金趋势", "ok": True}],
        }

        radar = provider.user_quant_fund_radar(user)
        queue = provider.user_trading_action_queue(user)

        self.assertEqual(radar["top_alerts"][0]["code"], "002463.SZ")
        self.assertGreaterEqual(radar["top_alerts"][0]["suspicion_score"], 80)
        self.assertIn("quant_fund_radar", queue)
        promoted = [item for item in queue["actions"] if item["code"] == "002463.SZ"][0]
        self.assertEqual(promoted["action"], "QUANT_WATCH")
        self.assertEqual(promoted["label"], "量化异动盯防")
        self.assertIn("尾盘", promoted["reason"])
        self.assertIn("quant_fund_snapshot", queue)
        self.assertGreaterEqual(provider.quant_fund_radar_history(user)["count"], 1)


    def test_quant_fund_radar_3_adds_tail_linkage_and_history(self):
        provider = DemoDataProvider()
        user = {"id": 992, "username": "radar-3-user", "role": "member"}
        provider.add_user_watchlist(user, "002463.SZ")
        provider.add_user_watchlist(user, "002938.SZ")

        def fake_analysis(code):
            return {
                "code": code,
                "name": "沪电股份" if code.startswith("002463") else "鹏鼎控股",
                "stance": "尾盘量化扰动，高风险盯防",
                "fund_trend": {"direction": "短线流出"},
                "quant_watch": {
                    "suspicion_score": 88 if code.startswith("002463") else 82,
                    "tail_dump_detected": True,
                    "evidence": ["14:30后放量急跌", "资金净流出与价格冲高回落共振"],
                },
                "action_points": ["尾盘先看承接，不追高"],
                "data_sources": [{"name": "minute", "ok": True}],
            }

        provider.technical_fund_analysis = fake_analysis

        radar = provider.user_quant_fund_radar(user)
        record = provider.save_user_quant_fund_radar_snapshot(user, radar)
        history = provider.quant_fund_radar_history(user)

        self.assertEqual(radar["version"], "3.0")
        self.assertEqual(radar["tail_session"]["level"], "高")
        self.assertGreaterEqual(radar["tail_session"]["alert_count"], 2)
        self.assertIn("linkage", radar)
        self.assertTrue(radar["linkage"]["dominant_tags"])
        self.assertEqual(record["summary"]["high_count"], 2)
        self.assertEqual(history["items"][0]["id"], record["id"])


if __name__ == "__main__":
    unittest.main()
