from DiscordAlertsTrader.alerts_tracker import AlertsTracker

tracker = AlertsTracker(brokerage=None,
                 portfolio_fname='tests/data/analysts_portfolio.csv',
                 dir_quotes='tests/data/live_quotes'
                 )


open_trade = tracker.portfolio.index[tracker.portfolio['Symbol'] == 'QQQ_051223C327'].to_list()[-1]
trailstat = tracker.compute_trail(open_trade)
assert(trailstat == 'min,-87.1%,$0.04,in 02:09:36| max,3.23%,$0.32,in 00:01:19| | TS:0.2,-19.35%,$0.25,in 00:08:14| TS:0.3,-29.03%,$0.22,in 00:16:39| TS:0.4,-38.71%,$0.19,in 00:17:09| TS:0.5,-48.39%,$0.16,in 00:22:04')
