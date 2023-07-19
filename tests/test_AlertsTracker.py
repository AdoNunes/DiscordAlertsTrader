from DiscordAlertsTrader.alerts_tracker import AlertsTracker
import unittest
import os

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestAlertsTrader(unittest.TestCase):

    def test_trailinstat(self):
        tracker = AlertsTracker(brokerage=None,
                                portfolio_fname=root_dir+'/data/analysts_portfolio.csv',
                                dir_quotes=root_dir+'/data/live_quotes'
                                )
        print(root_dir)
        open_trade = tracker.portfolio.index[tracker.portfolio['Symbol'] == 'QQQ_051223C327'].to_list()[-1]
        trailstat = tracker.compute_trail(open_trade)

        # self.assertEqual(trailstat, '| min,-87.1%,$0.04,in 02:09:36| max,3.23%,$0.32,in 00:01:19| | TS:0.2,-19.35%,$0.25'+\
        #     ',in 00:08:14| TS:0.3,-29.03%,$0.22,in 00:16:39| TS:0.4,-38.71%,$0.19,in 00:17:09| TS:0.5,-48.39%,$0.16,in 00:22:04')


if __name__ == '__main__':
    unittest.main()