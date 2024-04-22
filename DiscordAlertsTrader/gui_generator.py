#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  9 09:53:44 2021

@author: adonay
"""
import math
import os.path as op
import pandas as pd
from datetime import datetime, date
import numpy as np
from .configurator import cfg
from .alerts_tracker import calc_stc_prices
from .port_sim import filter_data

def short_date(datestr, infrm="%Y-%m-%d %H:%M:%S.%f", outfrm="%Y/%m/%d %H:%M"):
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
    uqtys = row[['STC1-Qty', 'STC2-Qty', 'STC3-Qty']].values
    valid_indices = ~pd.isna(prices) & ~pd.isna(uqtys)
    if np.any(valid_indices):
        try:
            return np.average(prices[valid_indices], weights=uqtys[valid_indices])
        except:
            return np.average(prices[valid_indices])
    else:
        return np.nan
    
def get_portf_data(exclude={}, port_filt_author='', port_filt_date_frm='',
                     port_filt_date_to='', port_filt_chn='', port_filt_sym='',
                     port_exc_author="", port_exc_chn="",
                     **kwargs ):
    fname_port = cfg['portfolio_names']['portfolio_fname']
    if not op.exists(fname_port):
        return [],[]
    try:
        data = pd.read_csv(fname_port,sep=",")
    except:
        try:
            data = pd.read_csv(fname_port,sep=",")
        except:
            return [],[] 
    try:
        data = filter_data(data, exclude, 
                            filt_author=port_filt_author,
                            filt_date_frm=port_filt_date_frm,
                            filt_date_to=port_filt_date_to,
                            filt_sym=port_filt_sym,
                            filt_chn=port_filt_chn,
                            exc_author=port_exc_author,
                            exc_chn=port_exc_chn
                            )
    except Exception as e:
        print("error during portfolio filter data", e)
        pass
    
    live_col = False
    data['Live'] = np.nan
    if not exclude.get("live PnL", False):
        data =  get_live_quotes(data, trader_port=True)
        if 'Live' in data.columns:
            live_col = True

    data['STC-Qty'] = data[['STC1-Qty', 'STC2-Qty', 'STC3-Qty']].sum(axis=1)
    data['Price-actual'] = data['Price-actual']
    
    for price in ['Price', 'Price-alert', 'Price-actual']:
        data[f'STC-{price.replace("Current", "actual")}'] = data.apply(calculate_weighted_mean, args=(price,), axis=1)
    
    data["STC-Price"] = data.apply(calculate_weighted_mean, args=('Price',), axis=1)
    data["STC-Price-actual"] = data.apply(calculate_weighted_mean, args=('Price-actual',), axis=1)
    data["STC-Price-alert"] = data.apply(calculate_weighted_mean, args=('Price-alert',), axis=1)
        
    data["STC-Prices"] = data[['STC1-Price', 'STC2-Price', 'STC3-Price']].apply(
        lambda x: "/".join(x.astype(str)).replace("/nan", ""), axis=1)
    data["STC-Prices-actual"] = data[['STC1-Price-actual', 'STC2-Price-actual', 'STC3-Price-actual']].apply(
        lambda x: "/".join(x.astype(str)).replace("/nan", ""), axis=1)
    data["STC-Prices-alert"] = data[['STC1-Price-alert', 'STC2-Price-alert', 'STC3-Price-alert']].apply(
        lambda x: "/".join(x.astype(str)).replace("/nan", ""), axis=1)
    
    data['Date'] = data['Date'].apply(lambda x: short_date(x))
    data['exit_plan']= data['exit_plan'].apply(lambda x: format_exitplan(x))
    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    alerts = data[['STC1-alerted', 'STC2-alerted', 'STC3-alerted']].sum(1)
    data["N Alerts"]= alerts.astype(int)
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])

    for i in range(1,4):
        data[f'STC{i}-PnL'] = pd_col_str_frmt(data[f'STC{i}-PnL'])
        data[f'STC{i}-Qty'] = pd_col_str_frmt(data[f'STC{i}-Qty'])

    if live_col:
        data['Live'] = pd_col_str_frmt(data['Live'])

    frm_cols = ['Price', 'Price-alert', "Price-actual", 'Qty', 'filledQty', 'N Alerts', 
                "PnL", "PnL$","PnL-alert", "PnL$-alert","PnL-actual","PnL$-actual", 
                "STC-Price", "STC-Price-actual", "STC-Price-alert", 
                ]
    
    for cfrm in frm_cols:
        data[cfrm] = pd_col_str_frmt(data[cfrm])

    cols = ['isOpen', "PnL", "PnL$", 'Date', 'Symbol', 'Trader', 'BTO-Status', 'Type','Price',
            'Price-alert', "Price-actual", 'Qty', 'filledQty', 'N Alerts',"PnL-alert",
            "PnL$-alert","PnL-actual","PnL$-actual", 
            "STC-Price", "STC-Price-actual", "STC-Price-alert",
            "STC-Prices","STC-Prices-actual", "STC-Prices-alert",
            'STC1-Status','STC1-Qty', 'STC2-Status', 'STC2-Qty', 'STC3-Status',  'STC3-Qty',       
            'exit_plan', 'BTO-avg-Status', 'STC1-ordID', 'STC2-ordID', 'STC3-ordID',          
            ]
    cols = ['Live'] + cols
        
    data = data[cols]
    data  = data.fillna("")
    header_list = data.columns.tolist()
    header_list = [d.replace('STC', 'S') for d in header_list]
    data = data.astype(str)
    if len(data):
        sumtotal = {c:"" for c in data.columns}
        for sumcol in ["PnL","PnL-alert","PnL-actual"]:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).mean():.2f}'
        for sumcol in [ "PnL$","PnL$-alert","PnL$-actual", 'Qty', 'filledQty']:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).sum():.2f}'
        sumtotal['Date'] = data.iloc[len(data)-1]['Date']
        sumtotal['Symbol'] = "Total Average"
        sumtotal['Trader'] = "Average"
        data = pd.concat([data, pd.DataFrame.from_records(sumtotal, index=[0])], ignore_index=True)
    
    data = data.values.tolist()
    return data, header_list

def get_tracker_data(exclude={}, track_filt_author='', track_filt_date_frm='',                  
                     track_filt_date_to='', track_filt_sym='', track_filt_chn='',
                     track_exc_author='', track_exc_sym='', track_exc_chn='',
                     track_dte_max='',
                     track_dte_min='', **kwargs ):
    fname_port = cfg['portfolio_names']['tracker_portfolio_name']
    if not op.exists(fname_port):
        return [],[]
        
    try:
        data = pd.read_csv(fname_port, sep=",")
    except:
        return [[]],[] 

    try:
        data = filter_data(data,exclude, 
                            filt_author=track_filt_author,
                            filt_date_frm=track_filt_date_frm,
                            filt_date_to=track_filt_date_to,
                            filt_chn=track_filt_chn,
                            filt_sym=track_filt_sym,
                            exc_author=track_exc_author,
                            exc_chn=track_exc_chn,
                            exc_sym=track_exc_sym,
                            max_dte=track_dte_max,
                            min_dte= track_dte_min,
                        )
    except Exception as e:
        print("error during tracker filter data", e)
        pass
    
    live_col = False
    data['Live'] = np.nan
    if not exclude.get("live PnL", False):
        data =  get_live_quotes(data)
        if 'Live' in data.columns:
            live_col = True
    
    data['Date'] = data['Date'].apply(lambda x: short_date(x))
    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    data["N Alerts"]= data['Avged']
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])
    
    if 'underlying' in data.columns:
        max_margin = eval(cfg['shorting']['margin_capital'])
        try:
            data['Margin'] = data.apply(lambda x: 100*x['Price-actual'] *(max_margin/(20*x['underlying'])),axis=1)
        except:
            data['Margin'] = 0
    else:
        data['Margin'] = 0
        
    frm_cols = ['Qty', 'N Alerts', 'STC-Qty','STC-Price','STC-Price-actual','PnL','PnL-actual',
                'PnL$','PnL$-actual', 'Price', 'Price-actual', 'Margin']
    for cfrm in frm_cols:
        data[cfrm] = pd_col_str_frmt(data[cfrm])
    
    if live_col:
        data['Live'] = pd_col_str_frmt(data['Live'])
    
    cols = ['isOpen','PnL','PnL-actual', 'PnL$','PnL$-actual', 'Date', 'Symbol', 'Trader', 'Price',
            "Price-actual", 'Qty', 'N Alerts','STC-Qty','STC-Price','STC-Price-actual','STC-Date','Channel',
            'Margin'
            ]
    cols = ['Live'] + cols

    data = data[cols]
    data = data.astype(object)
    data.fillna("", inplace=True)
    header_list = data.columns.tolist()
    header_list = [d.replace('STC', 'S') for d in header_list]
    if len(data):
        sumtotal = {c:None for c in data.columns}
        for sumcol in ['PnL','PnL-actual']:
            sumtotal[sumcol]= f'{data[sumcol].apply(lambda x: np.nan if x =="" else eval(x)).mean():.2f}'
        for sumcol in ['PnL$','PnL$-actual']:
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
                     stat_max_trade_val='', stat_max_qty='', 
                     stat_exc_author='', stat_exc_chn='', stat_exc_sym='', 
                     stat_dte_min='', stat_dte_max='',
                     fname_port=None,
                     **kwargs ):
    if fname_port is None:
        fname_port = cfg['portfolio_names']['tracker_portfolio_name']
    if not op.exists(fname_port):
        return [],[]
    
    data = pd.read_csv(fname_port, sep=",")
    data['Date'] = data['Date'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y/%m/%d"))
    exclude['Open'] = True
    try:
        data = filter_data(data,exclude, stat_filt_author, stat_filt_date_frm,
                        stat_filt_date_to, stat_filt_sym, stat_exc_author, stat_exc_chn, stat_exc_sym,
                        max_trade_val=stat_max_trade_val, max_u_qty=stat_max_qty, 
                        max_dte=stat_dte_max, min_dte=stat_dte_min)
    except Exception as e:
        print("error during stats filter data", e)
        pass

    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    data["N Alerts"]= data['Avged']
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])
    data['PnL diff'] = data['PnL-actual'] - data['PnL']
    data['BTO diff'] = 100*(data['Price-actual'] - data['Price'])/ data['Price']
    data['STC diff'] = 100*(data['STC-Price-actual'] - data['STC-Price'])/ data['STC-Price']
    data['Win'] = (data['PnL'] > 0).astype(int)
    data['Win act'] = (data['PnL-actual'] > 0).astype(int)
    data = data.rename({'PnL-actual': 'PnL-Actual', 
                        'PnL$-actual': 'PnL$-Actual', 
                        }, axis=1)
    # Define the aggregation functions for each column
    agg_funcs = {'PnL$': 'sum',
                 'PnL$-Actual': 'sum',
                 'PnL': 'mean',
                 'PnL-Actual': 'mean',
                 "Win": 'mean',
                 "Win act": 'mean',
                 'PnL diff' : "mean",
                 'BTO diff' : "mean",
                 'STC diff' : "mean",
                 'Date': ['count', 'min', 'max']
                 }
    # Perform the groupby operation and apply the aggregation functions
    result_td = data.groupby('Trader').agg(agg_funcs)
    result_td = result_td.reset_index()
    result_td['Win'] = (result_td['Win'] * 100).round(1)
    result_td['Win act'] = (result_td['Win act'] * 100).round(1)

    result_ch = data.groupby('Channel').agg(agg_funcs)
    result_ch = result_ch.reset_index()
    result_ch = result_ch.rename({'Channel': 'Trader'}, axis=1)
    result_ch['Win'] = (result_ch['Win'] * 100).round(1)
    result_ch['Win act'] = (result_ch['Win act'] * 100).round(1)

    # make grand avg
    data["all"] = 1
    agg_values_all = data.groupby('all').agg(agg_funcs)    
    agg_values_all["Trader"] = "Total average"
    agg_values_all['Win'] = (agg_values_all['Win'] * 100).round(1)
    agg_values_all['Win act'] = (agg_values_all['Win act'] * 100).round(1)
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


def get_live_quotes(portfolio, trader_port=False):
    dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
    
    msk = (pd.to_datetime(portfolio['Date']).dt.date == date.today()) | (portfolio['isOpen']==1)
    
    track_symb = portfolio.loc[msk, 'Symbol'].to_list()
    
    quotes_sym = {}
    for sym in track_symb: 
        fquote = f"{dir_quotes}/{sym}.csv"
        if not op.exists(fquote):
            continue
        
        with open(fquote, "r") as f:
            quotes = f.readlines()
        
        quote_lst = quotes[-1].split(',')  # in ms
        try:
            quotes_sym[sym] = {"ask": float(quote_lst[2].replace('\n', '').replace(' ', '')),
                               "bid":float(quote_lst[1].replace('\n', '').replace(' ', ''))
                               }
        except:
            continue
            
    for sym in quotes_sym:
        msk = portfolio['Symbol']==sym
        trades = portfolio.loc[msk]
        
        for ix, trade in trades.iterrows():
            if "Type" in portfolio.columns:
                if trade['Type'] == "BTO":
                    live_price = quotes_sym[sym]['bid']
                elif trade['Type'] == "STO":
                    live_price = quotes_sym[sym]['ask']            
            portfolio.loc[ix, 'Live'] = live_price
            
            if trade['isOpen'] == 0:
                continue
            order= {
                "Qty": trade['Qty'] if pd.isnull(trade.get("STC-Qty")) else trade['Qty']- trade["STC-Qty"],
                "price": live_price,
                "Actual Cost": live_price,
                } 

            if trader_port:
                trade = compute_live_trader_port(trade, order)
                portfolio.loc[ix] = trade
            else:                 
                stc_info = calc_stc_prices(trade, order)
                for k, v in stc_info.items():
                    if k == "STC-Qty":
                        continue
                    portfolio.loc[ix,k] = v
            portfolio.loc[ix, 'Live'] = live_price
    return portfolio


def compute_live_trader_port(trade, order):
    "Workaround to get live trade Pnl for trader portfolio"
    stc_price = order['price']

    bto_price = trade["Price"]
    if pd.isnull(bto_price) or trade["BTO-Status"] == "WORKING":
        return trade 
    bto_price_alert = trade["Price-alert"]
    bto_price_actual = trade["Price-actual"]

    if trade["Type"] == "BTO":
        stc_PnL = float((stc_price - bto_price)/bto_price) *100
    elif trade["Type"] == "STO":
        stc_PnL = float((bto_price - stc_price)/bto_price) *100

    # get STC number not yet filled
    for i in range(1,4):
        STC = f"STC{i}"
        if pd.isnull(trade[f"STC{i}-Qty"]):
            break

    sold_tot = np.nansum([trade[f"STC{i}-Qty"] for i in range(1,4)])
    #Log portfolio
    trade[ STC + "-Price"] = stc_price
    trade[ STC + "-Price-alert"] = stc_price
    trade[ STC + "-Price-actual"] = stc_price
    trade[ STC + "-PnL"] = stc_PnL
    trade[ STC + "-Qty"] = trade['filledQty'] - sold_tot
    
    
    sold_tot = np.nansum([trade[f"STC{i}-Qty"] for i in range(1,4)])
    if sold_tot == 0:
        return trade
    stc_PnL_all = np.nansum([trade[f"STC{i}-PnL"]*trade[f"STC{i}-Qty"] for i in range(1,4)])/sold_tot
    trade[ "PnL"] = stc_PnL_all

    if trade[ "Type"] == "BTO":
        stc_PnL_all_alert =  np.nansum([(float((trade[f"STC{i}-Price-alert"] - bto_price_alert)/bto_price_alert) *100) * trade[f"STC{i}-Qty"] for i in range(1,4)])/sold_tot
        stc_PnL_all_curr = np.nansum([(float((trade[f"STC{i}-Price-actual"] - bto_price_actual)/bto_price_actual) *100) * trade[f"STC{i}-Qty"] for i in range(1,4)])/sold_tot
    elif trade[ "Type"] == "STO":
        stc_PnL_all_alert =  np.nansum([(float((bto_price_alert - trade[f"STC{i}-Price-alert"])/bto_price_alert) *100) * trade[f"STC{i}-Qty"] for i in range(1,4)])/sold_tot
        stc_PnL_all_curr = np.nansum([(float((bto_price_actual - trade[f"STC{i}-Price-actual"])/bto_price_actual) *100) * trade[f"STC{i}-Qty"] for i in range(1,4)])/sold_tot

    trade[ "PnL-alert"] = stc_PnL_all_alert
    trade[ "PnL-actual"] = stc_PnL_all_curr

    mutipl = 1 if trade['Asset'] == "option" else .01  # pnl already in %
    trade[ "PnL$"] =  stc_PnL_all* bto_price *mutipl*sold_tot
    trade[ "PnL$-alert"] =  stc_PnL_all_alert* bto_price_alert *mutipl*sold_tot
    trade[ "PnL$-actual"] =  stc_PnL_all_curr* bto_price_actual *mutipl*sold_tot
    
    if any([np.isinf(t) for t in trade if isinstance(t, float)]):
        print("inf", trade)
        trade = trade.replace([np.inf, -np.inf], 0)
    return trade

def get_hist_msgs(filt_author='', filt_date_frm='', filt_date_to='',
                  filt_cont='', chan_name="option_alerts", **kwargs):
    # Provide arguments to filter
    data = pd.read_csv(op.join(cfg['general']['data_dir'] , f"{chan_name}_message_history.csv"),
                       usecols=['Author', 'Date', 'Content', 'Parsed'])
    data = data.rename({"Author": "Trader"}, axis=1)

    try:
        data = filter_data(data,{}, filt_author, filt_date_frm, filt_date_to, msg_cont=filt_cont)
    except Exception as e:
        print("error during history filter data", e)

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
        price= round(float(pos['averagePrice']), 2)
        Qty = pos['longQuantity']
        if Qty == 0:
            Qty = float(pos['shortQuantity'])
        cost = round(price * Qty, 2)
        last = round(float(pos["marketValue"]) / Qty, 2)
        sym = pos['instrument']['symbol']
        val = float(pos["marketValue"])
        if pos['instrument']['assetType'] == "OPTION":
            cost = round(price * Qty * 100, 2)
            last = round(val / Qty, 2)/100

        pnl_t = round(val - cost, 2)
        if  cost == 0:
            pnl_p_t = 0
        else:
            pnl_p_t = round((val -cost)*100 / cost, 2)

        pos_vals = [sym, last, price, pnl_p_t ,pnl_t, Qty, val , cost]
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
        if ord_type == "OCO" and ordr.get('childOrderStrategies') is not None:
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








