"read symbols from port and load saved live quotes and calculate profit/loss"
import pandas as pd
import os.path as op
from datetime import datetime, timedelta
import numpy as np
from DiscordAlertsTrader.configurator import cfg
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

def calc_trailingstop(data:pd.Series, pt:float, ts:float):
    """Calculate the trailing stop for a given series of quotes
    Parameters
    ----------
    data : pd.Series
        Series of quotes
    pt : float
        Profit target
    ts : float
        Trailing stop
    Returns
    -------
    trigger_price : float
        The price at which the trailing stop was triggered
    trigger_index : int
        The index of the quote at which the trailing stop was triggered
    pt_index : int
        The index of the quote at which the profit target was reached
    """
    start = data >= pt
    if start.sum():
        pt_index = start.idxmax()
        filtered_quotes = data.loc[pt_index:]

        # Loop over each point and check if new max or TS triggered
        max_value = filtered_quotes.iloc[0]
        trailing_stop = max_value - ts
        trigger_index = None
        for i in range(1, len(filtered_quotes)):
            current_value = filtered_quotes.iloc[i]
            # new high
            if current_value > max_value:
                max_value = current_value  # Update the maximum value
                trailing_stop = max_value - ts

            # Trailing stop triggered
            if current_value <= trailing_stop:
                trigger_index = i
                break

        if trigger_index:
            trigger_price = filtered_quotes.iloc[trigger_index]
            trigger_index = filtered_quotes.index[trigger_index]
        else:
            # If no trigger, then use the last value
            trigger_index = filtered_quotes.index[-1]
            trigger_price = filtered_quotes.loc[trigger_index]

        return trigger_price, trigger_index, pt_index
    else:
        return None, None, None


def calc_SL(data:pd.Series, sl:float, update:list=None):
    """Calculate the StopLoss for a given series of quotes
    Parameters
    ----------
    data : pd.Series
        Series of quotes
    sl : float
        initial stop loss
    update : list, optional
        List of tuples with target and new stop loss, by default None
    Returns
    -------
    sl_price : float
        The price at which the stop loss was triggered
    sl_index : int
        The index of the quote at which the stop loss was triggered
    """

    start = data <= sl
    sl_inx_vals = []
    # normal SL
    if start.sum():
        sl_index = start.idxmax()
        sl_val = data.loc[sl_index]
        sl_inx_vals.append([sl_index, sl_val])
    # SL update after PT
    if update is not None:
        for pt, new_sl in update:
            start = data >= pt
            # if PT reached
            if start.sum():
                pt_index = start.idxmax()
                filtered_quotes = data.loc[pt_index:]
                sl_trig = filtered_quotes <= new_sl
                # if SL reached
                if sl_trig.sum():
                    sl_index = sl_trig.idxmax()
                    sl_val = data.loc[sl_index]
                    sl_inx_vals.append([sl_index, sl_val])
    if sl_inx_vals:
        # get the min SL
        inx = np.argmin([int(i[0]) for i in sl_inx_vals])
        sl_inx_vals = sl_inx_vals[inx]
        return sl_inx_vals
    else:
        return None, None

def calc_PT(data:pd.Series, pt:float):
    """Calculate the Profit Target for a given series of quotes
    
    Parameters
    ----------
    Data : pd.Series
        Series of quotes
    pt : float
        Profit target
    
    Returns
    -------
    list
        pt_value, pt_index, pt_index    
    """
    
    start = data >= pt
    # normal SL
    if start.sum():
        pt_index = start.idxmax()
        pt_val = data.loc[pt_index]
        return pt_val, pt_index, pt_index
    return None, None, None
    
