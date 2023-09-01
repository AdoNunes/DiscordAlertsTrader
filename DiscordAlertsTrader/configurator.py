import configparser
import os
import os.path as op
import pandas as pd
import json

def update_port_cols():   
    portfolio_newcols = {"Price-Current":"Price-actual", "PnL-Current":"PnL-actual", "$PnL-Current":"PnL$-actual","$PnL":"PnL$",
                        "Price-Alert":"Price-alert", "PnL-Alert":"PnL-alert", "$PnL-Alert":"PnL$-alert",'uQty':'Qty',
                        "STC1-Alerted":"STC1-alerted", "STC1-uQty":"STC1-Qty","STC1-Price-Alerted":"STC1-Price-alert",
                        "STC1-Price-Current":"STC1-Price-actual",
                        "STC2-Alerted":"STC2-alerted", "STC2-uQty":"STC2-Qty","STC2-Price-Alerted":"STC2-Price-alert",
                        "STC2-Price-Current":"STC2-Price-actual",
                        "STC3-Alerted":"STC3-alerted", "STC3-uQty":"STC3-Qty","STC3-Price-Alerted":"STC3-Price-alert",
                        "STC3-Price-Current":"STC3-Price-actual",
                        }
    
    tracker_newcols = {'Amount':'Qty', "Price-current":"Price-actual", "Prices-current":"Prices-actual",
                        "PnL-current":"PnL-actual", "PnL$-current":"PnL$-actual", 'STC-Amount':'STC-Qty', 
                        'STC-Price-current':'STC-Price-actual', 'STC-Prices-current':'STC-Prices-actual',
                        'STC-PnL-current':'PnL-actual', 'STC-PnL$-current':'PnL$-actual', 'STC-PnL$':'PnL$',
                        'STC-PnL':'PnL'}

    if os.path.exists(cfg['portfolio_names']['portfolio_fname']):
        trader = pd.read_csv(cfg['portfolio_names']['portfolio_fname'])    
        trader = trader.rename(columns=portfolio_newcols)
        if "open_trailingstop" not in trader.columns:
            trader['open_trailingstop'] = None
        if 'trader_qty' not in trader.columns:
            trader['trader_qty'] = None        
        trader.to_csv(cfg['portfolio_names']['portfolio_fname'], index=False)
        
    if os.path.exists(cfg['portfolio_names']['tracker_portfolio_name']):
        tracker = pd.read_csv(cfg['portfolio_names']['tracker_portfolio_name'])
        tracker = tracker.rename(columns=tracker_newcols)
        tracker.to_csv(cfg['portfolio_names']['tracker_portfolio_name'], index=False)
    
package_dir = os.path.abspath(os.path.dirname(__file__))

config_path = package_dir + '/config.ini'
if not os.path.exists(config_path):
    print("\033[91mWARNING: DiscordAlertsTrader/config.ini not found. \033[0m")
    print("\033[91mWARNING: Rename DiscordAlertsTrader/config_example.ini to DiscordAlertsTrader/config.ini. \033[0m")
    print("\033[91mWARNING: Reverting to config_example.ini for now (might be necessary for testing). \033[0m")
    config_path = package_dir + '/config_example.ini'
else:
    # check that config.ini has same fields as in config_example.ini
    cfg_example = configparser.ConfigParser(interpolation=None)
    cfg_example.read(package_dir + '/config_example.ini', encoding='utf-8')
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(config_path, encoding='utf-8')
    missing_items = [(section, k) for section in cfg_example.sections() if cfg.has_section(section)
                      for k in cfg_example[section].keys() if not cfg.has_option(section, k)]
    if len(missing_items):
        raise ValueError(f"config.ini is missing the following items: {missing_items}\nadd missing items to config.ini and re-run")

                
# load configuration file
cfg = configparser.ConfigParser(interpolation=None)
cfg.read(config_path, encoding='utf-8')
cfg['root']= {'dir': package_dir}

# change data_dir if it is just a folder name
data_dir = cfg['general']['data_dir']
_, ext = os.path.splitext(data_dir)
if ext == "":    
    cfg['general']['data_dir'] = os.path.join(package_dir, "..", data_dir)
    print("full data dir:", cfg['general']['data_dir'])

# add path to file names
for k, v in cfg['portfolio_names'].items():
    cfg['portfolio_names'][k] = op.join(cfg['general']['data_dir'], v)
cfg['portfolio_names']['mock_portfolio_fname'] = './tests/trader_portfolio_simulated.csv'
cfg['portfolio_names']['mock_alerts_log_fname'] = './tests/trader_logger_simulated.csv'


# Define column names for portfolios and hist messages
portfolio_cols = ",".join([
                "Date", "Symbol", "Trader", "isOpen", "BTO-Status", "Asset", "Type", "Price", "Price-alert", "Price-actual",
                "Qty", "filledQty", "Avged", "Avged-prices", "exit_plan", "ordID", "Risk", "trailingstop", "PnL", "PnL$",
                "PnL-alert", "PnL$-alert","PnL-actual","PnL$-actual"
                ] + [
                    "STC%d-%s"% (i, v) for v in
                    ["alerted", "Status", "Qty", "xQty", "Price", "Price-alert", "Price-actual", "PnL","Date", "ordID"]
                    for i in range(1,4)])

tracker_portfolio_cols = ",".join([
                "Date", "Symbol", "Trader", 'Channel', "isOpen", "Asset", "Type", "Price", "Qty", "Price-actual", 
                "Prices", "Prices-actual", "Avged", "PnL", "PnL-actual","PnL$", "PnL$-actual"
                ] + [ f"STC-{v}" for v in
                    ["Qty", "Price", "Price-actual", "Prices", "Prices-actual", "Date"]
                    for i in range(1,2)] + ["TrailStats"])
cfg["col_names"] = {
    'portfolio': portfolio_cols,
    'alerts_log': 'Date,Symbol,Trader,action,parsed,msg,portfolio_idx',
    "tracker_portfolio": tracker_portfolio_cols,
    "chan_hist": 'AuthorID,Author,Date,Content,Parsed'
    }
# for leagacy ports
update_port_cols()
# get chan IDs in a dict format
channel_ids_str = cfg.get('discord', 'channel_IDS')
channel_ids = json.loads(channel_ids_str.replace("\n", "").replace(",}", "}"))
