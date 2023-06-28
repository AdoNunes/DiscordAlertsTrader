#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  9 09:53:44 2021

@author: adonay
"""
import math
import os.path as op
import pandas as pd
from datetime import datetime, date, timedelta
import numpy as np
from .configurator import cfg
from .alerts_tracker import calc_stc_prices

def short_date(datestr, infrm="%Y-%m-%d %H:%M:%S.%f", outfrm="%m/%d/%Y %H:%M"):
    return datetime.strptime(datestr, infrm).strftime(outfrm)

def formt_num_2str(x, decim=2, str_len=6, remove_zero=True):
    if pd.isnull(x) or x == 'nan':
        return ""
    if remove_zero and x == 0:
        return ""
    x = round(x, decim)
    return f'{x: >{str_len}.{decim}f}'#.replace(".00", "   ")

def max_dig_len(values, decim=2):
    # Gives interger and decimal lengths in an array-like values
    values_s = [str(round(v, decim)) if v % 1 else str(round(v))  for v in values if not math.isnan(v) and not math.isinf(v)]
    tmp_int = [len(v.split('.')[0]) for v in values_s]
    len_int = max(tmp_int) if tmp_int else 1
    tmp_dig = [len(v.split('.')[-1]) if "." in v else 0 for v in values_s]
    len_dig = max(tmp_dig) if tmp_dig else 1
    len_tot = len_int + len_dig + 1 if len_dig else  len_int + len_dig
    return len_tot, len_int, len_dig

def pd_col_str_frmt(pd_Series, max_decim=2, remove_zero=False):
    slen,_, decim = max_dig_len(pd_Series.to_numpy(), max_decim)
    return pd_Series.apply(lambda x: formt_num_2str(x,decim, slen, remove_zero))

def dataframe_num2str(db):
    for col in db:
        if db[col].dtype in [float, int]:
            db[col] = pd_col_str_frmt(db[col])
    return db

def round_int_flt(x, n=1):
    if x%1 == 0:
        return round(x)
    else:
        return round(x, n)

def format_exitplan(plan):

    if plan in ["", "{}"] or plan is None:
        return "None"
    plan = eval(plan)

    PT = [str(v) for v in [plan.get(f"PT{i}") for i in range(1,4)] if v is not None]
    SL = plan.get('SL')

    plan = "PT:" + ",".join(PT) if PT else ""
    sl_str = ", SL:" if plan else "SL:"
    plan = plan + sl_str + str(SL) if SL else plan

    return plan


def calculate_weighted_mean(row, sufix="Price"):
    prices = row[[f'STC1-{sufix}', f'STC2-{sufix}', f'STC3-{sufix}',]].values
    uqtys = row[['STC1-uQty', 'STC2-uQty', 'STC3-uQty']].values
    valid_indices = ~pd.isna(prices) & ~pd.isna(uqtys)
    if np.any(valid_indices):
        try:
            return np.average(prices[valid_indices], weights=uqtys[valid_indices])
        except:
            return np.average(prices[valid_indices])
    else:
        return np.nan
    
def get_portf_data(exclude={}, port_filt_author='', port_filt_date_frm='',
                     port_filt_date_to='', port_filt_chn='', **kwargs ):
    fname_port = cfg['portfolio_names']['portfolio_fname']
    if not op.exists(fname_port):
        return [],[]
    try:
        data = pd.read_csv(fname_port,sep=",")
    except:
        data = pd.read_csv(fname_port,sep=",")

    try:
        data = filter_data(data,exclude, port_filt_author, port_filt_date_frm,
                        port_filt_date_to, port_filt_chn)
    except Exception as e:
        print("error during portfolio filter data", e)
        pass
    
    data['Amount'] = data['uQty']
    data['STC-Amount'] = data[['STC1-uQty', 'STC2-uQty', 'STC3-uQty']].sum(axis=1)
    data['Price-current'] = data['Price-Current']
    
    for price in ['Price', 'Price-Alerted', 'Price-Current']:
        data[f'STC-{price.replace("Current", "current")}'] = data.apply(calculate_weighted_mean, args=(price,), axis=1)
    
    data["STC-Price"] = data.apply(calculate_weighted_mean, args=('Price',), axis=1)
    data["STC-Price-current"] = data.apply(calculate_weighted_mean, args=('Price-Current',), axis=1)
    data["STC-Price-Alerted"] = data.apply(calculate_weighted_mean, args=('Price-Alerted',), axis=1)
        
    data["STC-Prices"] = data[['STC1-Price', 'STC2-Price', 'STC3-Price']].apply(
        lambda x: "/".join(x.astype(str)).replace("/nan", ""), axis=1)
    data["STC-Prices-current"] = data[['STC1-Price-Current', 'STC2-Price-Current', 'STC3-Price-Current']].apply(
        lambda x: "/".join(x.astype(str)).replace("/nan", ""), axis=1)
    data["STC-Prices-Alerted"] = data[['STC1-Price-Alerted', 'STC2-Price-Alerted', 'STC3-Price-Alerted']].apply(
        lambda x: "/".join(x.astype(str)).replace("/nan", ""), axis=1)
    
    if exclude.get("live PnL", False):
        # alerted not calculated, so tmp chage name to price
        data =  get_live_quotes(data)
        data["STC-Price_o"] = data["STC-Price"]
        data["STC-Prices_o"] = data["STC-Prices"]
        data["STC-Price"] = data["STC-Price-Alerted"]
        data["STC-Prices"] = data["STC-Prices-Alerted"]
        
        data =  get_live_quotes(data)
        data["STC-Price-Alerted"] = data["STC-Price"]
        data["STC-Prices-Alerted"] = data["STC-Prices"]
        data["STC-Price"] = data["STC-Price_o"]
        data["STC-Prices"] = data["STC-Prices_o"]
        
    data['Date'] = data['Date'].apply(lambda x: short_date(x))
    data['exit_plan']= data['exit_plan'].apply(lambda x: format_exitplan(x))
    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    alerts = data[['STC1-Alerted', 'STC2-Alerted', 'STC3-Alerted']].sum(1)
    data["N Alerts"]= alerts.astype(int)
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])

    for i in range(1,4):
        data[f'STC{i}-PnL'] = pd_col_str_frmt(data[f'STC{i}-PnL'])
        data[f'STC{i}-uQty'] = pd_col_str_frmt(data[f'STC{i}-uQty'])

    frm_cols = ['Price', 'Price-Alert', "Price-Current", 'uQty', 'filledQty', 'N Alerts', 
                "PnL", "$PnL","PnL-Alert", "$PnL-Alert","PnL-Current","$PnL-Current", 
                "STC-Price", "STC-Price-current", "STC-Price-Alerted", 
                ]
    
    for cfrm in frm_cols:
        data[cfrm] = pd_col_str_frmt(data[cfrm])
    

    cols = ['isOpen', "PnL", "$PnL", 'Date', 'Symbol', 'Trader', 'BTO-Status', 'Price',
            'Price-Alert', "Price-Current", 'uQty', 'filledQty', 'N Alerts',"PnL-Alert",
            "$PnL-Alert","PnL-Current","$PnL-Current", 
            "STC-Price", "STC-Price-current", "STC-Price-Alerted",
            "STC-Prices","STC-Prices-current", "STC-Prices-Alerted",
            'STC1-Status','STC1-uQty', 'STC2-Status', 'STC2-uQty', 'STC3-Status',  'STC3-uQty',                      
            ]

    data = data[cols]
    data.fillna("", inplace=True)
    header_list = data.columns.tolist()
    header_list = [d.replace('STC', 'S') for d in header_list]
    data = data.astype(str)
    if len(data):
        sumtotal = {c:"" for c in data.columns}
        for sumcol in ["PnL","PnL-Alert","PnL-Current"]:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).mean():.2f}'
        for sumcol in [ "$PnL","$PnL-Alert","$PnL-Current"]:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).sum():.2f}'
        sumtotal['Date'] = data.iloc[len(data)-1]['Date']
        sumtotal['Symbol'] = "Total Average"
        sumtotal['Trader'] = "Average"
        data = pd.concat([data, pd.DataFrame.from_records(sumtotal, index=[0])], ignore_index=True)
    
    data = data.values.tolist()
    return data, header_list

def get_tracker_data(exclude={}, track_filt_author='', track_filt_date_frm='',
                     track_filt_date_to='', track_filt_sym='', track_exc_author='',
                     track_exc_chn='',**kwargs ):
    fname_port = cfg['portfolio_names']['tracker_portfolio_name']
    if not op.exists(fname_port):
        return [],[]
    
    try:
        data = pd.read_csv(fname_port, sep=",")
    except:
        return [[]],[]

    data['Date'] = data['Date'].apply(lambda x: short_date(x))
    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    data["N Alerts"]= data['Avged']
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])
    
    if not exclude.get("live PnL", False):
        data =  get_live_quotes(data)
    
    frm_cols = ['Amount', 'N Alerts', 'STC-Amount','STC-Price','STC-Price-current','STC-PnL','STC-PnL-current',
                'STC-PnL$','STC-PnL$-current', 'Price', 'Price-current']
    for cfrm in frm_cols:
        data[cfrm] = pd_col_str_frmt(data[cfrm])
    
    try:
        data = filter_data(data,exclude, track_filt_author, track_filt_date_frm,
                        track_filt_date_to, track_filt_sym, track_exc_author, track_exc_chn)
    except Exception as e:
        print("error during tracker filter data", e)
        pass
    cols = ['isOpen','STC-PnL','STC-PnL-current', 'STC-PnL$','STC-PnL$-current', 'Date', 'Symbol', 'Trader', 'Price',
            "Price-current", 'Amount', 'N Alerts','STC-Amount','STC-Price','STC-Price-current','STC-Date','Channel'
            ]
    # data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])
    data = data[cols]
    data.fillna("", inplace=True)
    header_list = data.columns.tolist()
    header_list = [d.replace('STC', 'S') for d in header_list]
    if len(data):
        sumtotal = {c:None for c in data.columns}
        for sumcol in ['STC-PnL','STC-PnL-current']:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).mean():.2f}'
        for sumcol in ['STC-PnL$','STC-PnL$-current']:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).sum():.2f}'
        sumtotal['Date'] = data.iloc[len(data)-1]['Date']
        sumtotal['Symbol'] = "Total Average"
        sumtotal['Trader'] = track_filt_author if len(track_filt_author) else "Average"
        data = pd.concat([data, pd.DataFrame.from_records(sumtotal, index=[0])], ignore_index=True)
        data.fillna("", inplace=True)
    data = data.values.tolist()
    return data, header_list


def get_stats_data(exclude={}, stat_filt_author='', stat_filt_date_frm='',
                     stat_filt_date_to='', stat_filt_sym='', 
                     stat_max_trade_cap='', stat_max_qty='', trail_stop_perc='',
                     stat_exc_author='', stat_exc_chn='', stat_exc_sym='',
                     fname_port=None,
                     **kwargs ):
    if fname_port is None:
        fname_port = cfg['portfolio_names']['tracker_portfolio_name']
    if not op.exists(fname_port):
        return [],[]
    
    data = pd.read_csv(fname_port, sep=",")

    data['Date'] = data['Date'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f").strftime("%m/%d/%Y"))
    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    data["N Alerts"]= data['Avged']
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])
    try:
        data = filter_data(data,exclude, stat_filt_author, stat_filt_date_frm,
                        stat_filt_date_to, stat_filt_sym, stat_exc_author, stat_exc_chn, stat_exc_sym)
    except Exception as e:
        print("error during stats filter data", e)
        pass
    if stat_max_qty != "" or stat_max_trade_cap != "":
        if stat_max_qty != "" and stat_max_qty.isnumeric():
            stat_max_qty = int(stat_max_qty)
            print("stat_max_qty:", stat_max_qty)
            option_mult = (data['Asset'] == 'option').astype(int)
            option_mult[option_mult==1] = 100
            exceeds_cap = data['Amount'] > stat_max_qty
            data.loc[exceeds_cap, 'Amount'] = stat_max_qty

        if stat_max_trade_cap != "" and stat_max_trade_cap.isnumeric():
            stat_max_trade_cap = int(stat_max_trade_cap)
            print("stat_max_trade_cap:", stat_max_trade_cap)
            option_mult = (data['Asset'] == 'option').astype(int)
            option_mult[option_mult==1] = 100
            trade_value = data['Amount'] * data['Price'] * option_mult
            exceeds_cap = trade_value > stat_max_trade_cap
            data.loc[exceeds_cap, 'Amount'] = np.floor(stat_max_trade_cap / (data['Price'] * option_mult))
            data = data[data['Amount'] * data['Price'] * option_mult <= stat_max_trade_cap]
        mult =(data['Asset'] == 'option').astype(int) 
        mult[mult==0] = .01  # pnl already in %
        data['STC-PnL$'] = data['Amount'] * data['STC-PnL'] * data['Price'] * mult
        data['STC-PnL$-current'] = data['Amount'] * data['STC-PnL-current'] * data['Price-current'] * mult
        data['STC-PnL$'] = data['STC-PnL$'].round()
        data['STC-PnL$-current'] = data['STC-PnL$-current'].round()

    data['PnL diff'] = data['STC-PnL-current'] - data['STC-PnL']
    data['BTO diff'] = 100*(data['Price-current'] - data['Price'])/ data['Price']
    data['STC diff'] = 100*(data['STC-Price-current'] - data['STC-Price'])/ data['STC-Price']
    data = data.rename({'STC-PnL-current': 'STC-PnL-Actual', 
                        'STC-PnL$-current': 'STC-PnL$-Actual', 
                        }, axis=1)
    # Define the aggregation functions for each column
    agg_funcs = {'STC-PnL$': 'sum',
                 'STC-PnL$-Actual': 'sum',
                 'STC-PnL': 'mean',
                 'STC-PnL-Actual': 'mean',
                 'PnL diff' : "mean",
                 'BTO diff' : "mean",
                 'STC diff' : "mean",
                 'Date': ['count', 'min', 'max']
                 }
    # Perform the groupby operation and apply the aggregation functions
    result_td = data.groupby('Trader').agg(agg_funcs)
    result_td = result_td.reset_index()
    
    result_ch = data.groupby('Channel').agg(agg_funcs)
    result_ch = result_ch.reset_index()
    result_ch = result_ch.rename({'Channel': 'Trader'}, axis=1)

    # make grand avg
    data["all"] = 1
    agg_values_all = data.groupby('all').agg(agg_funcs)    
    agg_values_all["Trader"] = "Total average"
    agg_values_all.loc[0, 'Trader'] = "Channels:"
    agg_values_all = agg_values_all.reset_index()

    result_td = pd.concat([result_td, agg_values_all, result_ch],axis=0, ignore_index=True)
    result_td.drop('all', axis=1, level=0, inplace=True)
    new_cols =[k for k in result_td.columns.get_level_values(0)]
    new_cols[-3] = "N Trades"
    new_cols[-2] = "Since"
    new_cols[-1] = "Last"
    result_td.columns = new_cols
    result_td = result_td.round(1)

    for cfrm in result_td.columns[1:-2]:
        result_td[cfrm] = pd_col_str_frmt(result_td[cfrm])
    result_td = result_td.fillna("")
    header_list = result_td.columns.tolist()
    header_list = [d.replace('STC-', '') for d in header_list]
    data = result_td.values.tolist()
    return data, header_list

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


def filter_data(data,exclude={}, track_filt_author='', track_filt_date_frm='', track_filt_date_to='',
                track_filt_sym='', track_exc_author='', track_exc_chn='', stat_exc_sym='', msg_cont=''):
    if len(exclude):
        for k, v in exclude.items():
            if k == "Cancelled" and v and k in data.columns:
                data = data[data["BTO-Status"] !="CANCELED"]
            elif k == "Closed" and v:
                data = data[data["isOpen"] !="No"]
            elif k == "Open" and v:
                data = data[data["isOpen"] !="Yes"]
            elif k == "NegPnL" and v:
                col = "PnL" if "PnL" in data else 'STC-PnL'                
                pnl = data[col].apply(lambda x: np.nan if x =="" else eval(x) if isinstance(x, str) else x)     
                data = data[pnl > 0 ]
            elif k == "PosPnL" and v:
                col = "PnL" if "PnL" in data else 'STC-PnL' 
                pnl = data[col].apply(lambda x: np.nan if x =="" else eval(x) if isinstance(x, str) else x)
                data = data[pnl < 0 ]
            elif k == "stocks" and v:
                data = data[data["Asset"] !="stock"]
            elif k == "options" and v:
                data = data[data["Asset"] !="option"]

    if track_filt_author:
        msk = [x.strip() for x in track_filt_author.split(",")]
        data = data[data['Trader'].str.contains('|'.join(msk), case=False)]
    if track_filt_date_frm:
        track_filt_date_frm = period_to_date(track_filt_date_frm)
        msk = pd.to_datetime(data['Date']).dt.date >= pd.to_datetime(track_filt_date_frm).date()
        data = data[msk]
    if track_filt_date_to:
        track_filt_date_to =  period_to_date(track_filt_date_to)
        msk = pd.to_datetime(data['Date']).dt.date <= pd.to_datetime(track_filt_date_to).date()
        data = data[msk]
    if track_filt_sym:
        msk = [x.strip() for x in track_filt_sym.split(",")]
        data = data[data['Symbol'].str.contains('|'.join(msk), case=False)]
    if track_exc_author:
        msk = [x.strip() for x in track_exc_author.split(",")]
        data = data[~data['Trader'].str.contains('|'.join(msk), case=False)]
    if track_exc_chn:
        msk = [x.strip() for x in track_exc_chn.split(",")]
        data = data[~data['Channel'].str.contains('|'.join(msk), case=False)]
    if stat_exc_sym:
        msk = [x.strip() for x in stat_exc_sym.split(",")]
        data = data[~data['Symbol'].str.contains('|'.join(msk), case=False)]
    if msg_cont:
        data = data[data['Content'].str.contains(msg_cont, case=False)]

    return data

def get_live_quotes(portfolio):
    dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
    track_symb = portfolio.loc[portfolio['isOpen']=='Yes', 'Symbol'].to_list()
    
    quotes_sym = {}
    for sym in track_symb: 
        fquote = f"{dir_quotes}/{sym}.csv"
        if not op.exists(fquote):
            continue
        
        with open(fquote, "r") as f:
            quotes = f.readlines()
        
        timestamp, quote = quotes[-1].split(',')  # in ms
        # quote_date = datetime.fromtimestamp(int(timestamp))
        # if (datetime.now() - quote_date).total_seconds() > 20:
        #     continue
        quotes_sym[sym] = float(quote.replace('\n', '').replace(' ', ''))
    
    for sym in quotes_sym:
        live_price = quotes_sym[sym]
        msk = (portfolio['Symbol']==sym) & (portfolio['isOpen']=='Yes')
        trades = portfolio.loc[msk]
        
        for _, trade in trades.iterrows():
            order= {
                "uQty": trade['Amount'] if pd.isnull(trade.get("STC-Amount")) else trade['Amount']- trade["STC-Amount"],
                "price": live_price,
                "Actual Cost": live_price,
                }                 
            stc_info = calc_stc_prices(trade, order)
            for k, v in stc_info.items():
                if k == "STC-Amount":
                    continue
                portfolio.loc[msk,k] = v
    return portfolio

def get_hist_msgs(filt_author='', filt_date_frm='', filt_date_to='',
                  filt_cont='', chan_name="option_alerts", **kwargs):
    # Provide arguments to filter
    data = pd.read_csv(op.join(cfg['general']['data_dir'] , f"{chan_name}_message_history.csv"),
                       usecols=['Author', 'Date', 'Content', 'Parsed'])
    data = data.rename({"Author": "Trader"}, axis=1)

    data = filter_data(data,{}, filt_author, filt_date_frm, filt_date_to, msg_cont=filt_cont)
    data['Trader'] = data['Trader'].apply(lambda x: x.split('#')[0])
    data['Date'] = data['Date'].apply(lambda x: short_date(x))

    data = data.fillna("")
    header_list = data.columns.tolist()
    return data.values.tolist(), header_list

def get_acc_bals(bksession):
    acc_inf = bksession.get_account_info()
    # if grabing new access token return None, try again
    if acc_inf is None:  
        acc_inf = bksession.get_account_info()
        if acc_inf is None:
            return {"id": 0, "balance":0, "cash":0, "funds":0},  {"id": "00", "balance":0, "cash":0, "funds":0}
    accnt= {"id" : acc_inf['securitiesAccount']['accountId'],
        "balance": acc_inf['securitiesAccount']['currentBalances'].get('liquidationValue', 0),
        "cash": acc_inf['securitiesAccount']['currentBalances'].get('cashBalance',0),
        "funds": acc_inf['securitiesAccount']['currentBalances'].get('availableFunds', 0),
        }
    return acc_inf, accnt

def get_pos(acc_inf):
    if acc_inf.get('securitiesAccount') is None:
        return ["NoAccount"], ["Sym", "Last", "price", "PnL_%", "PnL","Qty", "Val", "Cost"]
    positions = acc_inf['securitiesAccount'].get('positions', [])
    pos_tab = []
    pos_headings = ["Sym", "Last", "price", "PnL_%", "PnL","Qty", "Val", "Cost"]
    for pos in positions:
        price= round(pos['averagePrice'], 2)
        # pnl = pos['currentDayProfitLoss']
        pnl_p = pos['currentDayProfitLossPercentage'] * 100
        uQty = pos['longQuantity']
        if uQty == 0:
            uQty = pos['shortQuantity']
        cost = round(price * uQty, 2)
        last = round(pos["marketValue"] / uQty, 2)
        sym = pos['instrument']['symbol']
        asset = pos['instrument']['assetType']
        val = pos["marketValue"]
        if pos['instrument']['assetType'] == "OPTION":
            cost = round(price * uQty * 100, 2)
            last = round(pos["marketValue"] / uQty, 2)/100

        pnl_t = round(val - cost, 2)
        if  cost == 0:
            pnl_p_t = 0
        else:
            pnl_p_t = round((val -cost)*100 / cost, 2)

        pos_vals = [sym, last, price, pnl_p_t ,pnl_t, uQty, val , cost]
        pos_tab.append(pos_vals)

    db = pd.DataFrame(data=pos_tab, columns=pos_headings)
    db = dataframe_num2str(db)
    return db.values.tolist(), pos_headings

def order_info_pars(ord_dic, ord_list):
    """ get info from order request
    :param ord_dic: dict with order info, from 'orderStrategies' or
    'childOrderStrategies'
    """
    ord_headings = ["Sym", "Act", "Strat", "Price/stp","Date", "Qty/fill", "Status", "ordId"]
    sing_ord = []

    price = ord_dic.get("price")
    stprice = ord_dic.get("stopPrice")
    # If SL order with no stopPrice
    if price is None:
        price = ord_dic.get("stopPrice")
        stprice = None
    price = f"{price}" if stprice == None else f"{price}/{stprice}"

    sing_ord.append(ord_dic['orderType'])
    sing_ord.append(price)
    # sing_ord.append(stprice)

    date = ord_dic['enteredTime'].split("+")[0]
    date = short_date(date, "%Y-%m-%dT%H:%M:%S")
    sing_ord.append(date)

    qty = round_int_flt(ord_dic['quantity'])
    fill = round_int_flt(ord_dic['filledQuantity'])
    qty_fll = f"{qty}/{fill}" if fill else f"{qty}"
    sing_ord.append(qty_fll)
    sing_ord.append(ord_dic['status'])
    sing_ord.append(str(ord_dic['orderId']))

    for leg in ord_dic['orderLegCollection']:
        sing_ord_c = sing_ord.copy()
        sing_ord_c.insert(0, leg['instrument']['symbol'])
        sing_ord_c.insert(1, leg["instruction"].replace('BUY_TO_OPEN', "BUY").replace('SELL_TO_CLOSE', "SELL"))
        ord_list.append(sing_ord_c)

    return ord_list, ord_headings

def get_orders(acc_inf):
    if acc_inf.get('securitiesAccount') is None:
        return ["NoAccount"],  ["Sym", "Act", "Strat", "Price/stp","Date", "Qty/fill", "Status", "ordId"], []
    orders =acc_inf['securitiesAccount'].get('orderStrategies', [])
    if len(orders) == 0:
        return ["NoOrders"],  ["Sym", "Act", "Strat", "Price/stp","Date", "Qty/fill", "Status", "ordId"], []
    ord_tab, cols = [], []
    col = 0
    for ordr in orders:
        col = not col
        ord_type = ordr['orderStrategyType']
        if ord_type == "OCO":
            for chl in ordr['childOrderStrategies']:
                nlen = len(ord_tab)
                ord_tab, heads = order_info_pars(chl, ord_tab)
                nnlen = len(ord_tab) - nlen
                cols = cols + [col]*nnlen
        else:
            nlen = len(ord_tab)
            ord_tab, heads = order_info_pars(ordr, ord_tab)
            nnlen = len(ord_tab) - nlen
            cols = cols + [col]*nnlen

    db = pd.DataFrame(data=ord_tab, columns=heads)
    db = dataframe_num2str(db)
    return db.values.tolist(),heads, cols








