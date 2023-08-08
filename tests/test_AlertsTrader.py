import unittest
from unittest.mock import create_autospec
import os
from datetime import datetime
from colorama import  init
import queue

from DiscordAlertsTrader.alerts_trader import AlertsTrader
from DiscordAlertsTrader.configurator import cfg 
from DiscordAlertsTrader.message_parser import parse_trade_alert
from DiscordAlertsTrader.brokerages.TDA_api import TDA
from DiscordAlertsTrader.brokerages.eTrade_api import eTrade
from DiscordAlertsTrader.brokerages.weBull_api import weBull
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
        
        cfg['order_configs']['max_trade_capital'] = '1000'
        cfg['discord']['notify_alerts_to_discord'] = 'false'
        cfg['general']['DO_BTO_TRADES'] = 'true'
        cfg['general']['DO_STC_TRADES'] = 'true'
        
        trader = AlertsTrader(brokerage, 
                              portfolio_fname=self.trader_portfolio_fname,
                              alerts_log_fname=self.trader_log_fname,
                              update_portfolio=False,
                              queue_prints=queue.Queue(maxsize=50),
                              cfg=cfg
                              )
        
        
        # Expected values
        expected = {
            'BTO-Status': 'FILLED',
            'Price': 1.05,
            "ordID": 99,
            'Asset': 'option',
            'Price-alert': 1.5,
            'Price-actual': 1.1,
            'Qty': 5,
            'filledQty': 5,
            'exit_plan': "{'PT1': None, 'PT2': None, 'PT3': None, 'SL': None}",
            "STC1-Qty": 5,
            "STC1-Price": 2,
            "STC1-Price-actual": 2.2,
            "STC1-Price-alert": 2.1,
            "STC1-Status": "FILLED",
            "STC1-ordID": 100,
            
            }

        expected["PnL"] =  100*(expected["STC1-Price"]- expected["Price"])/ expected["Price"]
        expected["PnL$"] =  round(expected["PnL"] * expected["STC1-Qty"] * expected["Price"],1)
        expected["PnL-alert" ] = 100*(expected["STC1-Price-alert"]- expected["Price-alert"])/ expected["Price-alert"]
        expected["PnL$-alert"] =  expected["PnL-alert"] * expected["STC1-Qty"] * expected["Price-alert"]
        expected["PnL-actual"] =  100*(expected["STC1-Price-actual"]- expected["Price-actual"])/ expected["Price-actual"]
        expected["PnL$-actual"] =  expected["PnL-actual"] * expected["STC1-Qty"] * expected["Price-actual"]

        # Create a message, order and pars
        message = make_message()
        expdate = datetime.now().strftime("%m/%d")
        message.content = f'BTO {expected["Qty"]} AI 25c {expdate} @ {expected["Price-alert"]}'
        pars, order =  parse_trade_alert(message.content)
        order['Trader'] = f"{message.author.name}#{message.author.discriminator}"
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate return vals for the brokerage
        symbol = f'AI_{expdate.replace("/", "")}23C25'
        brokerage.get_quotes.return_value = {symbol: {'askPrice': expected['Price-actual']}}
        brokerage.send_order.return_value = [
            expected['BTO-Status'],
            expected["ordID"]         
            ]
        brokerage.get_order_info.return_value = [
            expected['BTO-Status'],
            {'quantity': expected["Qty"],
             "price": expected['Price'],
             'filledQuantity': expected["Qty"],
             'status': expected['BTO-Status'],
             'orderLegCollection':[
                {'instrument': {'symbol': symbol},
                 'instruction': "BUY"},  
            ]}]
        
        trader.new_trade_alert(order, pars, message.content)
        
        # make STC order
        message.content = f'STC {expected["STC1-Qty"]} AI 25c {expdate} @ {expected["STC1-Price-alert"]}'
        pars, order =  parse_trade_alert(message.content)
        order['Trader'] = f"{message.author.name}#{message.author.discriminator}"
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate return vals for the brokerage
        brokerage.get_quotes.return_value = {f'AI_{expdate.replace("/", "")}23C25': {'bidPrice': expected["STC1-Price-actual"]}}
        brokerage.send_order.return_value = [
            expected['STC1-Status'],
            expected["STC1-ordID"]         
            ]
        brokerage.get_order_info.return_value = [
            expected['STC1-Status'],
            {'status': expected['STC1-Status'],
             'quantity': expected["STC1-Qty"],
             'filledQuantity': expected["STC1-Qty"],
             "price": expected['STC1-Price'],
             'orderLegCollection':[{
                 'instrument': {'symbol': symbol},
                 'instruction': "SELL", 
                 "quantity": expected["STC1-Qty"]}],
             'closeTime' : order["Date"]
             }         
            ]
        
        trader.new_trade_alert(order, pars, message.content)
        
        # assert expected values
        trade = trader.portfolio.loc[0]
        for exp, val in expected.items():
            if not trade[exp] == val:
                print(f"Expected {exp} = {val} but got {trade[exp]}")
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)

    def tracker_order_sto(self, brokerage):
        """Test that the TDA order is sent correctly and trader works as expected for selling to open"""
        self.trader_portfolio_fname=root_dir+"/data/test_trader_portfolio.csv"
        self.trader_log_fname=root_dir+"/data/test_trader_log.csv"
        # remove in case they exist
        if os.path.exists(self.trader_portfolio_fname):
            os.remove(self.trader_portfolio_fname)
        if os.path.exists(self.trader_log_fname):
            os.remove(self.trader_log_fname)
        
        cfg['order_configs']['max_trade_capital'] = '1000'
        cfg['discord']['notify_alerts_to_discord'] = 'false'
        cfg['shorting']['max_dte'] = '100'
        cfg['shorting']['DO_STO_TRADES'] = 'true'
        cfg['shorting']['DO_BTC_TRADES'] = 'true'
        cfg['shorting']['BTC_SL'] = '50'
        cfg['shorting']['BTC_PT'] = '50'
        
        trader = AlertsTrader(brokerage, 
                              portfolio_fname=self.trader_portfolio_fname,
                              alerts_log_fname=self.trader_log_fname,
                              update_portfolio=False,
                              queue_prints=queue.Queue(maxsize=50),
                              cfg=cfg
                              )
        
        # Expected values
        expected = {
            'BTO-Status': 'FILLED',
            "Type": "STO",
            'Price': 2,
            "ordID": 99,
            'Asset': 'option',
            'Price-alert': 2.1,
            'Price-actual': 2.2,
            'Qty': 5,
            'filledQty': 5,
            'exit_plan': "{'PT1': None, 'PT2': None, 'PT3': None, 'SL': None}",
            "STC1-Qty": 5,
            "STC1-Price": 1.05,
            "STC1-Price-actual": 1.1,
            "STC1-Price-alert": 1.5,
            "STC1-Status": "FILLED",
            "STC1-ordID": 100,
            
            }
        exit_plan = eval(expected['exit_plan'])
        exit_plan['PT1'] = round(expected['Price'] * (1 - float(cfg['shorting']['BTC_PT'])/100),2)
        exit_plan['SL'] = round(expected['Price'] * (1 + float(cfg['shorting']['BTC_SL'])/100),2)
        expected['exit_plan'] = str(exit_plan)  
        
        expected["PnL"] =  100*(expected["Price"] - expected["STC1-Price"])/ expected["Price"]
        expected["PnL$"] =  round(expected["PnL"] * expected["STC1-Qty"] * expected["Price"],1)
        expected["PnL-alert" ] = 100*(expected["Price-alert"] - expected["STC1-Price-alert"])/ expected["Price-alert"]
        expected["PnL$-alert"] =  expected["PnL-alert"] * expected["STC1-Qty"] * expected["Price-alert"]
        expected["PnL-actual"] =  100*(expected["Price-actual"] - expected["STC1-Price-actual"])/ expected["Price-actual"]
        expected["PnL$-actual"] =  expected["PnL-actual"] * expected["STC1-Qty"] * expected["Price-actual"]

        # Create a message, order and pars
        message = make_message()
        expdate = datetime.now().strftime("%m/%d")
        message.content = f'STO {expected["Qty"]} AI 25c {expdate} @ {expected["Price-alert"]}'
        pars, order =  parse_trade_alert(message.content)
        order['Trader'] = f"{message.author.name}#{message.author.discriminator}"
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate return vals for the brokerage
        symbol = f'AI_{expdate.replace("/", "")}23C25'
        brokerage.get_quotes.return_value = {symbol: {'bidPrice': expected['Price-actual']}}
        brokerage.send_order.return_value = [
            expected['BTO-Status'],
            expected["ordID"]         
            ]
        brokerage.get_order_info.return_value = [
            expected['BTO-Status'],
            {'quantity': expected["Qty"],
             "price": expected['Price'],
             'filledQuantity': expected["Qty"],
             'status': expected['BTO-Status'],
             'orderLegCollection':[
                {'instrument': {'symbol': symbol},
                 'instruction': "SELL_TO_OPEN"},  
            ]}]
        
        trader.new_trade_alert(order, pars, message.content)
        
        # make STC order
        message.content = f'BTC {expected["STC1-Qty"]} AI 25c {expdate} @ {expected["STC1-Price-alert"]}'
        pars, order =  parse_trade_alert(message.content)
        order['Trader'] = f"{message.author.name}#{message.author.discriminator}"
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Generate return vals for the brokerage
        brokerage.get_quotes.return_value = {f'AI_{expdate.replace("/", "")}23C25': {'askPrice': expected["STC1-Price-actual"]}}
        brokerage.send_order.return_value = [
            expected['STC1-Status'],
            expected["STC1-ordID"]         
            ]
        brokerage.get_order_info.return_value = [
            expected['STC1-Status'],
            {'status': expected['STC1-Status'],
             'quantity': expected["STC1-Qty"],
             'filledQuantity': expected["STC1-Qty"],
             "price": expected['STC1-Price'],
             'orderLegCollection':[{
                 'instrument': {'symbol': symbol},
                 'instruction': "BUY_TO_CLOSE", 
                 "quantity": expected["STC1-Qty"]}],
             'closeTime' : order["Date"]
             }         
            ]
        
        trader.new_trade_alert(order, pars, message.content)
        
        # assert expected values
        trade = trader.portfolio.loc[0]
        for exp, val in expected.items():
            if not trade[exp] == val:
                print(f"Expected {exp} = {val} but got {trade[exp]}")
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

    def test_tracker_sto_TDA(self):
        mock_brokerage = create_autospec(TDA)
        self.tracker_order_sto(mock_brokerage)
        
    def test_tracker_etrade(self):
        mock_brokerage = create_autospec(eTrade)
        self.tracker_order(mock_brokerage)

    def test_tracker_webull(self):
        mock_brokerage = create_autospec(weBull)
        self.tracker_order(mock_brokerage)

# @patch('DiscordAlertsTrader.brokerages.TDA_api.TDA')
if __name__ == '__main__':
    unittest.main()
