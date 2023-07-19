
import unittest
import ast
from DiscordAlertsTrader.configurator import cfg

class TestConfigurator(unittest.TestCase):

    # fails in git workflow
    # def test_defaul_exit(self):
    #     print('default_exits:', cfg['order_configs']['default_exits'])
    #     trailstop_val = ast.literal_eval(cfg['order_configs']['default_exits'])
    #     vals = list(trailstop_val.keys())
    #     self.assertTrue(["PT1", "PT2", "PT3", "SL"] ==  vals)

    def test_general_options(self):
        cfg['general'].getboolean('DO_BTO_TRADES')
        cfg['order_configs'].getboolean('sell_current_price')
        cfg['order_configs'].getboolean('auto_trade')

    def test_portfolio_names(self):
        for v in cfg['portfolio_names'].values():
            self.assertTrue(v.endswith(".csv"))

    def test_cfg_options_set(self):
        self.assertTrue(cfg['general']['BROKERAGE'].lower() in ['', 'tda', "webull", 'etrade'])
        self.assertTrue(cfg['order_configs']['default_bto_qty'] in ['buy_one', 'trade_capital'])
        
if __name__ == '__main__':
    unittest.main()
