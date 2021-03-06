#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb 27 09:26:06 2021

@author: adonay
"""



import td
import json
import os.path as op
import numpy as np
import pandas as pd
from datetime import datetime
from config import (data_dir, CHN_NAMES, channel_IDS, UPDATE_PERIOD)
from place_order import get_TDsession, make_BTO_PT_SL_order, send_order, make_STC_lim


def find_open_trade(order, trades_log):

    trades_authr = trades_log["Trader"] == order["Trader"]
    trades_log = trades_log.loc[trades_authr]

    if len(trades_log) == 0:
        return None


    msk_ticker = trades_log["Symbol"].str.contains( order['Symbol'])
    if sum(msk_ticker) == 0:
       return None

    ticker_trades = trades_log[msk_ticker]
    sold_Qty =  ticker_trades[[f"STC{i}-Qty" for i in range(1,4)]].sum(1)
    open_trade = sold_Qty< .99

    if sum(open_trade) == 0:
       return None

    if sum(open_trade)> 1:
       raise "Traded more than once open"
    open_trade, = open_trade[open_trade].index.values
    return open_trade


class portfolio():

    def __init__(self):
        self.portfolio_fname = data_dir + "/trader_portfolio.csv"
        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=[
                "Date", "Symbol", "Trader", "isOpen", "Asset", "Type", "Price",
                "Qty", "Avged", "Plan_ord", "Plan_all", "ordID", "plan_ordIds"] + [
                    "STC%d-%s"% (i, v) for v in
                    ["Alerted", "Status", "Qty", "units", "Price", "PnL","Date", "ordID"] 
                    for i in range(1,4)] )

        self.alerts_log_fname = data_dir + "/trader_logger.csv"
        if op.exists(self.alerts_log_fname):
            self.portfolio = pd.read_csv(self.alerts_log_fname)
        else:            
            self.alerts_log = pd.DataFrame(columns=["Date", "Symbol", "Trader",
                                                "action", "pasesed", "msg"])
        self.TDsession = get_TDsession()
        self.accountId = self.TDsession.accountId

    def save_logs(self, csvs=["port", "alert"]):
        if "port" in csvs:
            self.portfolio.to_csv(self.portfolio_fname, index=False)
        if "alert" in csvs:    
            self.alerts_log.to_csv(self.alerts_log_fname, index=False)
        
        
    def new_stock_alert(self, order:dict, pars:str, msg):
        """ get order from ```parser_alerts``` """

        open_trade = find_open_trade(order, self.portfolio)
        isOpen = 1 if open_trade != None else 0
        
        time_strf = "%Y-%m-%d %H:%M:%S.%f"
        date = datetime.now().strftime(time_strf) 
    
        log_alert = {"Date": date,
                     "Symbol": order['Symbol'],
                     "Trader" : order['Trader'],
                     "pasesed" : pars,
                     "msg": msg
                     }
    
        if not isOpen and order["action"] == "BTO":
            # order["PTs"] = [order[f"PT{i}"] for i in range(1, order['n_PTs']+1)]
            order["PTs"] = [order["PT1"]]
            order['PTs_Qty'] = [1]
            order_response, order_id, order, ord_chngd = self.confirm_and_send(order, pars,
                                                       make_BTO_PT_SL_order)
            ordered = eval(order_response['request_body'])

            order_info = self.TDsession.get_orders(account=self.accountId, 
                                              order_id=order_id)
            order_status = order_info['status']

            Plan_ord = {}
            planIDs = [] # get it from order_info
            for child in ordered['childOrderStrategies']:
                for childStrat in child['childOrderStrategies']:
                    if childStrat['orderType'] == "LIMIT":
                        Plan_ord['PT']= childStrat['price']
                    elif childStrat['orderType'] in ["STOP", "STOPLIMIT"]:
                        Plan_ord['SL']= childStrat['stopPrice']

            plan_all = {}
            for p in [f"PT{i}" for i in range (1,4)] + ["SL"]:
                if order[p] is not None:
                    plan_all[p] = order[p]

            new_trade = {"Date": date,
                         "Symbol": order['Symbol'],
                         'isOpen': order_status,
                         "Qty": order_info['quantity'],
                         "Asset" : "Stock",
                         "Type" : "BTO",
                         "Price" : ordered["price"],
                         "ordID" : order_id,
                         "Plan_ord" : Plan_ord,
                         "Plan_all"  : str(plan_all),
                         "Trader" : order['Trader']
                         }
            self.portfolio = self.portfolio.append(new_trade, ignore_index=True)
            #Log portfolio, trades_log
            log_alert['action'] = "BTO"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(self)
            
        elif order["action"] == "BTO" and order['avg'] is not None:
            # if PT in order: cancel previous and make_BTO_PT_SL_order
            # else : BTO
            trades_log, str_act = make_BTO_Avg(order, trades_log, isOpen)
            #Log portfolio, trades_log
            
        elif order["action"] == "BTO":
            str_act = "Repeated BTO"
            log_alert['action'] = "BTO-Null"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(["alert"])
            
        elif order["action"] == "STC" and isOpen is None:
            str_act = "STC without BTO, maybe alredy sold"
            log_alert['action'] = "STC-Null"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(["alert"])
            
        elif order["action"] == "STC":
            position = self.portfolio.iloc[open_trade]
            # check if position already alerted and closed
            for i in range(1,4):
                STC = f"STC{i}"
                if pd.isnull(position[f"STC{i}-Alerted"]):
                    self.portfolio.loc[open_trade, f"STC{i}-Alerted"] = 1
                    if not pd.isnull(position[ f"STC{i}-Price"]):
                        print("Already sold")
                        log_alert['action'] = "STC-DoneBefore"
                        self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                        self.save_logs(["alert"])
                        return
                    break
            else:
                str_STC = "How many STC already?"
                print (str_STC)
                log_alert['action'] = "STC-TooMany"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                return
            
            qty_bought = position["Qty"]
            #TODO: change qty from portfolio to getting TD account position
            qty_sold = np.nansum([position[f"STC{i}-Qty"] for i in range(1,4)])
            
            if order['Qty'] == 1:  # Sell all
                # TODO: close other waiting orders
                order['qty'] = int(position["Qty"]) - qty_sold
            elif order['Qty'] < 1:  #portion 
                order['qty'] = round(qty_bought * order['Qty'])
                
            else:
                order['qty'] =  order['Qty']
            
            assert(order['qty'] + qty_sold <= qty_bought)
            
            order_response, order_id, order, ord_chngd = self.confirm_and_send(order, pars,
                           make_STC_lim) 

            ordered = eval(order_response['request_body'])

            order_info = self.TDsession.get_orders(account=self.accountId, 
                                              order_id=order_id)
            order_status = order_info['status']
            # Check if STC price changed
            # if position[STC + "-Status"] in ["WORKING", "WAITING"]
            
            sold_unts = order_info['orderLegCollection'][0]['quantity']          
            
            bto_price = self.portfolio.loc[open_trade, "Price"]
            stc_PnL = float((order["price"] - bto_price)/bto_price) *100
            
            #Log portfolio
            self.portfolio.loc[open_trade, STC + "-Status"] = order_info['status']
            self.portfolio.loc[open_trade, STC + "-Price"] = order_info['price']
            self.portfolio.loc[open_trade, STC + "-Date"] = date
            self.portfolio.loc[open_trade, STC + "-Qty"] = order['Qty']
            self.portfolio.loc[open_trade, STC + "-units"] = sold_unts
            self.portfolio.loc[open_trade, STC + "-PnL"] = stc_PnL
            self.portfolio.loc[open_trade, STC + "-ordID"] = order_id
        
            str_STC = f"{STC} {order['Symbol']} @{order_info['price']} ({order['Qty']}), {stc_PnL:.2f}%"
                      
            #Log trades_log
            log_alert['action'] = "STC-partial" if order['Qty']<0 else "STC-ALL" 
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(self)
            
            print(str_STC)


    def order_to_pars(self, order):
        pars_str = f"{order['action']} {order{'Symbol'}} @order{'price'}"
        for i in range(1, 4):
            pt = f"PT{i}"
            if pt in order.keys() and order[pt] is not None:
                pars_str = pars_str + f" {pt}: {order[pt]}"
            if "SL" in order.keys() and order["SL"] is not None:
                pars_str = pars_str + f" SL: {order['SL']}"
        return pars_str


    def confirm_and_send(self, order, pars, order_funct):
            resp, order, ord_chngd = self.notify_alert(order, pars)
            if resp in ["yes", "y"]:
                ord_resp, ord_id = send_order(order_funct(**order), self.TDsession)
                return ord_resp, ord_id, order, ord_chngd


    def notify_alert(self, order, pars):
        symb = order['Symbol']
        ord_ori = order.copy()
        while True:
            quotes = self.TDsession.get_quotes(instruments=[symb])
            price_now = f"CURRENTLY @{quotes[symb]['askPrice']}"
            resp = input(f"{pars} {price_now}. Make trade? (y, n or (c)hange) \n")
            if resp in [ "c", "change"]:
                new_order = order.copy()
                new_order['price'] = float(input(f"Change price @{order['price']}" + 
                                        f" {price_now}? Leave blank if NO \n")
                                      or order['price']) 
                if order['action'] == 'BTO':
                    PTs = [order[f'PT{i}'] for i in range(1,4)]
                    PTs = eval(input(f"Change PTs @{PTs} {price_now}?" + \
                                      " Leave blank if NO, respnd eg [1, None, None] \n")
                                          or str(PTs)) 
                    new_order["SL"] = float(input(f"Change SL @{order['SL']} {price_now}?"+
                                      " Leave blank if NO \n")
                                      or order['SL'])
                    
                    new_n = len([i for i in PTs if i is not None ])
                    if new_n != order['n_PTs']:
                        new_order['n_PTs']= new_n
                        new_order['PTs_Qty'] = [round(1/new_n,2) for i in range(new_n)]
                        new_order['PTs_Qty'][-1] = new_order['PTs_Qty'][-1] + (1- sum(new_order['PTs_Qty']))
                order = new_order
                pars = order_to_pars(order)
            else :
                break
            
        ord_chngd = ord_ori != order
        
        return resp, order, ord_chngd
        
        
        
# order = {'action': 'BTO',
#  'Symbol': 'DPW',
#  'price': 4.05,
#  'avg': None,
#  'PT1': 5.84,
#  'PT2': 6.39,
#  'PT3': 6.95,
#  'SL': 4.01,
#  'n_PTs': 3,
#  'PTs_Qty': [.33, .33, .34],
#  'Trader': 'ScaredShirtless#0001',
#  'PTs': [5.84],
#  'qty': 2}

# pars = "BTO DPW @4.05 PT! 5.84 SL: 4.01"

# msg = "BTO DPW @4.05"


   
# order = {'action': 'STC',
#  'Symbol': 'DPW',
#  'price': 5.84,
#  'qty': 2}

# pars = "STC DPW @ 5.84"


# order = {'action': 'STC',
#  'Symbol': 'CURLF',
#  'price': 24.05,
#  'Trader': 'ScaredShirtless#0001',
#  'PTs': [5.84],
#  'Qty': 1}

# pars = "STC CURLF @  24.0"
