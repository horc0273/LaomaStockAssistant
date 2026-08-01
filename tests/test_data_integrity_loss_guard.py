import unittest

from app.models import MarketOverview, Stock
from app.quant_engine import build_watchlist_item


class DataIntegrityLossGuardTests(unittest.TestCase):
    def test_non_positive_cost_is_not_counted_as_fake_profit(self):
        stock = Stock(
            market="A股",
            name="测试股",
            code="000001.SZ",
            price=100,
            change_pct=0,
            cost=-10,
            quantity=100,
            pnl_amount=99999,
            pnl_pct=0,
        )
        market = MarketOverview(
            source_note="test",
            updated_at="2026-07-30T10:00:00",
            indices=[],
            up_count=1,
            down_count=1,
            limit_up=0,
            limit_down=0,
            turnover_billion=10000,
            mood="震荡",
            themes=[],
        )

        item = build_watchlist_item(stock, market)

        self.assertFalse(item.cost_valid)
        self.assertEqual(item.pnl_amount, 0)
        self.assertEqual(item.pnl_pct, 0)
        self.assertTrue(item.data_warnings)


if __name__ == "__main__":
    unittest.main()
