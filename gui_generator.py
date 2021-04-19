#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr  9 09:53:44 2021

@author: adonay
"""

import PySimpleGUI as sg
import pandas as pd
from datetime import datetime
import numpy as np
from place_order import get_TDsession


def short_date(datestr, infrm="%Y-%m-%d %H:%M:%S.%f", outfrm="%m/%d %H:%M"):
    return datetime.strptime(datestr, infrm).strftime(outfrm)

def formt_num_2str(x, decim=2):
    if pd.isnull(x) or x == 'nan':
        return ""
    x = round(x, decim)
    return  f"%.{decim}f" % x if abs(x) % 1 else "%d" % x

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
        data[f'STC{i}-PnL'] = data[f'STC{i}-PnL'].apply(lambda x: formt_num_2str(x))

    data["PnL"]  = data[f"STC1-qPnL"].fillna(0) + \
        data["STC2-qPnL"].fillna(0) + \
            data["STC3-qPnL"].fillna(0)

    data["PnL"] = data["PnL"].apply(lambda x: formt_num_2str(x, 1))
    isopen = data['isOpen']

    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])

    cols = ['isOpen', "PnL", 'Date', 'Symbol', 'Trader', 'BTO-Status',
       'Price', 'Alert-Price', 'uQty', 'filledQty',
        'Alerted', 'STC1-PnL', 'STC2-PnL', 'STC3-PnL', 'STC1-Status',
       'STC2-Status', 'STC3-Status', 'STC1-xQty', 'STC2-xQty', 'STC3-xQty', 'exit_plan'
        ]
    data = data[cols]
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


acc_inf = TDSession.get_accounts(TDSession.accountId, ['orders','positions'])

msft_quotes = TDSession.get_quotes(instruments=['RIOT_012122C80'])

acc_inf['securitiesAccount']['accountId']
acc_inf['securitiesAccount']['currentBalances']['liquidationValue']
acc_inf['securitiesAccount']['currentBalances']['cashBalance']
acc_inf['securitiesAccount']['currentBalances']['availableFunds']


positions = acc_inf['securitiesAccount']['positions']

pos_tab = []
for pos in positions:

    price= round(pos['averagePrice'], 2)
    pnl = pos['currentDayProfitLoss']
    pnl_p = pos['currentDayProfitLossPercentage']
    uQty = pos['longQuantity']
    cost = round(price * uQty, 2)
    last = pos["marketValue"]
    sym = pos['instrument']['symbol']
    asset = pos['instrument']['assetType']

    if pos['instrument']['assetType'] == "OPTION":
        last = pos["marketValue"]/100
        cost = round(price * uQty * 100, 2)

    pos_vals = [sym, price, last, pnl_p, pnl, uQty, cost]
    pos_tab.append(pos_vals)

orders =acc_inf['securitiesAccount']['orderStrategies']


def order_info(ord_dic, ord_list):
    """ get info from order request
    :param ord_dic: dict with order info, from 'orderStrategies' or
    'childOrderStrategies'
    """
    ord_fields = ['quantity', 'filledQuantity','price', "stop", 'status',
              'enteredTime']
    sing_ord = []

    price = ord_dic.get("price")
    stprice = ord_dic.get("stopPrice")
    # If SL order with no stopPrice
    if price is None:
        price = ord_dic.get("stopPrice")
        stprice = None
    sing_ord.append(ord_dic['orderType'])
    sing_ord.append(price)
    sing_ord.append(stprice)

    date = ord_dic['enteredTime'].split("+")[0]
    date = short_date(date, "%Y-%m-%dT%H:%M:%S")
    sing_ord.append(date)

    sing_ord.append(ord_dic['quantity'])
    sing_ord.append(ord_dic['filledQuantity'])
    sing_ord.append(ord_dic['status'])
    sing_ord.append(ord_dic['orderId'])

    for leg in ord_dic['orderLegCollection']:
        sing_ord_c = sing_ord.copy()
        sing_ord_c.insert(0, leg['instrument']['symbol'])
        sing_ord_c.insert(1, leg["instruction"])
        ord_list.append(sing_ord_c)

    return ord_list


ord_tab = []
for ordr in orders:

    ord_type = ordr['orderStrategyType']

    if ord_type == "OCO":
        for chl in ordr['childOrderStrategies']:
            ord_tab = order_info(chl, ord_tab)
    else:
        ord_tab = order_info(ordr, ord_tab)











    ordr
    ordr
    ordr













