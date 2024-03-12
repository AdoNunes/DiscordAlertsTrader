from datetime import datetime
from DiscordAlertsTrader.alerts_tracker import AlertsTracker
from DiscordAlertsTrader.port_sim import calc_roi
import unittest
import os
import pandas as pd

# root_dir  =  os.path.abspath(os.path.dirname(__file__))

# class TestAlertsTracker(unittest.TestCase):


        
#     def test_rois(self):
        



initial_prices = 1
sl_update = []
avg_down = None

# Test PT
quotes = pd.Series([1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2])
out_1 = calc_roi(quotes, PT=1.2, TS=0, SL=0.3,  sl_update=[], avgdown=None)
assert out_1 == [[1.0, 1.2, 19.999999999999996, 19.999999999999996, 1, 1]]

# Test SL
quotes = pd.Series([1,1.1,1.5,0.7,.5,1.6,1.7,1.8,1.9,2])
out_2 = calc_roi(quotes, PT=1.7, TS=0, SL=0.5,  sl_update=[], avgdown=None)
assert out_2 == [[1.0, 0.5, -50.0, -50.0, 4, 1]]

# Test Sl update
quotes = pd.Series([1,1.1,1.5,0.9,.7,1.6,1.7,1.8,1.9,2])
out_3 = calc_roi(quotes, PT=1.7, TS=0, SL=0.5,  sl_update=[[1.1, 0.7], [1.2 , 0.9]], avgdown=None)
assert out_3 == [[1.0, 0.9, -9.999999999999998, -9.999999999999998, 3, 1]]

# Test avgdown
quotes = pd.Series([1,1.1,1.5,0.9,.8,1.53,1.6,1.7,1.8,1.9,2])
out_3 = calc_roi(quotes, PT=1.7, TS=0, SL=0.5,  sl_update=[[1.1, 0.6], [1.2 , 0.7]], avgdown=[[0.8, 1]])
assert out_3 == [[0.9, 1.53, 70.0, 70.0, 5, 2]]

# Test new SL and avgdown
quotes = pd.Series([1,1.1,1.5,0.9,.8,0.45,1.53,1.6,1.7,1.8,1.9,2])
out_4 = calc_roi(quotes, PT=1.7, TS=0, SL=0.5,  sl_update=[[1.1, 0.6], [1.2 , 0.7]], avgdown=[[0.8, 1]])
assert out_4 == [[0.9, 0.45, -50.0, -50.0, 5, 2]]

# Test avgup
quotes = pd.Series([1,1.27,1.5,0.9,.8,1.53,1.6,1.7,1.8,1.9,2])
out_5 = calc_roi(quotes, PT=1.7, TS=0, SL=0.5,  sl_update=[[1.1, 0.6], [1.2 , 0.7]], avgdown=[[1.27, 0.5]])
assert out_5 == [[1.09, 1.9, 74.31192660550457, 74.31192660550457, 9, 1.5]]

# Test avgup SL
quotes = pd.Series([1, 1.27, 1.5, 1.0213, .8, 1.53, 1.6, 1.7, 1.8, 1.9, 2])
out_5 = calc_roi(quotes, PT=1.7, TS=0, SL=0.9,  sl_update=[[1.1, 0.6], [1.2 , 0.7]], avgdown=[[1.27, 1]])
assert out_5 == [[1.135, 1.0213, -10.017621145374441, -10.017621145374441, 3, 2]]

# Test initial price
quotes = pd.Series([1, 1.27, 1.5, 1.0213, .8, 1.53, 1.6, 1.7, 1.8, 1.9, 2.56])
out_6 = calc_roi(quotes, PT=1.7, TS=0, SL=0.9,  sl_update=[[1.1, 0.6], [1.2 , 0.7]], avgdown=[[1.05, 1]], initial_prices=1.5)
print(out_6)
assert out_6 == [[1.5, 1.0, -33.33333333333333, -33.33333333333333, 0, 1]]

# Test pt update
quotes = pd.Series([1,1.2,1.3, .8, .7 , 1,1.6,1.7,1.8,1.9,2])
out_7 = calc_roi(quotes, PT=1.7, TS=0, SL=0.5, pt_update=[[0.8, 1]], sl_update=[[1.1, 0.5], [1.2 , 0.6]], initial_prices=1)
print(out_7)
assert out_7 == [[1, 1.0, 0.0, 0.0, 5, 1]]

if __name__ == '__main__':
    unittest.main()