import configparser
import os.path as op

# load configuration file
config = configparser.ConfigParser()
config.read('config.ini',  encoding='utf-8')

# add path to file names
data_dir = config['general']['data_dir']
for k, v in config['portfolio_name'].items():
    if "/" in v:
        continue
    config['portfolio_name'][k] = op.join(data_dir, v)

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

config["col_names"] = {
    'portfolio' : portfolio_cols,
    "tracker_portfolio":tracker_portfolio_cols
    } 
