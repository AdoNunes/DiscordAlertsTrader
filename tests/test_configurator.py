

def test_configurator():
    from configurator import config
    
    trailstop_val = config['order_configs']['default_trailstop']
    assert(trailstop_val == '' or  eval(trailstop_val) > .9)
    
    config['general'].getboolean('DO_BTO_TRADES')
    config['order_configs'].getboolean('sell_current_price')
    config['order_configs'].getboolean('auto_trade')