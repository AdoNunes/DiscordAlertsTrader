"read symbols from port and load saved live quotes and calculate profit/loss"
import pandas as pd
import os.path as op
import pytz
from datetime import datetime, timedelta, date, time
import numpy as np
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.message_parser import parse_symbol
from DiscordAlertsTrader.port_sim import filter_data, calc_trailingstop, calc_roi, calc_buy_trailingstop, save_or_append_quote
import matplotlib.pyplot as plt
from DiscordAlertsTrader.marketdata.thetadata_api import ThetaClientAPI
from DiscordAlertsTrader.marketdata.polygon import get_poly_data

def date_local(date_str):
    return pd.to_datetime(date_str).tz_localize('America/New_York').tz_convert('UTC')


def calc_returns(fname_port= cfg['portfolio_names']['tracker_portfolio_name'],
                dir_quotes= cfg['general']['data_dir'] + '/live_quotes',
                order_type = 'any',
                last_days= None,
                filt_date_frm='',
                filt_date_to='',
                stc_date = 'eod', # 'eod' or 'stc alert"
                max_underlying_price= 10000,
                min_price= 1,
                max_dte= 100,
                min_dte= 0,
                filt_hour_frm = "",
                filt_hour_to = "",
                include_authors = "",
                exclude_traders= "",
                exclude_symbols= [],
                invert_contracts=False,
                initial_price = "ask",
                PT=[80],
                pts_ratio = [1],
                TS=0,
                SL=45,
                TS_buy= 10,
                TS_buy_type= 'inverse',
                avg_down=None,
                sl_update = None,
                pt_update = None,
                max_margin = None,
                short_under_amnt = None,
                min_trade_val=None,
                sell_bto=False,
                max_short_val= None,
                verbose= True,
                trade_amount=1,
                trade_type = 'any',
                theta_client = None,
                with_poly = False,
                do_plot = False
                ):
    """simulate trade and get returns

    Parameters
    ----------
    fname_port : _type_, optional
        path to portfolio, by default cfg['portfolio_names']['tracker_portfolio_name']
    dir_quotes : _type_, optional
        path to quotes, by default cfg['general']['data_dir']+'/live_quotes'
    order_type : str, optional
        'any', 'call', 'put', by default 'any'
    last_days : int, optional
        subtract today to n prev days, by default 7
    stc_date : str, optional
        'eod', 'stc alert", 'exp' close trade end of day, when alerted or at exp date, by default 'eod'
    max_underlying_price : int, optional
        max stock price of the option, by default 500
    min_price : int, optional
        min price of option (1 contract), by default 50
    max_dte : int, optional
        max days to expiration for options, by default 5
    min_dte : int, optional
        min days to expiration for options, by default 0
    exclude_traders : list, optional
        List traders to exclude, by default ['enhancedmarket', 'SPY']
    exclude_symbols : list, optional
        List symbols to exclude, by default ['SPX',  'QQQ']
    invert_contracts : bool, optional
        Truns a put in to a call and viceversa, by default False
    initial_price : str, optional
        'ask', 'bid', "price_actual", "ask_+10" == ask +10, by default 'ask'
    PT : list of int, optional
        Profit target percent, by default [80]
    pts_ratio : list of int, optional
        ratio of PT to use, eg [0.4, 0,6] adds up to one, first pt 40%,second 60%, by default [1]
    TS : int, optional
        Trailing stop for sell, by default 0
    SL : int, optional
        stop loss percent, by default 45
    TS_buy : int, optional
        trailing stop percent before opening position (for shorting), by default 10
    TS_buy_type : str, optional
        buy or inverse, by default 'inverse'. If buy, T Stop goes down if price goes down,
        if inverse, T Stop goes up if price goes up
    avg_down : list, optional
        list of lists with [% avg down, % quantity], eg [[30, 50]] average at -30%, 50% initial quantity, by default [0]
    sl_update : list, optional
        list of lists with [ratio triger and sl], eg [[1.3, 1.1]] update SL at 30%, to 10% SLy, by default None
    pt_update : list, optional
        list of lists with [ratio triger and pt], eg [[0.8, 1.1]] update PT at -20%, to 10% PT, by default None
    max_margin : int, optional
        max margin to use for shorting, by default None
    short_under_amnt : int, optional
        for shorting, instead of Qty, qty set by underlying price, eg 400 would be 4 cons for a 100 underlying, by default None
    min_trade_val : int, optional
        min trade value FOR SHORTING, by default None
    sell_bto : bool, optional
        if true BTO get converted to STC, sells options, by default False
    max_short_val : int, optional
        max value of short trade, by default 1000
    verbose: bool, optional
        print verbose, by default False
    trade_amount: int, optional
        original qty, if 1 one contract, > 1 trade value, by default 1
    trade_type: str, optional
        any, bto or sto, by default any
    theta_client: object, optional
        client to get historical quotes, by default None
    with_poly: bool, optional
        use polygon data, by default False
    do_plot: bool, optional
        plot quotes, by default False

    Returns
    -------
    port : pd.DataFrame
        new cols: 'strategy-PnL, 'strategy-PnL$','strategy-entry','strategy-exit'
    no_quote : list
        list of symbols with no quotes
    params : dict
        parameters used for simulation
    """
    assert sum(pts_ratio) in [1,0.9999999999999999], "pts_ratio must add up to 1"
    assert len(pts_ratio) == len(PT), "pts_ratio must have same length as PT"

    with_theta = False if theta_client is None else True
    param = {'last_days': last_days,
            "stc_date":stc_date,
            'order_type': order_type,
            'max_underlying_price': max_underlying_price,
            'min_price': min_price,
            "initial_price": initial_price,
            'max_dte': max_dte,
            'min_dte': min_dte,
            "hour_frm": filt_hour_frm,
            "hour_to": filt_hour_to,
            "invert_contracts":invert_contracts,
            "include_authors": include_authors,
            'exclude_traders': exclude_traders,
            'exclude_symbols': exclude_symbols,
            "invert_contrats": invert_contracts,
            'PT': [PT],
            'pts_ratio' : pts_ratio,
            'TS': TS,
            'SL': SL,
            'TS_buy': TS_buy,
            'TS_buy_type' : TS_buy_type,
            'avg_down': avg_down,
            'sl_update': sl_update,
            'pt_update': pt_update,
            'max_margin': max_margin,
            'short_under_amnt': short_under_amnt,
            'min_trade_val': min_trade_val,
            'sell_bto':sell_bto,
            'trade_amount': trade_amount,
            'trade_type': trade_type
            }
    port = pd.read_csv(fname_port)
    port = port.sort_values(by='Date').reset_index(drop=True)
    if last_days is not None:
        msk = pd.to_datetime(port['Date']).dt.date >= pd.to_datetime(date.today()- timedelta(days=last_days)).date()
        port = port[msk]

    port = filter_data(
        port,
        exclude={'stocks':False, "Open":False},
        filt_author=include_authors,
        exc_author=','.join(exclude_traders),
        filt_date_frm=filt_date_frm,
        filt_date_to=filt_date_to,
        exc_chn='',
        exc_sym=','.join(exclude_symbols),
        min_con_val=min_price,
        max_underlying=max_underlying_price,
        max_dte=max_dte,
        min_dte=min_dte,
        filt_hour_frm=filt_hour_frm,
        filt_hour_to=filt_hour_to
    )

    if trade_type != 'any':
        port = port[port['Type'] == trade_type.upper()]

    if order_type != 'any':
        order_type = order_type.lower()
        ot = 'C' if order_type == 'call' else 'P' if order_type == 'put' else None
        port = port[port['Symbol'].str.split("_").str[1].str.contains(ot)]

    if sell_bto:
        port.loc[port['Type'] == 'BTO', 'Type'] = 'STO'

    # calc underlying, dte, right
    underlying = port['Symbol'].str.extract(r'[C|P](\d+(\.\d+)?)$').iloc[:, 0]
    port['underlying'] = pd.to_numeric(underlying)
    port['hour'] = pd.to_datetime(port['Date']).dt.hour
    de = port.loc[port['Asset'] == 'option', 'Symbol'].str.extract(r'_(\d{6})').iloc[:, 0]
    de = pd.to_datetime(de, format='%m%d%y').dt.date
    dte = pd.to_timedelta(de - pd.to_datetime(port['Date']).dt.date).dt.days
    port['dte'] = dte
    port['right'] = port['Symbol'].str.extract(r'([C|P])\d+(\.\d+)?$').iloc[:, 0]

    if invert_contracts:
        port['Symbol'] = port['Symbol'].str.replace(r'C(\d+)', r'xo\1', regex=True)
        port['Symbol'] = port['Symbol'].str.replace(r'P(\d+)', r'C\1', regex=True)
        port['Symbol'] = port['Symbol'].str.replace(r'xo(\d+)', r'P\1', regex=True)

    port = port.reset_index(drop=True)
    if len(port) == 0:
        print("No trades to calculate")
        exit()

    pt = [1 + p/100 for p in PT]
    ts = TS/100
    sl = 1 - SL/100
    ts_buy = TS_buy/100

    port['strategy-PnL'] = np.nan
    port['strategy-PnL$'] = np.nan
    port['strategy-entry'] = np.nan
    port['strategy-exit'] = np.nan
    port['strategy-close_date'] = pd.NaT
    port['reason_skip'] = np.nan


    do_margin = False if max_margin is None else True
    if do_margin:
        port['margin'] = np.nan
        margin = 0
    # Iterate over the trades
    for idx, row in port.iterrows():
        # idx = 234
        # row = port.loc[idx]
        if pd.isna(row['Price-actual']) and not with_theta and not with_poly:
            if verbose:
                print("no current price, skip")
            port.loc[idx, 'reason_skip'] = 'no current price'
            continue

        if do_margin:
            trade_margin = row['underlying'] * 100 * 0.2
            trade_open_date = pd.to_datetime(row['Date']).tz_localize('America/New_York')
            if idx:
                trades_open = port.iloc[:idx][~port.iloc[:idx]['strategy-close_date'].isnull()]
                if len(trades_open) == 0:
                    this_margin = trade_margin
                    margin = 0
                else:
                    open_trades = trades_open.loc[:idx][trades_open.loc[:idx]['strategy-close_date']>= trade_open_date]
                    margin = open_trades['margin'].sum()
                    # add current margin
                    this_margin = trade_margin + margin
                if this_margin > max_margin:
                    if verbose:
                        print(f"skipping trade {row['Symbol']} due to margin too high at {margin}")
                    port.loc[idx, 'reason_skip'] = 'margin too high'
                    continue

        # get STC date and quotes
        if stc_date == 'eod':
            date_close = row['Date'].replace("T00:00:00+0000", " 15:55:00.000000")
            date_close = pd.to_datetime(date_close).replace(hour=15, minute=55, second=0, microsecond=0)
        elif stc_date == 'stc alert':
            date_close = pd.to_datetime(row['STC-Date'])
            if pd.isna(date_close):
                ord_in = parse_symbol(row['Symbol'])
                date_close = pd.to_datetime(f"{ord_in['exp_month']}/{ord_in['exp_day']}/{ord_in['exp_year']} 15:55:00.000000")
            elif date_close.time() >= time(16,0):
                date_close = date_close.replace(hour=15, minute=55, second=0, microsecond=0)
        elif stc_date == 'exp':
            ord_in = parse_symbol(row['Symbol'])
            date_close = pd.to_datetime(f"{ord_in['exp_month']}/{ord_in['exp_day']}/{ord_in['exp_year']} 15:55:00.000000")

        quotes, port = process_quotes(dir_quotes, idx, port, date_close, with_theta, with_poly, verbose, theta_client)
        if quotes is None:
            continue
        # drop nans
        # quotes = quotes.dropna().reset_index(drop=True)

        # get quotes within trade dates
        dates = quotes['timestamp']
        msk = (dates >= date_local(row['Date']).timestamp()+0) & (dates <= date_local(date_close).timestamp()) & (quotes['ask'] > 0)
        if not msk.any():
            if verbose:
                print("quotes outside with dates", row['Symbol'])
            port.loc[idx, 'reason_skip'] = 'no quotes, outside dates'
            continue

        # get quotes within trade dates, ask and bid
        quotes = quotes[msk].reset_index(drop=True)
        quotes = quotes[3:].reset_index(drop=True)
        # quotes = quotes.iloc[::3]

        bad_data_times = pd.to_datetime(quotes['timestamp'], unit='s', utc=True).dt.tz_convert('America/New_York').dt.time
        bad_data_times = bad_data_times != pd.Timestamp("09:30:01").time()
        quotes = quotes[(quotes['ask']!=0) & (quotes['bid']!=0) & (bad_data_times)].reset_index(drop=True)

        if len(quotes) == 0:
            if verbose:
                print("no quotes", row['Symbol'])
            port.loc[idx, 'reason_skip'] = 'no quotes'
            continue

        # Set initial price
        if 'ask' in initial_price:
            price_curr = quotes['ask'].iloc[0]
        elif 'bid' in initial_price:
            price_curr = quotes['bid'].iloc[0]
        elif 'price_actual' in initial_price:
            price_curr = row['Price-actual']

        offset = None
        if "_" in initial_price:
            offset = initial_price.split("_")[1]
            if "+" in offset:
                price_curr = price_curr *  ( 1 + float(offset[1:])/100)
            elif "-" in offset:
                price_curr = price_curr * ( 1 - float(offset[1:])/100)

        # set bid and ask and last
        if port.loc[idx, 'Type'] == 'BTO':
            bid = quotes['bid']
            ask = quotes['ask']
        elif port.loc[idx, 'Type'] == 'STO':
            bid = quotes['ask']
            ask = quotes['bid']
        if "last" in quotes.columns:
            last = quotes['last']
        else:
            last = bid

        dates = pd.to_datetime(quotes['timestamp'], unit='s', utc=True).dt.tz_convert('America/New_York')

        if not len(ask):
            print("no quotes", row['Symbol'])
            continue

        # # add margin even if not triggered by ts buy
        # if do_margin:
        #     port.loc[idx, 'margin'] = trade_margin

        if do_plot:
            fig, ax1 = plt.subplots()
            tstm = quotes['timestamp']
            tstm -= tstm[0]
            ax1.plot(tstm, bid.values, "-o", label="bid", alpha=0.5)
            ax1.plot(tstm, ask.values, ".", label="ask", alpha=0.5)
            ax1.plot(tstm, last.values, "-.", label="last", alpha=0.5)
            ax1.plot(tstm[0], row['Price'], "rd", label="alert price")
            ax1.plot(tstm[0], row['Price-actual'], "bo", label="actual price")
            # ax2 = ax1.twinx()
            # ax2.bar(tstm, quotes['volume'].values, color='red', alpha=0.5, width=0.5, align='center', bottom=min(bid.values))
            # ax2.set_ylabel('Volume', color='red')

        # Check if initial price is triggered
        trigger_index = 0
        start = price_curr <= ask
        if start.sum():
            trigger_index = start.idxmax()
            ask = ask[trigger_index:]
            bid = bid[trigger_index:]
            last = last[trigger_index:]
            if do_plot:
                plt.plot(tstm.loc[trigger_index], ask.loc[trigger_index], "gp", label="triggered price offset")
        else:
            if verbose:
                print("initial price not triggered", row['Symbol'])
            port.loc[idx, 'reason_skip'] = 'no initial price'
            continue

        # Trigger trailingstops for opening position
        if ts_buy and TS_buy_type == 'inverse':
            price_curr, trigger_index, pt_index = calc_trailingstop(ask, price_curr, price_curr*ts_buy)
            if trigger_index == len(ask)-1:
                if verbose:
                    print("no trigger index", row['Symbol'])
                port.loc[idx, 'reason_skip'] = 'TS buy not triggered'
                continue
        elif ts_buy and TS_buy_type == 'buy':
            price_curr, trigger_index = calc_buy_trailingstop(ask, price_curr*ts_buy, price_curr)
            if trigger_index is None:
                if verbose:
                    print("no TS buy trigger index", row['Symbol'])
                port.loc[idx, 'reason_skip'] = 'TS buy not triggered'
                continue
        elif ts_buy:
            raise TypeError("TS_buy_type must be long or short")

        if do_plot:
            plt.plot(tstm[trigger_index], bid[trigger_index], "go")

        # calculate qty
        if short_under_amnt is not None:
            qty_t = max(1, short_under_amnt//port.loc[idx,'underlying'])
            if max_short_val is not None and qty_t*price_curr*100 > max_short_val:
                qty_t = max(max_short_val// (price_curr*100), 1)
            if min_trade_val is not None:
                if qty_t*price_curr*100 < min_trade_val:
                    if verbose:
                        print("skipping trade due to min trade val", row['Symbol'])
                    port.loc[idx, 'reason_skip'] = 'min trade val'
                    port.loc[idx, 'strategy-close_date'] = dates.loc[1].tz_convert('America/New_York')
                    continue
        elif trade_amount is None:
            qty_t = row['Qty']
        elif trade_amount > 1:
            qty_t = max(trade_amount// (price_curr*100), 1)
        else:
            qty_t = 1

        # check margin for shorting
        if do_margin:
            trades_open = port.iloc[:idx][~port.iloc[:idx]['strategy-close_date'].isnull()]
            this_margin = trade_margin*qty_t
            if len(trades_open):
                open_trades = trades_open.loc[:idx][trades_open.loc[:idx]['strategy-close_date']>= trade_open_date]
                margin = open_trades['margin'].sum()
                # add current margin
                this_margin = margin + trade_margin*qty_t
            if this_margin > max_margin:
                if verbose:
                    print(f"skipping trade {row['Symbol']} due to margin too high at {margin}")
                port.loc[idx, 'reason_skip'] = 'margin too high'
                continue
            # add margin otherwise
            port.loc[idx, 'margin'] = trade_margin*qty_t

        if do_margin and avg_down is not None and (trade_margin*qty_t*len(avg_down) + margin > max_margin):
            avg_down_ = None
            print("skipping avg down due to margin", row['Symbol'])
        else:
            avg_down_ = avg_down

        rois = []
        for ipt in pt:
            roi_actual, = calc_roi(bid.loc[trigger_index:],  PT=ipt, TS=ts, SL=sl, do_plot=False,
                                    initial_prices=price_curr,sl_update=sl_update, avgdown=avg_down_,
                                    pt_update=pt_update,  last=last.loc[trigger_index:], ask=ask.loc[trigger_index:],
                                    action=port.loc[idx, 'Type'])
            rois.append(roi_actual)

        rois_r = np.array(rois)
        # Take avg of rois
        roi_actual[0] = rois_r[0,0]
        roi_actual[1] = rois_r[np.argmax(rois_r[:,1]),1]
        roi_actual[2] = sum([r*q for r,q in zip(rois_r[:,2], pts_ratio)])
        roi_actual[3] = sum([r*q for r,q in zip(rois_r[:,3], pts_ratio)])
        roi_actual[4] = int(rois_r[np.argmax(rois_r[:,4]),4])
        roi_actual[5] = np.max(rois_r[:,5])

        if do_plot:
            ax1.plot(tstm[trigger_index],roi_actual[0], "gx", label="triggered prices")
            for roi in rois:
                ax1.plot(tstm[roi[-2]],roi[1], "ro")
            plt.legend()
            ax1.set_title(f"{row['Symbol']}, {row['Date']}")
            plt.show(block=False)

        if roi_actual[-2] == len(bid)-1:
            port.loc[idx, 'last'] = 1

        dt_close= dates.loc[roi_actual[-2]].tz_convert('America/New_York')
        port.loc[idx, 'strategy-close_date'] = pd.to_datetime(dt_close)
        pnl = roi_actual[2]
        qty_ratio = roi_actual[-1]
        mult = .1 if row['Asset'] == 'stock' else 1
        pnlu = pnl*roi_actual[0]*mult*qty_t*qty_ratio

        # calculate PnL
        port.loc[idx, 'Qty'] = qty_t
        port.loc[idx, 'strategy-trade$'] = roi_actual[0]*100*qty_t
        port.loc[idx, 'strategy-trade$_avg'] = roi_actual[0]*100*qty_t*qty_ratio
        port.loc[idx, 'strategy-PnL'] = pnl
        port.loc[idx, 'strategy-PnL$'] = pnlu
        port.loc[idx,'strategy-entry'] = roi_actual[0]
        port.loc[idx,'strategy-exit'] = roi_actual[1]

        port.loc[idx,'max_pnl'] = round( 100*(bid.max() - port.loc[idx, 'Price-actual'])/port.loc[idx, 'Price-actual'], 2)

        port.loc[idx, 'PnL$'] = port.loc[idx, 'PnL']*port.loc[idx, 'Price']*qty_t
        port.loc[idx, 'PnL$-actual'] = port.loc[idx, 'PnL-actual']*port.loc[idx, 'Price-actual']*qty_t
        if qty_ratio > 1:
            port.loc[idx, 'reason_skip'] = f"avg down {qty_ratio}"
    return port, param


def process_quotes(dir_quotes, idx, port, date_close, with_theta=False, with_poly=False, verbose=False, client: ThetaClientAPI=None):
    """
    Process quotes for a given trade.

    Args:
        dir_quotes (str): Directory path where quotes are stored.
        idx (int): Index of the trade row in the DataFrame.
        port (pandas.DataFrame): DataFrame containing trade data.
        date_close (str): Datetime when to close the trade.
        with_theta (bool, optional): Whether to include theta in processing. Defaults to False.
        with_poly (bool, optional): Whether to include poly in processing. Defaults to False.
        verbose (bool, optional): Whether to print verbose messages. Defaults to False.
        client (object, optional): Client to get historical quotes. Defaults to None.

    Returns:
        quotes, port
    """
    row = port.loc[idx]

    # File path for the quote
    fquote = f"{dir_quotes}/{row['Symbol']}.csv"

    if with_theta or with_poly:
        load_from_disk = False

        # Check if quote file exists
        if op.exists(fquote):
            quotes = pd.read_csv(fquote, on_bad_lines='skip')

            # Check if we have quotes for the trade dates (quotes are full days)
            date_start = pd.to_datetime(row['Date']).date()
            date_end = date_close.date()
            all_dates = [date_start + timedelta(days=x) for x in range((date_end - date_end).days + 1)]
            all_dates = [d for d in all_dates if d.weekday() < 5]

            sampl_ix = min(len(quotes), 1000)
            converted_dates = quotes[::sampl_ix]['timestamp'].apply(
                lambda x:
                    pd.to_datetime(x, unit='s')
                    .tz_localize('UTC')
                    .tz_convert('America/New_York').date()
            ).unique()
            # print("converted_dates", converted_dates)

            # Check if all trade dates have quotes available
            if all([d in converted_dates for d in all_dates]):
                load_from_disk = True

        # If quotes are not loaded from disk, fetch them from the source
        if not load_from_disk:
            try:
                if with_theta:
                    # Fetch quotes using theta
                    dt_b = pd.to_datetime(row['Date']).date()
                    dt_s = date_close.date()
                    # quotes = client.get_hist_quotes(row['Symbol'], [dt_b, dt_s])
                    # geeks = client.get_geeks(row['Symbol'], [dt_b, dt_s])
                    quotes = client.get_hist_trades(row['Symbol'], [dt_b, dt_s])

                    if quotes is None:
                        raise Exception("No quotes")
                else:
                    # Fetch quotes using poly
                    date_start = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S.%f').date().strftime('%Y-%m-%d')
                    date_end = date_close.date().strftime('%Y-%m-%d')

                    quotes = get_poly_data(row['Symbol'], date_start, date_end, 'second',  ask='h', bid='l')
                    date_end = date_close.date().strftime('%Y-%m-%d')

                    quotes = get_poly_data(row['Symbol'], date_start, date_end, 'second',  ask='h', bid='l')
                    quotes['timestamp'] = quotes['timestamp'] // 1000
            except Exception as e:
                if verbose:
                    print("No quotes for", row['Symbol'], e)
                port.loc[idx, 'reason_skip'] = 'no quotes'
                return None, port

            # Save or append quotes
            save_or_append_quote(quotes, row['Symbol'], dir_quotes)
            print("Saving...", row['Symbol'], row['Date'])
    elif not op.exists(fquote):
        port.loc[idx, 'reason_skip'] = 'no quotes'
        return None, port
    else:
        # Load quotes from disk
        quotes = pd.read_csv(fquote, on_bad_lines='skip')
        quotes.rename(columns={' quote_ask':"ask", ' quote' :'bid'}, inplace=True)
    return quotes, port


def generate_report(port, param={}, no_quote=None, verbose=True):
    if no_quote is not None and verbose:
        print(f"N trades with no quote: {len(no_quote)}")

    if len(param) > 0 and verbose:
        msg_str = "\nParameters used:"
        for k,v in param.items():
            msg_str += f"{k}: {v} "
        print(msg_str)

    port = port[port['strategy-PnL'].notnull()]
    port.loc[:,'win'] = port['strategy-PnL'] > 0
    print("Pnl alert: %.2f, Pnl actual: %.2f, Pnl strategy: %.2f, win rate: %.2f" % (
        port['PnL'].mean(), port['PnL-actual'].mean(), port['strategy-PnL'].mean(),
        port['win'].sum()/port['win'].count()
        ))
    print("Pnl $ alert: $%.2f, Pnl actual: $%.2f, Pnl strategy: $%.2f" % (
        port['PnL$'].sum(), port['PnL$-actual'].sum(), port['strategy-PnL$'].sum()))

    # Perform the groupby operation and apply the aggregation functions
    agg_funcs = {'PnL$': 'sum',
                'PnL$-actual': 'sum',
                'PnL': 'mean',
                'PnL-actual': 'mean',
                'strategy-PnL': 'mean',
                'strategy-PnL$': 'sum',
                "Price": ['mean', 'median'],
                "win": 'sum',
                'Date': ['count']
                }

    result_td = port.groupby('Trader').agg(agg_funcs).sort_values(by=('Date', 'count'), ascending=False)
    return result_td

def grid_search(params_dict, PT=[60], TS=[0], SL=[45], TS_buy=[5,10,15,20,25]):
    # params_dict for calc_returns
    res = []
    port_out = None
    for pt in PT:
        for sl in SL:
            for ts_buy in TS_buy:
                for ts in TS:
                    pnl_t = f'pt{pt}' if pt != 0 else ''
                    pnl_t += f'_sl{sl}' if sl != 0 else ''
                    pnl_t += f'_tsb{ts_buy}' if ts_buy != 0 else ''
                    pnl_t += f'_ts{ts}' if ts != 0 else ''

                    pnl_t += f'_ts{ts}' if ts != 0 else ''
                    params_dict['PT'] = [pt]
                    params_dict['SL'] = sl
                    params_dict['TS_buy'] = ts_buy
                    params_dict['TS'] = ts

                    port, param = calc_returns(**params_dict)
                    if port_out is None:
                        port_out = port

                    port_renamed = port[['strategy-PnL', 'strategy-PnL$']].rename(
                        columns={'strategy-PnL': f'%{pnl_t}', 'strategy-PnL$': f'${pnl_t}'})
                    port_out = pd.concat([port_out, port_renamed], axis=1)

                    port = port[port['strategy-PnL'].notnull()]
                    win = (port['strategy-PnL'] > 0).sum()/port['strategy-PnL'].count()
                    res.append([pt, sl, ts_buy, ts, port['strategy-PnL'].mean(), port['strategy-PnL$'].sum(), len(port), win*100])
        print(f"Done with PT={pt}")

    sorted_columns = ['Date', 'Symbol', 'Trader', 'Channel', 'Type','Price',
                        'Price-actual', "Qty",
                        # 'Avged', 'PnL', 'PnL-actual', 'PnL$',  'PnL$-actual', 'STC-Price', 'STC-Price-actual',
                        'underlying', 'dte', 'right', 'bid', 'spread',
                        'hour', 'max_pnl', 'strategy-trade$'] + [col for col in port_out.columns if col.startswith('%')] + [
                            col for col in port_out.columns if col.startswith('$')]
    port_out = port_out[sorted_columns]
    return res, port_out


if __name__ == '__main__':
    import os
    with_theta = True
    with_poly = False
    if with_theta:
        from thetadata import ThetaClient
        client = ThetaClientAPI()
        # client = ThetaClient(username=cfg['thetadata']['username'], passwd=cfg['thetadata']['passwd'])
        dir_quotes = cfg['general']['data_dir'] + '/hist_quotes'
    elif with_poly:
        dir_quotes = cfg['general']['data_dir'] + '/hist_quotes_poly'
        os.makedirs(dir_quotes, exist_ok=True)
        client = None
    else:
        client = None
        dir_quotes = cfg['general']['data_dir'] + '/live_quotes'

    params = {
        'fname_port': 'data/oculus_port.csv',
        'order_type': 'any',
        'last_days': 30,
        'filt_date_frm': "",
        'filt_date_to': "",
        'stc_date':'eod',#'exp', #,'stc alert', #'exp',# ,  #  # 'eod' or
        'max_underlying_price': 40000,
        'min_price': 10,
        'max_dte': 10,
        'min_dte': 0,
        'filt_hour_frm': "",
        'filt_hour_to': "",
        'include_authors': "",
        'exclude_symbols': [],
        'initial_price' : 'ask', # 'ask_+10',
        'PT': [90], #[20,25,35,45,55,65,95,],# [90],#
        'pts_ratio' :[1],#[0.2,0.2,0.2,0.1,0.1,0.1,0.1,],#   [0.4, 0.3, 0.3], #
        'sl_update' :  None, #   [[1.20, 1.05], [1.5, 1.3]], #
        "pt_update" : [ [.3,0.7]], #   None, #
        'avg_down':[[1.5, 1]], #  [[1.1, .1],[1.2, .1],[1.3, .1],[1.4, .2],[1.5, .2],[1.6, .2]], #
        'SL': 90,
        'TS': 0,
        'TS_buy': 0,
        'TS_buy_type':'inverse',
        # 'max_margin': 100000,
        'short_under_amnt' : 2000,
        'min_trade_val': .01,
        'verbose': True,
        'trade_amount': 1000,
        # "sell_bto": True,
        # "max_short_val": 4000,
        "invert_contracts": False,
        "do_plot": False
    }
    import time as tt
    t0 = tt.time()
    port, param = calc_returns(dir_quotes=dir_quotes, theta_client=client, with_poly=with_poly, **params)

    t1 = tt.time()
    print(f"Time to calc returns: {t1-t0:.2f} sec")

    sport = port[['Date','Symbol','Trader', 'Price', 'strategy-PnL',
                'strategy-PnL$','strategy-entry','strategy-exit', 'strategy-close_date','reason_skip']] #

    result_td =  generate_report(port, param, None, verbose=True)

    if 0:
        import matplotlib.pyplot as plt

        stat_type =  'strategy-PnL' # 'PnL' #  'PnL-actual'#
        stat_typeu = stat_type.replace("PnL", "PnL$")
        fig, axs = plt.subplots(2, 2, figsize=(10, 10))

        nwin = result_td['win']['sum'].iloc[0]
        ntot = result_td['Date']['count'].iloc[0]
        nlost = ntot - nwin

        winr = f"{nwin}(w)-{nlost}(l)/{ntot}(t)"
        winp = round((result_td['win']['sum'].iloc[0]/result_td['Date']['count'].iloc[0])*100)
        pnl_emp =  nwin* np.mean(param['PT'][0]) - nlost*param['SL']

        excl = ''
        if param['exclude_symbols']:
            excl = f"(no {param['exclude_symbols']})"
        title = f"{param['include_authors']} {excl} winrate {winp}% {winr}, trade amount {param['trade_amount']}" \
            + f" \nat market: avg PnL%={port['strategy-PnL'].mean():.2f}, "\
                +f"${port['strategy-PnL$'].sum():.0f}" \
                    + f"\nTS_buy {param['TS_buy']}, PT {param['PT']}, TS {param['TS']},  SL {param['SL']}"
                # + f" \nat set order: avg PnL%={pnl_emp/ntot:.2f}, "\
                    # +f" ${param['trade_amount']*(pnl_emp/100):.0f} \n" \

        fig.suptitle(title)
        port[stat_typeu].cumsum().plot(ax=axs[0,0], title=f'cumulative {stat_typeu}', grid=True, marker='o', linestyle='dotted')
        axs[0,0].set_xlabel("Trade number")
        axs[0,0].set_ylabel("$")

        port[stat_type].cumsum().plot(ax=axs[0,1], title='cumulative '+stat_type, grid=True, marker='o', linestyle='dotted')
        axs[0,1].set_xlabel("Trade number")
        axs[0,1].set_ylabel("%")

        port[stat_typeu].plot(ax=axs[1,0], title=stat_typeu, grid=True, marker='o', linestyle='dotted')
        axs[1,0].set_xlabel("Trade number")
        axs[1,0].set_ylabel("$")

        port[stat_type].plot(ax=axs[1,1], title=stat_type, grid=True, marker='o', linestyle='dotted')
        axs[1,1].set_xlabel("Trade number")
        axs[1,1].set_ylabel("%")
        plt.show(block=True)

    if 0:
        params['theta_client'] = client
        params['with_poly'] = with_poly
        params['dir_quotes'] = dir_quotes
        # res, port_out = grid_search(params, PT= [30, 40], SL=[30], TS_buy=[0], TS= [0])
        res, port_out = grid_search(
            params,
            PT= list([5] + np.arange(10,150, 10)) + [180, 200,250,300],
            SL=np.arange(20,101,10),
            TS_buy=[0],
            TS=[0],
        )
        # res, port_out = grid_search(params, PT= list[30,60,80,120,170,200,250,300] , SL=[50, 80,90], TS_buy=[0], TS= [0])

        res = np.stack(res)
        sorted_indices = np.argsort(res[:, 4])
        sorted_array = res[sorted_indices].astype(int)
        print(sorted_array[:20])
        hdr = ['PT', 'SL', 'TS_buy', 'TS', 'pnl', 'pnl$', 'trade count', 'win rate']

        df = pd.DataFrame(sorted_array, columns=hdr)

        f_t_Date = f"from_{pd.to_datetime(port_out['Date']).min().date().strftime('%y_%m_%d')}"+\
                    f"_to_{pd.to_datetime(port_out['Date']).max().date().strftime('%y_%m_%d')}"
        pname = params['fname_port'].split("/")[-1].split('_port.csv')[0]
        df.to_csv(f"data/analysis/{pname}{param['include_authors']}_grid_search_{f_t_Date}_ask_.5avgdown.csv", index=False)
        port_out.to_csv(f"data/analysis/{pname}{param['include_authors']}_port_strats_{f_t_Date}_ask_.5avgdown.csv", index=False)
        # PT 40,  SL 20,  trailing stop starting at PT: 25,    PNL avg : 5%,  return: $2750,   num trades: 53
        # print(result_td)
