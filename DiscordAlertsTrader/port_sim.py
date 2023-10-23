import time
from typing import List
import pandas as pd
from datetime import date, timedelta
import numpy as np
import matplotlib.pyplot as plt
from thetadata import OptionReqType, OptionRight, DateRange, DataType
from DiscordAlertsTrader.message_parser import parse_symbol

def get_timestamp(row):
        date_time = (row[DataType.DATE] + timedelta(milliseconds=row[DataType.MS_OF_DAY]))
        return date_time.timestamp()

def get_hist_quotes(symbol:str, date_range:List[date], client, interval_size:int=1000):
    # symbol: APPL_092623P426
    # date_range: [date(2021, 9, 24), date(2021, 9, 24)] start and end date, or start date only
    # interval_size: 1000 (milliseconds)

    option = parse_symbol(symbol)
    exp = date(option['exp_year'], option['exp_month'], option['exp_day'])
    right = OptionRight.PUT if option['put_or_call'] == 'P' else OptionRight.CALL
    if len(date_range) == 1:
        drange = DateRange(date_range[0], date_range[0])
    else:
        drange = DateRange(date_range[0], date_range[1])
    
    with client.connect():
            # Make the request
            out = client.get_hist_option(
                req=OptionReqType.QUOTE,  
                root=option['symbol'],
                exp=exp,
                strike=option['strike'],
                right=right,
                date_range=drange,
                interval_size=interval_size
            )

    # Apply the function row-wise to compute the timestamp and store it in a new column
    out['timestamp'] = out.apply(get_timestamp, axis=1)
    out['timestamp'] = out['timestamp'].astype(int)
    out['bid'] = out[DataType.BID]
    out['ask'] = out[DataType.ASK]
    out = out[['timestamp', 'bid', 'ask']]
    out = out[(out['ask']!=0) & (out['bid']!=0)] # remove zero ask
    return out

def save_or_append_quote(quotes, symbol, path_quotes, overwrite=False):
    fname = f"{path_quotes}/{symbol}.csv"
    if overwrite:
        quotes.to_csv(fname, index=False)
        return
    try:
        df = pd.read_csv(fname)
        df = pd.concat([df, quotes], ignore_index=True)
        df = df.sort_values(by=['timestamp']).drop_duplicates(subset=['timestamp'])
    except FileNotFoundError:
        df = quotes
    df.to_csv(fname, index=False)

def period_to_date(period):
    "Convert str to date. Period can be today, yesterday, week, biweek, month, mtd. ytd"
    possible_periods = ['today', 'yesterday', 'week', 'biweek', 'month', "mtd", "ytd"]
    if period not in possible_periods:
        return period
    # Get the current date
    current_date = date.today()

    if period == 'today':
        return current_date
    elif period == 'yesterday':
        return current_date - timedelta(days=1)
    elif period == 'week':
        return current_date - timedelta(days=7)
    elif period == 'biweek':
        return current_date - timedelta(days=14)
    elif period == 'month':
        return current_date - timedelta(days=30)
    elif period == 'mtd':
        return current_date.replace(day=1)
    elif period == 'ytd':
        return current_date.replace(month=1, day=1)
    
