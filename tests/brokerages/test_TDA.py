import unittest
from unittest.mock import MagicMock

import pandas as pd
from td.client import TDClient
from td.orders import Order, OrderLeg

from brokerages.TDA_api import TDA


class TestTDA(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.tda = TDA(self.api_key)

    # def test_get_session(self):
    #     self.tda.session = MagicMock(spec=TDClient)
    #     self.tda.session.login.return_value = True
    #     self.tda.session.get_accounts.return_value = [{"securitiesAccount": {"accountId": "test_account_id"}}]

    #     success = self.tda.get_session()

    #     self.assertTrue(success)
    #     # Check if the login method was called once without any arguments
    #     self.assertEqual(self.tda.session.login.call_count, 1)
    #     self.assertEqual(self.tda.session.login.call_args, ())
    #     self.tda.session.get_accounts.assert_called_once_with(account="all")
    #     self.assertEqual(self.tda.session.accountId, "test_account_id")

    def test_send_order(self):
        self.tda.session = MagicMock(spec=TDClient)
        self.tda.session.place_order.return_value = {"order_id": "test_order_id"}
        self.tda.session.accountId = "test_account_id"
        test_order = MagicMock()

        order_response, order_id = self.tda.send_order(test_order)

        self.tda.session.place_order.assert_called_once_with(account="test_account_id", order=test_order)
        self.assertEqual(order_response, {"order_id": "test_order_id"})
        self.assertEqual(order_id, "test_order_id")

    def test_cancel_order(self):
        self.tda.session = MagicMock(spec=TDClient)
        self.tda.session.cancel_order.return_value = True
        self.tda.session.accountId = "test_account_id"
        test_order_id = "test_order_id"

        result = self.tda.cancel_order(test_order_id)

        self.tda.session.cancel_order.assert_called_once_with("test_account_id", test_order_id)
        self.assertTrue(result)

    def test_get_order_info(self):
        self.tda.session = MagicMock(spec=TDClient)
        self.tda.session.accountId = 12345
        self.tda.session.get_orders.return_value = {
            'orderStrategyType': 'SINGLE',
            'status': 'FILLED'
        }
        order_status, order_info = self.tda.get_order_info(order_id=123)
        self.assertEqual(order_status, 'FILLED')
        self.assertEqual(order_info['orderStrategyType'], 'SINGLE')

    def test_get_quotes(self):
        self.tda.session = MagicMock(spec=TDClient)
        self.tda.session.get_quotes.return_value = {'symbol': 'AAPL', 'price': 150}
        result = self.tda.get_quotes(symbol='AAPL')
        self.assertEqual(result, {'symbol': 'AAPL', 'price': 150})
    
    
    def test_get_positions_orders(self):
        # Mock TDClient.get_accounts method
        mock_get_accounts = MagicMock()
        mock_get_accounts.return_value = {
            'securitiesAccount': {
                'positions': [
                    {
                        "longQuantity": 10,
                        "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
                        "averagePrice": 150,
                        "currentDayProfitLoss": 200
                    }
                ]
            }
        }

        # Replace TDClient.get_accounts with the mocked version
        self.tda.session = MagicMock()
        self.tda.session.get_accounts = mock_get_accounts

        df_pos, df_ordr = self.tda.get_positions_orders()

        expected_df_pos = pd.DataFrame(
            [{
                "symbol": "AAPL",
                "asset": "EQUITY",
                "type": "long",
                "Qty": 10,
                "Avg Price": 150,
                "PnL": 200,
                "PnL %": 200 / (150 * 10)
            }],
            dtype=object,
            columns=["symbol", "asset", "type", "Qty", "Avg Price", "PnL", "PnL %"],
        ).astype({"Qty": "object", "Avg Price": "object", "PnL": "object", "PnL %": "float64"})

        pd.testing.assert_frame_equal(df_pos, expected_df_pos, check_like=True)
        self.assertTrue(df_ordr.empty)

    def test_make_BTO_lim_order(self):
        symbol = 'AAPL'
        uQty = 10
        price = 150

        new_order = self.tda.make_BTO_lim_order(Symbol=symbol, uQty=uQty, price=price)

        self.assertIsInstance(new_order, Order)
        self.assertEqual(new_order._grab_order()['orderStrategyType'], 'TRIGGER')
        self.assertEqual(new_order._grab_order()['orderType'], 'LIMIT')
        self.assertEqual(new_order._grab_order()['session'], 'NORMAL')
        self.assertEqual(new_order._grab_order()['duration'], 'GOOD_TILL_CANCEL')
        self.assertEqual(new_order._grab_order()['price'], price)

        self.assertEqual(len(new_order.order_legs_collection), 1)
        order_leg = new_order.order_legs_collection['order_leg_1']
        self.assertEqual(order_leg['instruction'], 'BUY')
        self.assertEqual(order_leg['instrument'], {'assetType': 'EQUITY', 'symbol': symbol})
        self.assertEqual(order_leg['quantity'], uQty)


if __name__ == '__main__':
    unittest.main()