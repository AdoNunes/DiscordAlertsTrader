"read symbols from port and load saved live quotes and calculate profit/loss"
import pandas as pd
import os.path as op
import pytz
from datetime import datetime, timedelta, date
import numpy as np
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.port_sim import filter_data, calc_trailingstop, calc_roi, calc_buy_trailingstop
import matplotlib.pyplot as plt

do_plot = 0
def calc_returns(fname_port= cfg['portfolio_names']['tracker_portfolio_name'],
                dir_quotes= cfg['general']['data_dir'] + '/live_quotes',
                last_days= None,
                filt_date_frm='',
                filt_date_to='',
                stc_date = 'eod', # 'eod' or 'stc alert"
                max_underlying_price= 5000,
                min_price= 10,
                max_dte= 500,
                min_dte= 0,
                filt_hour_frm = "",
                filt_hour_to = "",
                include_authors = "",
                exclude_traders= [ 'SPY'],
                exclude_symbols= ['SPX',  'QQQ'],
                PT=80,
                TS=0,
                SL=45,
                TS_buy= 10,
                TS_buy_type= 'inverse',
                max_margin = None,
                verbose= True,
                trade_amount=1,
                trade_type = 'any'
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
    stc_date : str, optional
        'eod' or 'stc alert" close trade end of day or when alerted, by default 'eod'
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
    TS_buy_type : str, optional
        buy or inverse, by default 'inverse'. If buy, T Stop goes down if price goes down,
        if inverse, T Stop goes up if price goes up
    max_margin : int, optional
        max margin to use for shorting, by default None
    verbose: bool, optional
        print verbose, by default False
    trade_amount: int, optional
        none:original qty, if 1 one contract, > 1 trade value, by default 1
    trade_type: str, optional
        any, bto or sto, by default any

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
             "stc_date":stc_date,
            'max_underlying_price': max_underlying_price,
            'min_price': min_price,
            'max_dte': max_dte,
            'min_dte': min_dte,
            "hour_frm": filt_hour_frm,
            "hour_to": filt_hour_to,
            "include_authors": include_authors,
            'exclude_traders': exclude_traders,
            'exclude_symbols': exclude_symbols,
            'PT': PT,
            'TS': TS,
            'SL': SL,
            'TS_buy': TS_buy,
            'TS_buy_type' : TS_buy_type,
            'max_margin': max_margin,
            'trade_amount': trade_amount,
            'trade_type': trade_type
            }
    port = pd.read_csv(fname_port)
    if last_days is not None:
        msk = pd.to_datetime(port['Date']).dt.date >= pd.to_datetime(date.today()- timedelta(days=last_days)).date()
        port = port[msk]
    
    port = filter_data(port, 
                    exclude={'stocks':True},
                    filt_author=include_authors, 
                    exc_author=','.join(exclude_traders),
                    filt_date_frm= filt_date_frm,
                    filt_date_to= filt_date_to,
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
    port = port.reset_index(drop=True)
    if len(port) == 0:
        print("No trades to calculate")
        exit()

    pt = 1 + PT/100
    ts = TS/100
    sl = 1 - SL/100
    ts_buy = TS_buy/100

    port['strategy-PnL'] = np.nan
    port['strategy-PnL$'] = np.nan
    port['strategy-entry'] = np.nan
    port['strategy-exit'] = np.nan
    port['strategy-close_date'] = pd.NaT   
    port['reason_skip'] = np.nan
    
    no_quote = []
    do_margin = False if max_margin is None else True
    if do_margin:  
        port['margin'] = np.nan  
        port = port.reset_index(drop=True)
        qty_t = 1
    
    for idx, row in port.iterrows(): 
        # row = port.iloc[110]
        if pd.isna(row['Price-actual']):
            if verbose:
                print("no current price, skip")
            port.loc[idx, 'reason_skip'] = 'no current price'
            continue
        price_curr = row['Price-actual']
        
        if do_margin:
            trade_margin = row['underlying'] * 100 * 0.2
            trade_open_date = pd.to_datetime(row['Date'])
            open_trades = port.iloc[:idx][(port.iloc[:idx]['strategy-close_date'] >= trade_open_date)]
            margin = open_trades['margin'].sum() + trade_margin
            if margin > max_margin:
                if verbose:
                    print(f"skipping trade {row['Symbol']} due to margin too high at {margin}")
                port.loc[idx, 'reason_skip'] = 'margin too high'
                continue
            # else:
                # print("margin", margin, "trade margin", trade_margin, "symbol", row['Symbol'])
        
        # Load data
        fquote = f"{dir_quotes}/{row['Symbol']}.csv"
        if not op.exists(fquote):
            if verbose:
                no_quote.append(row['Symbol'])
            port.loc[idx, 'reason_skip'] = 'no quotes'
            continue    
        quotes = pd.read_csv(fquote, on_bad_lines='skip')

            
        # get quotes within trade dates
        dates = quotes['timestamp']#.apply(lambda x: datetime.fromtimestamp(x))
        
        if 'bid' in quotes:
            ask = quotes['ask']
        else:
            ask = quotes[' quote']
        
        if stc_date == 'eod':
            date_close = row['Date'].replace("T00:00:00+0000", " 15:55:00.000000")
            date_close = pd.to_datetime(date_close).replace(hour=15, minute=55, second=0, microsecond=0)
        elif stc_date == 'stc alert':
            date_close = pd.to_datetime(row['STC-Date'].replace("T00:00:00+0000", " 15:55:00.000000"))

        msk = (dates >= pd.to_datetime(row['Date']).timestamp()) & (dates <= pd.to_datetime(date_close).timestamp()) & (ask > 0)

        if not msk.any():
            if verbose:
                print("quotes outside with dates", row['Symbol'])
            port.loc[idx, 'reason_skip'] = 'no quotes, outside dates'
            continue

        quotes = quotes[msk].reset_index(drop=True)
        
        
        if 'bid' in quotes:
            bid = quotes['bid']
            ask = quotes['ask']
            dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x, tz=pytz.utc))
            price_curr = ask.iloc[0]
        else:
            bid = quotes[' quote']
            ask = quotes[' quote']
            dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))

        
        # add margin even if not triggered by ts buy
        if do_margin:
            port.loc[idx, 'margin'] = trade_margin
        
        if do_plot:
            plt.figure()
            tstm = quotes['timestamp']
            tstm -= tstm[0]
            plt.plot(tstm,bid.values, "-o")
            plt.plot(tstm[0], price_curr, "bo")
            
        trigger_index = 0       
        if ts_buy and TS_buy_type == 'inverse':         
            price_curr, trigger_index, pt_index = calc_trailingstop(bid, 0, price_curr*ts_buy)
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
            plt.plot(tstm[trigger_index],bid[trigger_index], "go")
        
        roi_actual, = calc_roi(bid.loc[trigger_index:], PT=pt, TS=ts, SL=sl, do_plot=False, initial_prices=price_curr)
        
        if do_plot:
            plt.plot(tstm[roi_actual[-1]],roi_actual[1], "ro")
            plt.show(block=False)
        
        if roi_actual[-1] == len(bid)-1:        
            port.loc[idx, 'last'] = 1
            
        port.loc[idx, 'strategy-close_date'] = dates.iloc[roi_actual[-1]]
        pnl = roi_actual[2]
        mult = .1 if row['Asset'] == 'stock' else 1

        if trade_amount is None:
            qty_t = row['Qty']        
        elif trade_amount > 1:
            qty_t = trade_amount// (roi_actual[0]*100)
        else:
            qty_t = 1
        pnlu = pnl*roi_actual[0]*mult*qty_t
        
        port.loc[idx, 'strategy-PnL'] = pnl
        port.loc[idx, 'strategy-PnL$'] = pnlu
        port.loc[idx,'strategy-entry'] = roi_actual[0]
        port.loc[idx,'strategy-exit'] = roi_actual[1]
        
        port.loc[idx, 'PnL$'] = port.loc[idx, 'PnL']*port.loc[idx, 'Price']*qty_t
        port.loc[idx, 'PnL$-actual'] = port.loc[idx, 'PnL-actual']*port.loc[idx, 'Price-actual']*qty_t


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
    for pt in PT:
        for sl in SL:
            for ts_buy in TS_buy:
                for ts in TS:
                    params_dict['PT'] = pt
                    params_dict['SL'] = sl
                    params_dict['TS_buy'] = ts_buy
                    params_dict['TS'] = ts
                    
                    port, no_quote, param = calc_returns(**params_dict)                    
                    port = port[port['strategy-PnL'].notnull()]        
                    win = (port['strategy-PnL'] > 0).sum()/port['strategy-PnL'].count() 
                    res.append([pt, sl, ts_buy, ts, port['strategy-PnL'].mean(), port['strategy-PnL$'].sum(), len(port), win*100])
        print(f"Done with PT={pt}")
    return res