def calc_roi(quotes:pd.Series, PT:float, TS:float, SL:float, do_plot:bool=False, initial_prices=None, sl_update:list=None)->list:
    """Calculate roi for a given series of quotes

    Parameters
    ----------
    quotes : pd.Series
        quote values, each row is a quote, col a value
    PT : float
        profit target, ratio. 125% = 2.25
    TS : float
        trailing stop activated when PT is reached
    SL : float
        stop loss
    do_plot : bool, optional
        option to plot everyquote, by default False
    initial_price : float, optional
        initial price, by default None
    sl_update : list, optional
        list of tuples with target and new stop loss, by default None

    Returns
    -------
    list
        initial price, sell price, ROI with TS, ROI without TS
    """
    roi = []


    quotes = quotes.dropna()

    if initial_prices is None:
        initial_price = quotes.iloc[0]
    else:
        initial_price = initial_prices

    # Calculate the PT, SL and trailing stop levels
    pt = initial_price * PT
    sl = initial_price * SL
    ts = initial_price * TS
    if TS == 0:
        trigger_price, trigger_index, pt_index = calc_PT(quotes, pt)
    else:
        trigger_price, trigger_index, pt_index = calc_trailingstop(quotes, pt, ts)

    # convert SL update into price
    new_update = None
    if sl_update:
        new_update = []
        for upt, usl in sl_update:
            new_update.append([initial_price *upt, initial_price * usl])
        # print(f"initial {initial_price}, PT {pt} Sl {sl} update{new_update}")
    sl_index, sl_val = calc_SL(quotes, sl, new_update)

    if do_plot:
        plt.figure()
        quotes.apply(lambda x: (x-quotes.iloc[0])/quotes.iloc[0]).plot()

    # no TP no SL, then use the last value
    if trigger_index is None and sl_index is None:
        sell_price = quotes.iloc[-1]
        no_ts_sell = sell_price
        if do_plot:
            plt.plot(quotes.index[len(quotes)-1], (quotes.iloc[-1]-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)
    # no TP, use SL
    elif trigger_index is None:
        sell_price = sl_val
        no_ts_sell = sl_val
        if do_plot:
            plt.plot(quotes.index.get_loc(sl_index), (sell_price-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)
    # SL before TP
    elif sl_index is not None and int(trigger_index) > int(sl_index) :
        sell_price = sl_val
        no_ts_sell = sl_val
        if do_plot:
            plt.plot(quotes.index.get_loc(sl_index), (quotes.loc[sl_index]-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)
    # TP
    else:
        sell_price = trigger_price
        no_ts_sell = quotes.loc[pt_index]
        if do_plot:
            plt.plot(quotes.index.get_loc(trigger_index), (quotes.loc[trigger_index]-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)

    if do_plot:
        max = quotes.apply(lambda x: (x-quotes.iloc[0])/quotes.iloc[0]).max()
        roi_ = (sell_price - initial_price)/initial_price * 100
        plt.title(f"max: {round(max*100)}%, sell:{round(roi_)}")
        plt.axhline(PT-1, color='green', linestyle='--', label=f'PT {(PT-1)*100}%', alpha=.5)
        plt.axhline(SL-1, color='red', linestyle='--', label=f'SL {(SL-1)*100}%', alpha=.5)
        plt.axhline(0, color='k', linestyle='--', label='bto', alpha=.5)

    prof = [initial_price, sell_price, (sell_price - initial_price)/initial_price * 100, (no_ts_sell - initial_price)/initial_price * 100 ]
    roi.append(prof)
    plt.show(block=False)
    return roi

def parse_option_info(symbol):
    option_inf = {
    "symbol": symbol.split('_')[0],
    "date": symbol.split('_')[1][:6],
    "otype": symbol.split('_')[1][6],
    "strike": symbol.split('_')[1][7:],
    }
    return option_inf

def calculate_days_to_expiration(row):
    option_date_str = parse_option_info(row['Symbol'])['date']
    option_date = datetime.strptime(option_date_str, '%m%d%y').date()
    expiration_date = pd.to_datetime(row['Date']).date()
    days_to_expiration = (option_date - expiration_date).days
    return days_to_expiration

def port_max_per_trade(port, max_per_trade:float):
    "Limit the max amount per trade"
    option_mult = (port['Asset'] == 'option').astype(int)
    option_mult[option_mult==1] = 100
    trade_value = port['Amount'] * port['Price'] * option_mult
    exceeds_cap = trade_value > max_per_trade
    port.loc[exceeds_cap, 'Amount'] = np.floor(max_per_trade / (port['Price'] * option_mult)) 
    port = port[port['Amount'] * port['Price'] * option_mult <= max_per_trade]
    mult =(port['Asset'] == 'option').astype(int) 
    mult[mult==0] = .01  # pnl already in %
    port['STC-PnL$'] = port['Amount'] * port['STC-PnL'] * port['Price'] * mult
    port['STC-PnL$-current'] = port['Amount'] * port['STC-PnL-current'] * port['Price-current'] * mult
    port['STC-PnL$'] = port['STC-PnL$'].round()
    port['STC-PnL$-current'] = port['STC-PnL$-current'].round()
    return port

fname_port = cfg['portfolio_names']['tracker_portfolio_name']
port = pd.read_csv(fname_port)
dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
ntrades = len(port)

print(f"From {len(port)} trades, removing open trades: {(~(port['isOpen']==0)).sum()} open, not options: " +\
    f"{(~(port['Asset']=='option')).sum()} and with no current price: {port['Price-current'].isna().sum()}")

port = port[(port['isOpen']==0) & (port['Asset']=='option') & ~port['Price-current'].isna()]

odte_only = True
port['days_to_expiration'] = port.apply(calculate_days_to_expiration, axis=1)
if odte_only:
    print("Keeping only trades with 0 dtoe, removing: ", (port['days_to_expiration']!=0).sum())
    port = port[port['days_to_expiration']==0]

print(f"Setting trades to a max of $1000, removing {len(port)- len(port_max_per_trade(port, 1000))} trades")
port = port_max_per_trade(port, 1000)


# strategies: PT and SL, delayed entry
print(f"Calculating strategy pnl... with {len(port)} trades")

delayed_entry = 0
not_entred = []
pnls, pnlus = [], []
port['STC-PnL-strategy'] = np.nan
port['STC-PnL$-strategy'] = np.nan

no_quote = []
for idx, row in port.iterrows():
    
    # Load data
    fquote = f"{dir_quotes}/{row['Symbol']}.csv"
    if not op.exists(fquote):
        no_quote.append(row['Symbol'])
        continue    
    quotes = pd.read_csv(fquote, on_bad_lines='skip')
    
    # get quotes within trade dates
    dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))
    try:
        msk = (dates >= pd.to_datetime(row['Date'])) & ((dates <= pd.to_datetime(row['STC-Date']))) & (quotes[' quote'] > 0)
    except TypeError:
        stc_date = row['STC-Date'].replace("T00:00:00+0000", " 16:00:00.000000")
        msk = (dates >= pd.to_datetime(row['Date'])) & ((dates <= pd.to_datetime(stc_date))) & (quotes[' quote'] > 0)
        # print("error with dates", row['Symbol'], row['STC-Date'])
        # continue
    
    if not msk.any():
        print("quotes outside with dates", row['Symbol'])
        continue

    quotes = quotes[msk].reset_index(drop=True)
    dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))
    quotes_vals = quotes[' quote']
    
    price_alert = row['Price']
    price_curr = row['Price-current']
    
    # roi_alert, = calc_roi(quotes_vals, PT=1.75, TS=0, SL=.5, do_plot=False, initial_prices=price_alert)
    roi_current, = calc_roi(quotes_vals, PT=1.45, TS=0, SL=0, do_plot=False, initial_prices=price_curr)
    
    pnl = roi_current[2]
    mult = .1 if row['Asset'] == 'stock' else 1
    if mult == .1: raise Exception("There should be no stocks in the portfolio")
    pnlu = pnl*row['Amount']*roi_current[0]*mult
    