def port_cap_trades(data, max_trade_val:int=None, min_con_val:int=None, max_u_qty:int=None, 
                    max_underlying:int=None, max_dte:int=None, min_dte:int=None):
    """Cap portfolio trades

    Parameters
    ----------
    data : pd.DataFrame
        portfolio analysts dataframe
    max_trade_val : int, optional
        max value of the trade, reduce quantity or remove if too large, by default None
    min_con_val : int, optional
        option contract min price, remove if too small, by default None
    max_u_qty : int, optional
        max units trade, by default None
    max_underlying: int, optional
        max value underlying option price, by default None
    max_dte : int, optional
        max days to expiration, by default None
    min_dte : int, optional
        min days to expiration, by default None

    Returns
    -------
    portfolio
        with capped values
    """

    if max_underlying is not None:
        underlying = data['Symbol'].str.extract(r'[C|P](\d+(\.\d+)?)$').iloc[:, 0]
        data['underlying'] = pd.to_numeric(underlying)
        # msk out, neg so NaNs are not removed
        data = data[~(data['underlying'] > max_underlying)]

    if max_dte is not None or min_dte is not None:
        de = data.loc[data['Asset'] == 'option', 'Symbol'].str.extract(r'_(\d{6})').iloc[:, 0]
        de = pd.to_datetime(de, format='%m%d%y').dt.date
        dte = pd.to_timedelta(de - pd.to_datetime(data['Date']).dt.date).dt.days
        # msk out, neg so NaNs are not removed
        msk_out = (dte > max_dte) | (dte < min_dte) 
        data = data[~msk_out]

    if max_u_qty is not None:
        exceeds_cap = data['Qty'] > max_u_qty
        data.loc[exceeds_cap, 'Qty'] = max_u_qty

    if min_con_val is not None:
        option_mult = (data['Asset'] == 'option').astype(int)
        option_mult[option_mult==1] = 100
        con_value = (data['Price'] * option_mult) < min_con_val
        data = data[~con_value | ~(data['Asset'] == 'option')]
    
    if max_trade_val is not None:
        option_mult = (data['Asset'] == 'option').astype(int)
        option_mult[option_mult==1] = 100
        trade_value = data['Qty'] * data['Price'] * option_mult
        exceeds_cap = trade_value > max_trade_val
        data.loc[exceeds_cap, 'Qty'] = np.floor(max_trade_val / (data['Price'] * option_mult))
        data = data[data['Qty'] * data['Price'] * option_mult <= max_trade_val]

    # recalculates pnls
    if any([max_u_qty, max_trade_val]):
        mult =(data['Asset'] == 'option').astype(int) 
        mult[mult==0] = .01  # pnl already in %
        data.loc[:,'PnL$'] = data['Qty'] * data['PnL'] * data['Price'] * mult
        data.loc[:,'PnL$-actual'] = data['Qty'] * data['PnL-actual'] * data['Price-actual'] * mult
        data.loc[:,'PnL$'] = data['PnL$'].round()
        data.loc[:,'PnL$-actual'] = data['PnL$-actual'].round()
    return data