params_bry = {
    'fname_port':  'data/bryce_short_port.csv', #cfg['portfolio_names']['tracker_portfolio_name'], # 
    'dir_quotes': cfg['general']['data_dir'] + '/hist_quotes', #'/live_quotes', # 
    'last_days': None,
    'filt_date_frm': '',
    'filt_date_to': '',
    'stc_date': 'eod',  # 'eod' or 'stc alert"
    'max_underlying_price': "",
    'min_price': 10,
    'max_dte': 500,
    'min_dte': 0,
    'filt_hour_frm': "",
    'filt_hour_to': "",
    'include_authors': "bryce,Bryce000",
    'exclude_traders': [ 'cow',  'spy','me_short', 'mage','joker','tradewithnando','Father#4214',"enh" ], # 
    'TS_buy_type':'inverse',
    'max_margin': None,
    'verbose': True,
    'trade_amount': 2000,
    'trade_type': 'any'
}
do_sym = "SPX"
if do_sym == "SPX":
    params_bry['exclude_symbols']= ['QQQ']
    params_bry['PT']= 11
    params_bry['TS']= 0
    params_bry['SL']= 60
    params_bry['TS_buy']= 10
elif do_sym == "QQQ":
    params_bry['exclude_symbols']= ['SPX']
    params_bry['PT']= 20
    params_bry['TS']= 0
    params_bry['SL']= 50
    params_bry['TS_buy']= 5

