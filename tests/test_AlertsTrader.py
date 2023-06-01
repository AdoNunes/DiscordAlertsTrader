import unittest
from unittest.mock import create_autospec
import os
from datetime import datetime
from colorama import  init

from DiscordAlertsTrader.alerts_trader import AlertsTrader
from DiscordAlertsTrader.configurator import cfg 
from DiscordAlertsTrader.message_parser import parse_trade_alert
from DiscordAlertsTrader.brokerages.TDA_api import TDA
from DiscordAlertsTrader.brokerages.eTrade_api import eTrade
from mock_discord_message import make_message

init(autoreset=True)

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestAlertsTrader(unittest.TestCase):

    def tracker_order(self, brokerage):
        """Test that the TDA order is sent correctly and trader works as expected"""
        self.trader_portfolio_fname=root_dir+"/data/test_trader_portfolio.csv"
        self.trader_log_fname=root_dir+"/data/test_trader_log.csv"
        # remove in case they exist
        if os.path.exists(self.trader_portfolio_fname):
            os.remove(self.trader_portfolio_fname)
        if os.path.exists(self.trader_log_fname):
            os.remove(self.trader_log_fname)
        
        trader = AlertsTrader(brokerage, 
                              portfolio_fname=self.trader_portfolio_fname,
                              alerts_log_fname=self.trader_log_fname,
                              update_portfolio=False,
                              )
        
        # Expected values
        expected = {
            'BTO-Status': 'FILLED',
            'Price': 1.05,
            "ordID": 99,
            'Asset': 'option',
            'Price-Alert': 1.5,
            'Price-Current': 1.1,
            'uQty': 5,
            'filledQty': 5,
            'exit_plan': "{'PT1': None, 'PT2': None, 'PT3': None, 'SL': None}",
            "STC1-uQty": 5,
            "STC1-Price": 2,
            "STC1-Price-Current": 2.2,
            "STC1-Price-Alerted": 2.1,
            "STC1-Status": "FILLED",
            "STC1-ordID": 100,
            
            }
        expected["PnL"] =  100*(expected["STC1-Price"]- expected["Price"])/ expected["Price"]
        expected["$PnL"] =  round(expected["PnL"] * expected["STC1-uQty"] * expected["Price"],1)
        expected["PnL-Alert" ] = 100*(expected["STC1-Price-Alerted"]- expected["Price-Alert"])/ expected["Price-Alert"]
        expected["$PnL-Alert"] =  expected["PnL-Alert"] * expected["STC1-uQty"] * expected["Price-Alert"]
        expected["PnL-Current"] =  100*(expected["STC1-Price-Current"]- expected["Price-Current"])/ expected["Price-Current"]
        expected["$PnL-Current"] =  expected["PnL-Current"] * expected["STC1-uQty"] * expected["Price-Current"]

        # Create a message, order and pars
        message = make_message()
        expdate = datetime.now().strftime("%m/%d")
        message.content = f'BTO {expected["uQty"]} AI 25c {expdate} @ {expected["Price-Alert"]}'
        pars, order =  parse_trade_alert(message.content)
        order['Trader'] = f"{message.author.name}#{message.author.discriminator}"
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate return vals for the brokerage
        brokerage.get_quotes.return_value = {f'AI_{expdate.replace("/", "")}23C25': {'askPrice': expected['Price-Current']}}
        brokerage.send_order.return_value = [
            expected['BTO-Status'],
            expected["ordID"]         
            ]
        brokerage.get_order_info.return_value = [
            expected['BTO-Status'],
            {'quantity': expected["uQty"],
             "price": expected['Price'],
             'filledQuantity': expected["uQty"]}         
            ]
        
        trader.new_trade_alert(order, pars, message.content)
        
        # make STC order
        message.content = f'STC {expected["STC1-uQty"]} AI 25c {expdate} @ {expected["STC1-Price-Alerted"]}'
        pars, order =  parse_trade_alert(message.content)
        order['Trader'] = f"{message.author.name}#{message.author.discriminator}"
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate return vals for the brokerage
        brokerage.get_quotes.return_value = {f'AI_{expdate.replace("/", "")}23C25': {'bidPrice': expected["STC1-Price-Current"]}}
        brokerage.send_order.return_value = [
            expected['STC1-Status'],
            expected["STC1-ordID"]         
            ]
        brokerage.get_order_info.return_value = [
            expected['STC1-Status'],
            {'quantity': expected["STC1-uQty"],
             "price": expected['STC1-Price'],
             'orderLegCollection':[{"quantity": expected["STC1-uQty"]}],
             'closeTime' : order["Date"]
             }         
            ]
        
        trader.new_trade_alert(order, pars, message.content)
        
        # assert expected values
        trade = trader.portfolio.loc[0]
        for exp, val in expected.items():
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)

        # Delete the generated file
        os.remove(self.trader_portfolio_fname)
        os.remove(self.trader_log_fname)

    def test_tracker_TDA(self):
        mock_brokerage = create_autospec(TDA)
        self.tracker_order(mock_brokerage)

    def test_tracker_etrade(self):
        mock_brokerage = create_autospec(eTrade)
        self.tracker_order(mock_brokerage)
        

# @patch('DiscordAlertsTrader.brokerages.TDA_api.TDA')
if __name__ == '__main__':
    unittest.main()
