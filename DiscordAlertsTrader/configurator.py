import configparser
import os
import os.path as op
import json

package_dir = os.path.abspath(os.path.dirname(__file__))
assert(op.exists(package_dir+'/config.ini'), 
       FileNotFoundError("config.ini not found, rename condig_example and add discord token"))
# load configuration file
cfg = configparser.ConfigParser()
cfg.read(package_dir+'/config.ini',  encoding='utf-8')

# change data_dir if it is just a folder name
data_dir = cfg['general']['data_dir']
_, ext = os.path.splitext(data_dir)
if ext == "":    
    cfg['general']['data_dir'] = os.path.join(package_dir, "..", data_dir)
    print("full data dir:", cfg['general']['data_dir'])

# add path to file names
for k, v in cfg['portfolio_names'].items():
    cfg['portfolio_names'][k] = op.join(data_dir, v)
cfg['portfolio_names']['mock_portfolio_fname'] = './tests/trader_portfolio_simulated.csv'
cfg['portfolio_names']['mock_alerts_log_fname'] = './tests/trader_logger_simulated.csv'

# Define column names for portfolios and hist messages
portfolio_cols = ",".join([
                "Date", "Symbol", "Trader", "isOpen", "BTO-Status", "Asset", "Type", "Price", "Price-Alert", "Price-Current",
                "uQty", "filledQty", "Avged", "Avged-prices", "exit_plan", "ordID", "Risk", "SL_mental","PnL", "$PnL",
                "PnL-Alert", "$PnL-Alert","PnL-Current","$PnL-Current"
                ] + [
                    "STC%d-%s"% (i, v) for v in
                    ["Alerted", "Status", "xQty", "uQty", "Price", "Price-Alerted", "Price-Current", "PnL","Date", "ordID"]
                    for i in range(1,4)])

tracker_portfolio_cols = ",".join([
                "Date", "Symbol", "Trader", 'Channel', "isOpen", "Asset", "Type", "Price", "Amount", "Price-current", "Prices", "Prices-current", "Avged"
                ] + [ f"STC-{v}" for v in
                    ["Amount", "Price", "Price-current", "Prices", "Prices-current", "PnL", "PnL-current","PnL$", "PnL$-current", "Date"]
                    for i in range(1,2)] + ["TrailStats"])
cfg["col_names"] = {
    'portfolio': portfolio_cols,
    'alerts_log': 'Date,Symbol,Trader,action,parsed,msg,portfolio_idx',
    "tracker_portfolio": tracker_portfolio_cols,
    "chan_hist": 'AuthorID,Author,Date,Content,Parsed'
    } 

# get chan IDs in a dict format
channel_ids_str = cfg.get('discord', 'channel_IDS')
channel_ids = json.loads(channel_ids_str.replace("\n", "").replace(",}", "}"))