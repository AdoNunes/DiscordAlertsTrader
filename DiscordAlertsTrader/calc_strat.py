"read symbols from port and load saved live quotes and calculate profit/loss"
import pandas as pd
import os.path as op
from datetime import datetime, timedelta, date
import numpy as np
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.port_sim import filter_data, calc_trailingstop, calc_roi



def calc_returns(fname_port= cfg['portfolio_names']['tracker_portfolio_name'],
                dir_quotes= cfg['general']['data_dir'] + '/live_quotes',
                last_days= 7,
                max_underlying_price= 500,
                min_price= 50,
                max_dte= 5,
                min_dte= 0,
                exclude_traders= ['enhancedmarket', 'SPY'],
                exclude_symbols= ['SPX',  'QQQ'],
                exclude_channs= "",
                PT=80,
                TS=0,
                SL=45,
                TS_buy= 10,
                max_margin = None
                ):
    """simulate trade and get returns

    Parameters
    ----------
    fname_port : _type_, optional
        path to portfolio, by default cfg['portfolio_names']['tracker_portfolio_name']
    dir_quotes : _type_, optional
        path to quotes, by default cfg['general']['data_dir']+'/live_quotes'
    last_days : int, optional
        subtract today to n prev days, by default 7
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
    exclude_channs : list, optional
        List channels to exclude, by default ""
    PT : int, optional
        Profit target percent, by default 80
    TS : int, optional
        Trailing stop for sell, by default 0
    SL : int, optional
        stop loss percent, by default 45
    TS_buy : int, optional
        trailing stop percent before opening position (for shorting), by default 10
    max_margin : int, optional
        max margin to use for shorting, by default None

    Returns
    -------
    port : pd.DataFrame
        new cols: 'strategy-PnL, 'strategy-PnL$','strategy-entry','strategy-exit'
    no_quote : list
        list of symbols with no quotes
    params : dict
        parameters used for simulation
    """
    param = {'last_days': last_days,
            'max_underlying_price': max_underlying_price,
            'min_price': min_price,
            'max_dte': max_dte,
            'min_dte': min_dte,
            'exclude_traders': exclude_traders,
            'exclude_symbols': exclude_symbols,
            'PT': PT,
            'TS': TS,
            'SL': SL,
            'TS_buy': TS_buy,
            'max_margin': max_margin,
            }
    port = pd.read_csv(fname_port)
    msk = pd.to_datetime(port['Date']).dt.date >= pd.to_datetime(date.today()- timedelta(days=last_days)).date()
    port = port[msk]
    
    port = filter_data(port, 
                    exclude={'stocks':True}, 
                    exc_author=','.join(exclude_traders),
                    exc_chn='', 
                    exc_sym=','.join(exclude_symbols), 
                    min_con_val=min_price, 
                    max_u_qty=1, 
                    max_underlying=max_underlying_price, 
                    max_dte=max_dte, 
                    min_dte=min_dte                  
                    )

    if len(port) == 0:
        print("No trades to calculate")
        exit()

    pt = 1 + PT/100
    ts = TS/100
    sl = 1 - SL/100
    ts_buy = TS_buy/100

    port['strategy-PNL'] = np.nan
    port['strategy-PnL$'] = np.nan
    port['strategy-entry'] = np.nan
    port['strategy-exit'] = np.nan
    port['strategy-close_date'] = pd.NaT   

    no_quote = []
    do_margin = False if max_margin is None else True
    if do_margin:  
        port['margin'] = np.nan  
        port = port.reset_index(drop=True)
    
    for idx, row in port.iterrows():        
        if do_margin:
            trade_margin = row['underlying'] * 100 * 0.2
            trade_open_date = pd.to_datetime(row['Date'])
            open_trades = port.iloc[:idx][(port.iloc[:idx]['strategy-close_date'] >= trade_open_date)]
            margin = open_trades['margin'].sum() + trade_margin
            if margin > max_margin:
                print(f"skipping trade {row['Symbol']} due to margin too high at {margin}")
                continue
            else:
                print("margin", margin, "trade margin", trade_margin, "symbol", row['Symbol'])
        
        # Load data
        fquote = f"{dir_quotes}/{row['Symbol']}.csv"
        if not op.exists(fquote):
            no_quote.append(row['Symbol'])
            continue    
        quotes = pd.read_csv(fquote, on_bad_lines='skip')
        
        # get quotes within trade dates
        dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))

        try:
            # msk = (dates >= pd.to_datetime(row['Date'])) & ((dates <= pd.to_datetime(row['STC-Date']))) & (quotes[' quote'] > 0)
            stc_date = pd.to_datetime(row['STC-Date']).replace(hour=15, minute=50, second=0, microsecond=0)
            msk = (dates >= pd.to_datetime(row['Date'])) & ((dates <= stc_date)) & (quotes[' quote'] > 0)
        except TypeError:
            # continue
            stc_date = row['STC-Date'].replace("T00:00:00+0000", " 15:50:00.000000")
            stc_date = pd.to_datetime(stc_date).replace(hour=16, minute=0, second=0, microsecond=0)
            msk = (dates >= pd.to_datetime(row['Date'])) & ((dates <= pd.to_datetime(stc_date))) & (quotes[' quote'] > 0)

        if not msk.any():
            print("quotes outside with dates", row['Symbol'])
            continue
        
        if do_margin:
            port.loc[idx, 'margin'] = trade_margin

        quotes = quotes[msk].reset_index(drop=True)
        dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))
        quotes_vals = quotes[' quote']

        trigger_index = 0
        price_curr = row['Price-actual']
        if ts_buy:
            price_curr, trigger_index, pt_index = calc_trailingstop(quotes_vals, price_curr,price_curr*ts_buy)
        roi_actual, = calc_roi(quotes_vals.loc[trigger_index:], PT=pt, TS=ts, SL=sl, do_plot=False, initial_prices=price_curr)
        
        port.loc[idx, 'strategy-close_date'] = dates.iloc[roi_actual[-1]]
        pnl = roi_actual[2]
        mult = .1 if row['Asset'] == 'stock' else 1
        pnlu = pnl*roi_actual[0]*mult*row['Qty']
        
        port.loc[idx, 'strategy-PnL'] = pnl
        port.loc[idx, 'strategy-PnL$'] = pnlu
        port.loc[idx,'strategy-entry'] = roi_actual[0]
        port.loc[idx,'strategy-exit'] = roi_actual[1]
        
    return port, no_quote, param

