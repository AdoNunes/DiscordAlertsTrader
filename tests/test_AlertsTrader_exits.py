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


init(autoreset=True)

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestAlertsTrader(unittest.TestCase):

    def prepare(self):
        # make port files
        self.trader_portfolio_fname=root_dir+"/data/test_trader_portfolio.csv"
        self.trader_log_fname=root_dir+"/data/test_trader_log.csv"
        # remove in case they exist
        if os.path.exists(self.trader_portfolio_fname):
            os.remove(self.trader_portfolio_fname)
        if os.path.exists(self.trader_log_fname):
            os.remove(self.trader_log_fname)
        
        # make trade moves
        today = datetime.now().strftime("%m/%d")
        self.trades = [f"BTO 10 AAPL 100c {today} @ .5 PT 125%TS30% SL 50%",
                     f"exitupdate AAPL 100c {today}  PT2.2 ",
                     f"exitupdate AAPL 100c {today} PT2.2"
                     ]
        self.exits = ['PT 30%TS10 SL 10%']

    def tracker_order(self, brokerage):
        """Test that the TDA order is sent correctly and trader works as expected"""

        self.prepare()
        
        cfg['order_configs']['max_trade_capital'] = '1000'
        cfg['discord']['notify_alerts_to_discord'] = 'false'
        cfg['general']['DO_BTO_TRADES'] = 'true'
        cfg['order_configs']['max_trade_capital'] = '5000'
        cfg["order_configs"]["default_exits"] = ""
        
        trader = AlertsTrader(brokerage, 
                            portfolio_fname=self.trader_portfolio_fname,
                            alerts_log_fname=self.trader_log_fname,
                            update_portfolio=False,
                            queue_prints=queue.Queue(maxsize=50),
                            cfg=cfg
                            )
        
        ################################################################################
        # Buy alert
        buy_alert = self.trades[0]
        pars, order =  parse_trade_alert(buy_alert)

        # Expected values
        expected = {
            'BTO-Status': 'FILLED',
            'action': order['action'],
            "Symbol": order['Symbol'],
            'Price': order['price'],
            "ordID": 99,
            "STC-SL-ordID": 1,
            "STC-orderID": 100,
            'Asset': order['asset'],
            'uQty': order['uQty'],
            'exit_plan': {'PT1': order['PT1'], 'PT2': order['PT2'], 'PT3': order['PT3'], 'SL': order['SL']},
            
            }

        # Create a message, order and pars
        order['Trader'] = 'test'
        order["Date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        # Generate return vals for the brokerage
        brokerage.get_quotes.return_value = {expected['Symbol']: {'askPrice': expected['Price']}} 
        brokerage.send_order.return_value = ["WORKING",expected["ordID"]]
        brokerage.get_order_info.return_value = [
            "WORKING",
            {'quantity': expected["uQty"],
             "price": expected['Price'],
             'filledQuantity': expected["uQty"],
             'status': "WORKING",
             'orderLegCollection':[
                {'instrument': {'symbol': expected['Symbol']},
                 'instruction': "BUY"},  
            ]}]
        ################################################################################
        # Buy alert working
        trader.new_trade_alert(order, pars, buy_alert)
        trader.portfolio.loc[0, 'exit_plan']        
        self.assertEqual(eval(trader.portfolio.loc[0, 'exit_plan']), expected['exit_plan']) 

        ################################################################################
        # Buy alert filled, send exit orders
        brokerage.get_order_info.side_effect = [
        ["FILLED",
        {'quantity': expected["uQty"],
            "price": expected['Price'],
            'filledQuantity': expected["uQty"],
            'status': "FILLED",
            'orderLegCollection':[
            {'instrument': {'symbol': expected['Symbol']},
                'instruction': "BUY"},  
        ]}], # for BTO
        ["WAITING",
        {'quantity': expected["uQty"],
            "price": expected['Price'],
            'filledQuantity': expected["uQty"],
            'status': "WAITING",
            'orderLegCollection':[
            {'instrument': {'symbol': expected['Symbol']},
                'instruction': "BUY"},  
        ]}], # for SL
        ]
        brokerage.get_quotes.return_value = {expected['Symbol']: {'bidPrice': expected['Price']*1.05}}
        trader.update_orders()
        
        ################################################################################
        # Update the exit orders, trigger PT SL
        exit_plan = eval(trader.portfolio.loc[0, 'exit_plan'])
        pt_target = eval(exit_plan['PT1'].split("TS")[0])
        ts_target = eval(exit_plan['PT1'].split("TS")[1])
        brokerage.get_quotes.return_value = {expected['Symbol']: {'bidPrice': pt_target}}
        
        brokerage.get_order_info.side_effect = [[ 
            # for SL
            "WORKING",
            {'quantity': expected["uQty"],
             "price": expected['Price'],
             'filledQuantity': expected["uQty"],
             'status': "WORKING",
             'orderLegCollection':[
                {'instrument': {'symbol': expected['Symbol']},
                 'instruction': "BUY"},  
            ]}],
            # [["WORKING"], {}], # for cancelling SL      
            [ 
            # for TS filled 
            "FILLED",
            {'quantity': expected["uQty"],
             "price": pt_target - ts_target,
             'filledQuantity': expected["uQty"],
             'status': "FILLED",
             'orderLegCollection':[
                {'instrument': {'symbol': expected['Symbol']},
                'quantity': expected["uQty"],
                'instruction': "BUY"}  
            ]}],
            [ 
            # for log_filled_STC 
            "FILLED",
            {'quantity': expected["uQty"],
             "price": pt_target + ts_target,
             'filledQuantity': expected["uQty"],
             'status': "FILLED",
             'orderLegCollection':[
                {'instrument': {'symbol': expected['Symbol']},
                'quantity': expected["uQty"],
                 'instruction': "BUY"},],
             "closeTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
             }]
            ]
        brokerage.send_order.return_value = ["WORKING", 101]
        trader.update_orders()


    def test_tracker_TDA(self):
        mock_brokerage = create_autospec(TDA)
        mock_brokerage.name = 'tda'
        self.tracker_order(mock_brokerage)



# @patch('DiscordAlertsTrader.brokerages.TDA_api.TDA')
if __name__ == '__main__':
    unittest.main()