params_enh = {
    'fname_port': cfg['portfolio_names']['tracker_portfolio_name'],
    'dir_quotes': cfg['general']['data_dir'] + '/live_quotes',
    'last_days': None,
    'filt_date_frm': '',
    'filt_date_to': '',
    'stc_date':'stc alert',  # 'eod' or 'stc alert"
    'max_underlying_price': "",
    'min_price': 10,
    'max_dte': 500,
    'min_dte': 0,
    'filt_hour_frm': "",
    'filt_hour_to': "",
    'include_authors': "enh",
    'exclude_traders': ['algo_2', 'cow',  'spy', 'Bryce000', 'algo_1','me_short', 'mage','joker','algo_3','tradewithnando','Father#4214', ], # "enh"
    'exclude_symbols': [],
    'PT': 10,
    'TS': 5,
    'SL': 30,
    'TS_buy': 0,
    'TS_buy_type':'inverse',
    'max_margin': None,
    'verbose': False,
    'trade_amount': None,
    'trade_type': 'any'
}


params_dem = {
    'fname_port': cfg['general']['data_dir'] + "/Demon_port.csv",
    'dir_quotes': cfg['general']['data_dir'] + '/hist_quotes',
    'last_days': None,
    'filt_date_frm': '8/12',
    'filt_date_to': '',
    'stc_date':'eod',  # 'eod' or 'stc alert"
    'max_underlying_price': "",
    'min_price': 10,
    'max_dte': 500,
    'min_dte': 0,
    'filt_hour_frm': "",
    'filt_hour_to': "",
    'include_authors': "demon",
    'exclude_traders': ['algo_2', 'cow',  'spy', 'Bryce000', 'algo_1','me_short', 'mage','joker','algo_3','tradewithnando','Father#4214', ], # "enh"
    'exclude_symbols': [],
    'PT': 50,
    'TS': 0,
    'SL': 100,
    'TS_buy': 0,
    'TS_buy_type':'inverse',
    'max_margin': None,
    'verbose': False,
    'trade_amount': 1000,
    'trade_type': 'any'
}

