from datetime import datetime
from DiscordAlertsTrader.alerts_tracker import AlertsTracker
from DiscordAlertsTrader.message_parser import parse_trade_alert
import unittest
import os

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestAlertsTracker(unittest.TestCase):

    def prepare(self):
        # make port files
        self.tracker_portfolio_fname=root_dir+"/data/test_tracker_portfolio.csv"
        # remove in case they exist
        if os.path.exists(self.tracker_portfolio_fname):
            os.remove(self.tracker_portfolio_fname)

        
    def test_sto(self):
        self.prepare()
        tracker = AlertsTracker(brokerage=None,
                                portfolio_fname=self.tracker_portfolio_fname,
                                dir_quotes=root_dir+'/data/live_quotes'
                                )
        
        buy = "STO 3  AAPL 100c 8/5 @1.5"
        sell = "BTC 3  AAPL 100c 8/5 @1"
        pars, order =  parse_trade_alert(buy)
        order["Trader"] = 'test'
        msg_b = tracker.trade_alert(order, live_alert=False, channel=None)        
        pars, order =  parse_trade_alert(sell)
        order["Trader"] = 'test'
        order['Date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        msg_s = tracker.trade_alert(order, live_alert=False, channel=None)
        
        trade = tracker.portfolio.loc[0]
        self.assertTrue(round(trade['PnL'],2) == 33.33)
        self.assertTrue(round(trade['PnL$']) == 150)


if __name__ == '__main__':
    unittest.main()