#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  9 09:53:44 2021

@author: adonay
"""


import pandas as pd
from datetime import datetime
import numpy as np
from place_order import get_TDsession


def short_date(datestr, infrm="%Y-%m-%d %H:%M:%S.%f", outfrm="%m/%d %H:%M"):
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
    values_s = [str(round(v, decim)) if v %1 else str(round(v)) for v in values]
    len_int = max([len(v.split('.')[0]) for v in values_s])
    len_dig = max([len(v.split('.')[-1]) if "." in v else 0 for v in values_s])
    len_tot = len_int + len_dig + 1 if len_dig else  len_int + len_dig
    return len_tot, len_int, len_dig

def pd_col_str_frmt(pd_Series, max_decim=2, remove_zero=True):
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

    if plan == "" or plan == "{}":
        return "None"
    plan = eval(plan)

    PT = [str(v) for v in [plan.get(f"PT{i}") for i in range(1,4)] if v is not None]
    SL = plan.get('SL')

    plan = "PT:" + ",".join(PT) if PT else ""
    sl_str = ", SL:" if plan else "SL:"
    plan = plan + sl_str + str(SL) if SL else plan

    return plan

def get_portf_data():
    data = pd.read_csv("data/trader_portfolio.csv")
    cols_out = ['Asset', 'Type', 'Avged', 'STC1-uQty', 'STC2-uQty', 'STC3-uQty',
                'STC1-Price', 'STC2-Price', 'STC3-Price','STC1-Date', 'STC2-Date',
                'STC3-Date', 'STC1-ordID', 'STC2-ordID', 'STC3-ordID', 'ordID']

    cols = [c for c in data.columns if c not in cols_out]

    data = data[cols]

    data['Date'] = data['Date'].apply(lambda x: short_date(x))

    data['exit_plan']= data['exit_plan'].apply(lambda x: format_exitplan(x))
    data["isOpen"] = data["isOpen"].map({1:"Yes", 0:"No"})
    alerts = data[['STC1-Alerted', 'STC2-Alerted', 'STC3-Alerted']].sum(1)
    data["Alerted"]= alerts.astype(int)

    cols_pnl = ['STC1-PnL', 'STC2-PnL', 'STC3-PnL']
    for i in range(1,4):
        # Get xQty relative PnL
        data[f"STC{i}-qPnL"] = data[f'STC{i}-PnL']* data[f'STC{i}-xQty']
        # Format nums to str for left centered col
        data[f'STC{i}-PnL'] = pd_col_str_frmt(data[f'STC{i}-PnL'])
        data[f'STC{i}-xQty'] = pd_col_str_frmt(data[f'STC{i}-xQty'])

    data["PnL"]  = data[f"STC1-qPnL"].fillna(0) + \
        data["STC2-qPnL"].fillna(0) + \
            data["STC3-qPnL"].fillna(0)
    data["PnL"] = pd_col_str_frmt(data["PnL"], 1)

    isopen = data['isOpen']
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])

    frm_cols = ['Price', 'Alert-Price', 'uQty', 'filledQty', 'Alerted']
    for cfrm in frm_cols:
        data[cfrm] = pd_col_str_frmt(data[cfrm])

    cols = ['isOpen', "PnL", 'Date', 'Symbol', 'Trader', 'BTO-Status',
       'Price', 'Alert-Price', 'uQty', 'filledQty',
        'Alerted', 'STC1-PnL', 'STC2-PnL', 'STC3-PnL', 'STC1-Status',
       'STC2-Status', 'STC3-Status', 'STC1-xQty', 'STC2-xQty', 'STC3-xQty', 'exit_plan'
        ]
    data = data[cols]
    data.fillna("", inplace=True)
    header_list = data.columns.tolist()
    header_list = [d.replace('STC', '') for d in header_list]

    data = data.values.tolist()
    # tpnl = [[i] for i in data["PnL"].values.tolist()]
    # isopen = [[i] for i in isopen.values.tolist()]
    return data, header_list#, tpnl, isopen


hists = ['option_alerts_message_history.csv']

def get_hist_msgs(filt_author='', filt_date_frm='', filt_date_to='',
                  filt_cont='', chan_name="option_alerts", **kwargs):
    # Provide arguments to filter

    data = pd.read_csv(f"data/{chan_name}_message_history.csv")
    cols = ['Author', 'Date', 'Content']
    data = data[cols]

    data = data[~data['Author'].str.contains('Xcapture')]
    data['Author'] = data['Author'].apply(lambda x: x.split('#')[0])
    data['Date'] = data['Date'].apply(lambda x: short_date(x))

    data = data.dropna()
    if filt_author:
        data = data[data['Author'].str.contains(filt_author, case=False)]
    if filt_date_frm:
        data = data[data['Date'] > filt_date_frm]
    if filt_date_to:
        data = data[data['Date'] < filt_date_to]
    if filt_cont:
        data = data[data['Content'].str.contains(filt_cont, case=False)]

    header_list = data.columns.tolist()
    return data.values.tolist(), header_list



def get_acc_bals(TDSession):
    acc_inf = TDSession.get_accounts(TDSession.accountId, ['orders','positions'])

    accnt= {"id" : acc_inf['securitiesAccount']['accountId'],
        "balance": acc_inf['securitiesAccount']['currentBalances']['liquidationValue'],
        "cash": acc_inf['securitiesAccount']['currentBalances']['cashBalance'],
        "funds": acc_inf['securitiesAccount']['currentBalances']['availableFunds'],
        }
    return acc_inf, accnt


def get_pos(acc_inf):
    positions = acc_inf['securitiesAccount']['positions']
    pos_tab = []
    pos_headings = ["Sym", "Last", "price", "PnL_%", "PnL","Qty", "Val", "Cost"]
    for pos in positions:
        price= round(pos['averagePrice'], 2)
        # pnl = pos['currentDayProfitLoss']
        pnl_p = pos['currentDayProfitLossPercentage'] * 100
        uQty = pos['longQuantity']
        cost = round(price * uQty, 2)
        last = round(pos["marketValue"] / uQty, 2)
        sym = pos['instrument']['symbol']
        asset = pos['instrument']['assetType']
        val = pos["marketValue"]
        if pos['instrument']['assetType'] == "OPTION":
            cost = round(price * uQty * 100, 2)
            last = round(pos["marketValue"] / uQty, 2)/100

        pnl_t = round(val - cost, 2)
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
    ord_fields = ['quantity', 'filledQuantity','price', "stop", 'status',
              'enteredTime']
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
    sing_ord.append(ord_dic['orderId'])

    for leg in ord_dic['orderLegCollection']:
        sing_ord_c = sing_ord.copy()
        sing_ord_c.insert(0, leg['instrument']['symbol'])
        sing_ord_c.insert(1, leg["instruction"])
        ord_list.append(sing_ord_c)

    return ord_list, ord_headings


def get_orders(acc_inf):
    orders =acc_inf['securitiesAccount']['orderStrategies']

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