params = params_dem
port, no_quote, param = calc_returns(**params)


# print(port[['Date','Symbol','Trader', 'PnL', 'PnL-actual', 'strategy-PnL','PnL$', 'PnL$-actual',
#                 'strategy-PnL$','strategy-entry','strategy-exit', 'strategy-close_date']])
print(port[['Date','Symbol','Trader', 'strategy-PnL', 'strategy-PnL$','strategy-entry',
            'strategy-exit', 'strategy-close_date']]) 
sport = port[['Date','Symbol','Trader', 'Price', 'strategy-PnL',
               'strategy-PnL$','strategy-entry','strategy-exit', 'strategy-close_date','reason_skip']] # 

result_td =  generate_report(port, param, no_quote, verbose=True)

if 1:
    import matplotlib.pyplot as plt
    
    stat_type =   'strategy-PnL' # 'PnL-actual'#'PnL' #
    stat_typeu = stat_type.replace("PnL", "PnL$")
    fig, axs = plt.subplots(2, 2, figsize=(10, 10))
    
    nwin = result_td['win']['sum'].iloc[0]
    ntot = result_td['Date']['count'].iloc[0]
    nlost = ntot - nwin
    
    winr = f"{nwin}(w)-{nlost}(l)/{ntot}(t)"
    winp = round((result_td['win']['sum'].iloc[0]/result_td['Date']['count'].iloc[0])*100)
    pnl_emp =  nwin* param['PT'] - nlost*param['SL']
    
    excl = ''
    if param['exclude_symbols']:
        excl = f"(no {param['exclude_symbols']})"
    title = f"{param['include_authors']} {excl} winrate {winp}% {winr}, trade amount {param['trade_amount']}" \
        + f" \nat market: avg PnL%={result_td['strategy-PnL']['mean'].iloc[0]:.2f}, "\
            +f"${result_td['strategy-PnL$']['sum'].iloc[0]:.2f}" \
            + f" \nat set order: avg PnL%={pnl_emp/ntot:.2f}, "\
            +f"${param['trade_amount']*(pnl_emp/100):.0f} \n" \
                +f"TS_buy {param['TS_buy']}, PT {param['PT']}, TS {param['TS']},  SL {param['SL']}"
            

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
    plt.show(block=False)
# best PT 60, SL 45, TS 0, TS_buy 10
# best PT 40, SL 35, TS 25, TS_buy 0

# best PT 100., SL 40,   TS_buy 30.,  pnl -27.5, pnl $ -950,   trade count 32
# res = grid_search(port, PT=np.arange(30,120,10), TS=[0], SL=np.arange(30,100,5), TS_buy=[10,15,20,25,30, 35,40], max_margin=None)
if 0:
    # res = grid_search(params, PT= list(np.arange(0,60, 10)) + list(np.arange(60,150, 10)), SL=np.arange(10,60,10), TS_buy=[0,5,10,20,30], TS= [0, 10,20,50])
    # res = grid_search(params, PT= list(np.arange(0,60, 10)) + list(np.arange(60,150, 10)), SL=np.arange(10,60,10), TS_buy=[0], TS= [0])
    res = grid_search(params, PT= list(np.arange(10,80, 20)), SL=np.arange(10,70,20), TS_buy=[0,5,10,20,30], TS= [0, 10,20,50])
 
    res = np.stack(res)
    sorted_indices = np.argsort(res[:, 5])
    sorted_array = res[sorted_indices].astype(int)
    print(sorted_array[-20:])
    hdr = ['PT', 'SL', 'TS_buy', 'TS', 'pnl', 'pnl$', 'trade count', 'win rate']
    df = pd.DataFrame(sorted_array, columns=hdr)
    # df.to_csv("data/Bryce_QQQ_grid_search_9-14_buyTS.csv", index=False)
    # PT 40,  SL 20,  trailing stop starting at PT: 25,    PNL avg : 5%,  return: $2750,   num trades: 53
    # print(result_td)