#     # price_delayed = price_curr + (price_curr*(price_curr/100))
#     # if delayed_entry > 0:
#     #     msk = quotes[' quote'] >= price_delayed
#     # elif delayed_entry < 0:
#     #     msk = quotes[' quote'] <= price_delayed
#     # else:
#     #     msk = quotes[' quote'] == price_curr
#     # if not msk.any():
#     #     not_entred.append(row['Symbol'])
#     #     continue
    

#     # price_delayed = quotes.loc[msk.idxmax(), ' quote']

#     sell_curr = row['STC-Price-current']
#     if pd.isna(row['STC-Price-current']):        
#         sell_curr = quotes.iloc[-1][' quote']
#         if not (pd.to_datetime(row['STC-Date']) - datetime.fromtimestamp(quotes.iloc[-1]['timestamp'])) < timedelta(seconds=300):
#             print ('date not matched by {} seconds'.format((pd.to_datetime(row['STC-Date']) - datetime.fromtimestamp(quotes.iloc[-1]['timestamp'])).seconds))
#             continue
    
    # pnl = (sell_curr - price_delayed)/price_delayed*100
    # mult = .1 if row['Asset'] == 'stock' else 1
    # pnlu = pnl*row['STC-Amount']*price_delayed*mult
    
    port.loc[idx, 'STC-PnL-strategy'] = pnl
    port.loc[idx, 'STC-PnL$-strategy'] = pnlu
    
    pnls.append([row['STC-PnL'], row['STC-PnL-current'], pnl])
    pnlus.append([row['STC-PnL$'], row['STC-PnL$-current'], pnlu])

print(f"N trades with no quote: {len(no_quote)}, N trades with no entry: {len(not_entred)}")
print(f"Strategy with {len(pnlus)} trades")
pnls_m = np.nanmean(np.array(pnls) , axis=0)
print("Pnl alert: %.2f, Pnl current: %.2f, Pnl strategy: %.2f" % (pnls_m[0], pnls_m[1], pnls_m[2]))
pnlus_m = np.nansum(np.array(pnlus) , axis=0)
print("Pnl $ alert: %.2f, Pnl $ current: %.2f, Pnl $ strategy: %.2f" % (pnlus_m[0], pnlus_m[1], pnlus_m[2]))