def filter_data(data,exclude={}, filt_author='', filt_date_frm='', filt_date_to='',
                filt_sym='', exc_author='', exc_chn='', exc_sym='', msg_cont='',
                max_trade_val="", min_con_val="", max_u_qty="", max_underlying="", max_dte="", min_dte="",
                filt_chn="", filt_hour_frm="", filt_hour_to=""
                ):
    if len(exclude):
        for k, v in exclude.items():
            if k == "Canceled" and v and "BTO-Status" in data.columns:
                data = data[data["BTO-Status"] !="CANCELED"]
            elif k == "Rejected" and v and "BTO-Status" in data.columns:
                data = data[data["BTO-Status"] !="REJECTED"]
            elif k == "Closed" and v:
                data = data[data["isOpen"] !=0]
            elif k == "Open" and v:
                data = data[data["isOpen"] !=1]
            elif k == "NegPnL" and v:
                col = "PnL" if "PnL" in data else 'PnL'                
                pnl = data[col].apply(lambda x: np.nan if x =="" else eval(x) if isinstance(x, str) else x)     
                data = data[pnl > 0 ]
            elif k == "PosPnL" and v:
                col = "PnL" if "PnL" in data else 'PnL' 
                pnl = data[col].apply(lambda x: np.nan if x =="" else eval(x) if isinstance(x, str) else x)
                data = data[pnl < 0 ]
            elif k == "stocks" and v:
                data = data[data["Asset"] !="stock"]
            elif k == "options" and v:
                data = data[data["Asset"] !="option"]
            elif k == "bto" and v and "Type" in data.columns:
                data = data[data["Type"] !="BTO"]
            elif k == "sto" and v and "Type" in data.columns:
                data = data[data["Type"] !="STO"]
    if filt_author:
        msk = [x.strip() for x in filt_author.split(",")]
        data = data[data['Trader'].str.contains('|'.join(msk), case=False)]
    if filt_date_frm:
        if len(filt_date_frm.split("/")) == 2:
            filt_date_frm = f"{filt_date_frm}/{str(date.today().year)[2:]}"
        filt_date_frm = period_to_date(filt_date_frm)
        msk = pd.to_datetime(data['Date']).dt.date >= pd.to_datetime(filt_date_frm).date()
        data = data[msk]
    if filt_date_to:
        if len(filt_date_to.split("/")) == 2:
            filt_date_to = f"{filt_date_to}/{str(date.today().year)[2:]}"
        filt_date_to =  period_to_date(filt_date_to)
        msk = pd.to_datetime(data['Date']).dt.date <= pd.to_datetime(filt_date_to).date()
        data = data[msk]
    if filt_hour_frm:
        msk = pd.to_datetime(data['Date']).dt.hour >= filt_hour_frm
        data = data[msk]
    if filt_hour_to:
        msk = pd.to_datetime(data['Date']).dt.hour <= filt_hour_to
        data = data[msk]
    if filt_sym:
        msk = [x.strip() for x in filt_sym.split(",")]
        data = data[data['Symbol'].str.contains('|'.join(msk), case=False)]
    if filt_chn:
        msk = [x.strip() for x in filt_chn.split(",")]
        data = data[data['Channel'].str.contains('|'.join(msk), case=False)]
    if exc_author:
        msk = [x.strip() for x in exc_author.split(",")]
        data = data[~data['Trader'].str.contains('|'.join(msk), case=False)]
    if exc_chn and "Channel" in data.columns:
        msk = [x.strip() for x in exc_chn.split(",")]
        data = data[~data['Channel'].str.contains('|'.join(msk), case=False)]
    if exc_sym:
        msk = [x.strip() for x in exc_sym.split(",")]
        data = data[~data['Symbol'].str.contains('|'.join(msk), case=False)]
    if msg_cont:
        data.loc[:, 'Content'] = data['Content'].fillna('')
        data = data[data['Content'].str.contains(msg_cont, case=False)]

    arguments = [max_trade_val, min_con_val, max_u_qty, max_underlying, max_dte, min_dte]
    for i in range(len(arguments)):
        if isinstance(arguments[i], (int,float)):
            arguments[i] = arguments[i]
        elif isinstance(arguments[i], str) and arguments[i].isdigit():            
            arguments[i] = eval(arguments[i])
        else:
            arguments[i] = None
    max_trade_val, min_con_val, max_u_qty, max_underlying, max_dte, min_dte = arguments
    data = port_cap_trades(data, max_trade_val, min_con_val, max_u_qty, max_underlying, max_dte, min_dte)
    return data

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
            actual_value = filtered_quotes.iloc[i]
            # new high
            if actual_value > max_value:
                max_value = actual_value  # Update the maximum value
                trailing_stop = max_value - ts

            # Trailing stop triggered
            if actual_value <= trailing_stop:
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


def calc_buy_trailingstop(data:pd.Series, ts:float, buy_price:float=None):
    """Calculate the trailing stop for a given series of quotes
    Parameters
    ----------
    data : pd.Series
        Series of quotes
    ts : float
        Trailing stop, constant value
    buy_price : float
        Initial buy price
    Returns
    -------
    trigger_price : float
        The price at which the trailing stop was triggered
    trigger_index : int
        The index of the quote at which the trailing stop was triggered
    """
    
    # If pt is None, use the first value of the series
    min_value = buy_price or data.iloc[0]  
    trailing_stop = min_value + ts
    trigger_index = None
    
    for i in range(1, len(data)):
        actual_value = data.iloc[i]
        # New low
        if actual_value < min_value:
            min_value = actual_value  # Update the minimum value
            trailing_stop = min_value + ts

        # Trailing stop triggered
        if actual_value >= trailing_stop:
            trigger_index = i
            break

    if trigger_index is not None:
        trigger_price = data.iloc[trigger_index]
        trigger_index = data.index[trigger_index]
        return trigger_price, trigger_index
    else:
        # If no trigger, return None
        return None, None



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

