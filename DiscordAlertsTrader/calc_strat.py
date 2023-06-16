"read symbols from port and load saved live quotes and calculate profit/loss"
import pandas as pd
import os.path as op
from datetime import datetime, timedelta
import numpy as np
from DiscordAlertsTrader.configurator import cfg

fname_port = cfg['portfolio_names']['tracker_portfolio_name']
port = pd.read_csv(fname_port)
dir_quotes = cfg['general']['data_dir'] + '/live_quotes'


port = port[port['isOpen']==0]

delayed_entry = 0
not_entred = []
pnls, pnlus = [], []
port['STC-PnL-strategy'] = np.nan
port['STC-PnL$-strategy'] = np.nan

no_quote = []
for idx, row in port.iterrows():
    
    fquote = f"{dir_quotes}/{row['Symbol']}.csv"
    if not op.exists(fquote):
        no_quote.append(row['Symbol'])
        continue

    quotes = pd.read_csv(fquote, on_bad_lines='skip')
    dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))
    try:
        msk = (dates >= pd.to_datetime(row['Date'])) & ((dates <= pd.to_datetime(row['STC-Date'])))
    except TypeError:
        continue
    
    if not msk.any():
        continue

    quotes = quotes[msk].reset_index(drop=True)
    dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))
    
    price_alert = row['Price']
    price_curr = row['Price-current']
    
    price_delayed = price_alert + (price_alert*(delayed_entry/100))
    
    msk = quotes[' quote'] <= price_delayed
    if not msk.any():
        not_entred.append(row['Symbol'])
        continue
    
    sell_curr = row['STC-Price-current']
    if pd.isna(row['STC-Price-current']):        
        sell_curr = quotes.iloc[-1][' quote']
        if not (pd.to_datetime(row['STC-Date']) - datetime.fromtimestamp(quotes.iloc[-1]['timestamp'])) < timedelta(seconds=100):
            print ('date not matched')
    
    pnl = (sell_curr - price_delayed)/price_delayed*100
    mult = .1 if row['Asset'] == 'stock' else 1
    pnlu = pnl*row['STC-Amount']*price_delayed*mult
    
    port.loc[idx, 'STC-PnL-strategy'] = pnl
    port.loc[idx, 'STC-PnL$-strategy'] = pnlu
    
    pnls.append([row['STC-PnL'], row['STC-PnL-current'], pnl])
    pnlus.append([row['STC-PnL$'], row['STC-PnL$-current'], pnlu])

pnls_m = np.nanmean(np.array(pnls) , axis=0)
print("Pnl alert: %.2f, Pnl current: %.2f, Pnl strategy: %.2f" % (pnls_m[0], pnls_m[1], pnls_m[2]))
pnlus_m = np.nanmean(np.array(pnlus) , axis=0)
print("Pnl $ alert: %.2f, Pnl $ current: %.2f, Pnl $ strategy: %.2f" % (pnlus_m[0], pnlus_m[1], pnlus_m[2]))