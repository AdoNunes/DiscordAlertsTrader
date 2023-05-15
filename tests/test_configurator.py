
import unittest
from configurator import cfg

class TestConfigurator(unittest.TestCase):

    def test_trailstop_val(self):
        trailstop_val = cfg['order_configs']['default_trailstop']
        self.assertTrue(trailstop_val == '' or eval(trailstop_val) > .9)

    def test_general_options(self):
        cfg['general'].getboolean('DO_BTO_TRADES')
        cfg['order_configs'].getboolean('sell_current_price')
        cfg['order_configs'].getboolean('auto_trade')

    def test_portfolio_names(self):
        for v in cfg['portfolio_names'].values():
            self.assertTrue(v.endswith(".csv"))

    def test_cfg_options_set(self):
        self.assertTrue(cfg['general']['BROKERAGE'] in ['', 'TDA', "webull", 'etrades'])
        self.assertTrue(cfg['order_configs']['default_bto_qty'] in ['buy_one', 'trade_capital'])
        
if __name__ == '__main__':
    unittest.main()
