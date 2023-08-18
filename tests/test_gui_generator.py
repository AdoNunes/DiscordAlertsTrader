import os

import unittest
import pandas as pd
import numpy as np
from DiscordAlertsTrader.gui_generator import get_stats_data
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.alerts_tracker import calc_stc_prices

class TestConfigurator(unittest.TestCase):

    def test_get_stats_data(self):
        fname_port="test_tracker_portfolio.csv"
        
        # make dummy portfolio
        cols = cfg["col_names"]["tracker_portfolio"]
        dt = "2023-05-15 10:02:47.409000,NFLX_051923C345,test#3069,chan,0,option,BTO,10,5,12,,,,,,,,,,,,,2023-05-16 12:39:37.884000,".split(',')
        port = pd.DataFrame([dt], columns=cols.split(","))
        port = port.replace('', np.nan)
        order = {
            "price":12,
            "Actual Cost":24,
            'Qty' :1,
            }
        stc_info = calc_stc_prices(port.loc[0], order)
        for k, v in stc_info.items():
            port.loc[0,k] = v
        port.to_csv(fname_port, index=False)
        
        data, _ = get_stats_data(exclude={}, stat_filt_author='', stat_filt_date_frm='',
                    stat_filt_date_to='', stat_filt_sym='', 
                    stat_max_trade_cap='', stat_max_qty='', trail_stop_perc='',
                    fname_port=fname_port)
        self.assertTrue(data[0][1:] == data[1][1:])
    
        data, h = get_stats_data(exclude={}, stat_filt_author='', stat_filt_date_frm='',
                    stat_filt_date_to='', stat_filt_sym='', 
                    stat_max_trade_cap='', stat_max_qty='1', trail_stop_perc='',
                    fname_port=fname_port)
        
        expected = [
            ['Trader', 'test'],
            ['PnL$', '200'],
            ['PnL$-Actual', '1200'],
            ['PnL', '20'],
            ['PnL-Actual', '100'],
            ['Win', '100'],
            ['Win act', '100'],
            ['PnL diff', '80'],
            ['BTO diff', '20'],
            ['STC diff', '100'],
            ['N Trades', '1'],
            ['Since', '05/15/2023'],
            ['Last', '05/15/2023']
            ]

        for k,v, exp in zip(h,data[0], expected):
            self.assertTrue(k == exp[0])
            self.assertTrue(v == exp[1])

        # Delete the generated file
        os.remove(fname_port)

if __name__ == '__main__':
    unittest.main()