def calc_roi(quotes:pd.Series, PT:float, TS:float, SL:float, do_plot:bool=False, initial_prices=None, sl_update:list=None,
             avgdown:list=None)->list:
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
    avgdown : list, optional
        list with lists of [percentage price, percentage quantity] default None

    Returns
    -------
    list
        initial price, sell price, ROI with TS, ROI without TS, and sell_index, qty_ratio
    """
    roi = []


    quotes = quotes.dropna()

    if initial_prices is None:
        initial_price = quotes.iloc[0]
    else:
        initial_price = initial_prices
    sl = initial_price * SL
    # average down 
    ds_inf = []
    tot_qty_ratio = 1
    if avgdown is not None:
        # check if ds before PT
        pt = initial_price * PT
        trigger_price, trigger_index, pt_index = calc_PT(quotes, pt)
        for dws in avgdown:            
            sl_index, sl_val = calc_SL(quotes, initial_price *(1-dws[0]/100), [])            
            if (trigger_index is None and sl_index is not None) or \
                (trigger_index and sl_index and trigger_index > sl_index):
                ds_inf.append([sl_index, sl_val, dws[1]/100])
        if len(ds_inf):
            # make average price
            tot_qty_ratio = sum([1] + [i[2] for i in ds_inf])
            initial_price = sum([initial_price] + [i[1]*i[2] for i in ds_inf])/tot_qty_ratio
            quotes = quotes[quotes.index >= ds_inf[-1][0]]
            sl = initial_price * SL
    
    # Calculate the PT, SL and trailing stop levels
    pt = initial_price * PT
    
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
        sell_index = quotes.index[-1]
        if do_plot:
            plt.plot(quotes.index[len(quotes)-1], (quotes.iloc[-1]-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)
    # no TP, use SL
    elif trigger_index is None:
        sell_price = sl_val
        no_ts_sell = sl_val
        sell_index = sl_index
        if do_plot:
            plt.plot(quotes.index.get_loc(sl_index), (sell_price-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)
    # SL before TP
    elif sl_index is not None and int(trigger_index) > int(sl_index) :
        sell_price = sl_val
        no_ts_sell = sl_val
        sell_index = sl_index
        if do_plot:
            plt.plot(quotes.index.get_loc(sl_index), (quotes.loc[sl_index]-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)
    # TP
    else:
        sell_price = trigger_price
        no_ts_sell = quotes.loc[pt_index]
        sell_index = trigger_index
        if do_plot:
            plt.plot(quotes.index.get_loc(trigger_index), (quotes.loc[trigger_index]-quotes.iloc[0])/quotes.iloc[0], marker='o', alpha=.5)

    if do_plot:
        max = quotes.apply(lambda x: (x-quotes.iloc[0])/quotes.iloc[0]).max()
        roi_ = (sell_price - initial_price)/initial_price * 100
        plt.title(f"max: {round(max*100)}%, sell:{round(roi_)}")
        plt.axhline(PT-1, color='green', linestyle='--', label=f'PT {(PT-1)*100}%', alpha=.5)
        plt.axhline(SL-1, color='red', linestyle='--', label=f'SL {(SL-1)*100}%', alpha=.5)
        plt.axhline(0, color='k', linestyle='--', label='bto', alpha=.5)

    prof = [initial_price, sell_price, (sell_price - initial_price)/initial_price * 100, (no_ts_sell - initial_price)/initial_price * 100, sell_index, tot_qty_ratio ]
    roi.append(prof)
    plt.show(block=False)
    return roi