def generate_report(port, param={}, no_quote=None, verbose=True):
    if no_quote is not None and verbose:
        print(f"N trades with no quote: {len(no_quote)}")

    if len(param) > 0 and verbose:
        msg_str = "\nParameters used:"
        for k,v in param.items():
            msg_str += f"{k}: {v} "
        print(msg_str)
        
    port = port[port['strategy-PnL'].notnull()]
    print("Pnl alert: %.2f, Pnl actual: %.2f, Pnl strategy: %.2f" % (
        port['PnL'].mean(), port['PnL-actual'].mean(), port['strategy-PnL'].mean()))
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
                'Date': ['count']
                }
    result_td = port.groupby('Trader').agg(agg_funcs).sort_values(by=('Date', 'count'), ascending=False)
    return result_td


port, no_quote, param = calc_returns(
    fname_port= cfg['portfolio_names']['tracker_portfolio_name'],
    dir_quotes= cfg['general']['data_dir'] + '/live_quotes',
    last_days= 7,
    max_underlying_price= 500,
    min_price= 50,
    max_dte= 5,
    min_dte= 0,
    exclude_traders= ['enhancedmarket', 'SPY'],
    exclude_symbols= ['SPX',  'QQQ'],
    exclude_channs = "",
    PT=80,
    TS=0,
    SL=45,
    TS_buy= 10,
    max_margin = 25000
    )

# print(port[['Date','Symbol','Trader', 'PnL', 'PnL-actual', 'PnL-strategy','PnL$', 'PnL$-actual',
    #             'PnL$-strategy','strategy-entry','strategy-exit', 'strategy-close_date']])

result_td =  generate_report(port, param, no_quote, verbose=True)