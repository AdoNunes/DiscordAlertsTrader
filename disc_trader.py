#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb 27 09:26:06 2021

@author: adonay
"""

import re
import os.path as op
import numpy as np
import pandas as pd
from datetime import datetime
import config as cfg 
from place_order import (get_TDsession, make_BTO_PT_SL_order, send_order, 
                         make_STC_lim, make_lim_option,
                         make_Lim_SL_order, make_STC_SL)
# import dateutil.parser.parse as date_parser
from colorama import Fore, Back, Style


def find_open_trade(order, trades_log):

    trades_authr = trades_log["Trader"] == order["Trader"]
    trades_log = trades_log.loc[trades_authr]

    if len(trades_log) == 0:
        return None

    msk_ticker = trades_log["Symbol"].str.contains( order['Symbol'])
    if sum(msk_ticker) == 0:
       return None

    ticker_trades = trades_log[msk_ticker]
    sold_Qty =  ticker_trades[[f"STC{i}-xQty" for i in range(1,4)]].sum(1)
    open_trade = sold_Qty< .99

    if sum(open_trade) == 0:
       return None

    if sum(open_trade)> 1:
       raise "Traded more than once open"
    open_trade, = open_trade[open_trade].index.values
    return open_trade


class AlertTrader():

    def __init__(self, 
                 portfolio_fname=cfg.portfolio_fname,
                 alerts_log_fname=cfg.alerts_log_fname,
                 test_TDsession=None):        
       
        self.portfolio_fname = portfolio_fname
        self.alerts_log_fname = alerts_log_fname
        
        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=[
                "Date", "Symbol", "Trader", "isOpen", "BTO-Status", "Asset", "Type", "Price",
                "uQty", "Avged", "Plan_ord", "Plan_all", "ordID", "plan_ordIds"] + [
                    "STC%d-%s"% (i, v) for v in
                    ["Alerted", "Status", "xQty", "uQty", "Price", "PnL","Date", "ordID"] 
                    for i in range(1,4)] )
        
        if op.exists(self.alerts_log_fname):
            self.alerts_log = pd.read_csv(self.alerts_log_fname)
        else:            
            self.alerts_log = pd.DataFrame(columns=["Date", "Symbol", "Trader",
                                                "action", "parsed", "msg", "portfolio_idx"])
            
        # For testing a fake TDsession is created
        if test_TDsession is not None:
            self.TDsession = test_TDsession
        else:
             self.TDsession = get_TDsession()
                
        self.accountId = self.TDsession.accountId

    def save_logs(self, csvs=["port", "alert"]):
        if "port" in csvs:
            self.portfolio.to_csv(self.portfolio_fname, index=False)
        if "alert" in csvs:    
            self.alerts_log.to_csv(self.alerts_log_fname, index=False)


    def order_to_pars(self, order):
        pars_str = f"{order['action']} {order['Symbol']} @{order['price']}"
        if {order['action']} == "BTO":
            for i in range(1, 4):
                pt = f"PT{i}"
                if pt in order.keys() and order[pt] is not None:
                    pars_str = pars_str + f" {pt}: {order[pt]}"
                if "SL" in order.keys() and order["SL"] is not None:
                    pars_str = pars_str + f" SL: {order['SL']}"
        elif {order['action']} == "STC":
            pars_str = pars_str + f" Qty:{order['uQty']}({int(order['xQty']*100)}%)"
        return pars_str


    def confirm_and_send(self, order, pars, order_funct):
            resp, order, ord_chngd = self.notify_alert(order, pars)
            if resp in ["yes", "y"]:
                
                ord_resp, ord_id = send_order(order_funct(**order), self.TDsession)
                if ord_resp is None:
                    raise("Something wrong with order response")
                
                print(Back.GREEN + f"Sent order {pars}")
                return ord_resp, ord_id, order, ord_chngd
            
            elif resp in ["no", "n"]:
                return None, None, order, None

    def notify_alert(self, order, pars):
        
        def price_now(Symbol):
            quote = self.TDsession.get_quotes(
                instruments=[Symbol])[Symbol]['askPrice']
            return "CURRENTLY @%.2f"% quote
        
        symb = order['Symbol']
        ord_ori = order.copy()
        while True:

            resp = input(Back.RED  + f"{pars} {price_now(symb)}. Make trade? (y, n or (c)hange) \n").lower()
                         
            if resp in [ "c", "change", "y", "yes"] and 'uQty' not in order.keys():                
                order['uQty'] = int(input(f" Numer of share/contractsnot available. How many units to buy? {price_now(symb)} \n"))
                
            if resp in [ "c", "change"]:
                new_order = order.copy()
                new_order['price'] = float(input(f"Change price @{order['price']}" + 
                                        f" {price_now(symb)}? Leave blank if NO \n")
                                      or order['price']) 
                if order['action'] == 'BTO':
                    PTs = [order[f'PT{i}'] for i in range(1,4)]
                    PTs = eval(input(f"Change PTs @{PTs} {price_now(symb)}? \
                                      Leave blank if NO, respnd eg [1, None, None] \n")
                                          or str(PTs)) 
                    new_order["SL"] = (input(f"Change SL @{order['SL']} {price_now(symb)}?"+
                                      " Leave blank if NO \n")
                                      or order['SL'])
                    new_order["SL"] = eval(new_order["SL"]) if isinstance(new_order["SL"], str) else new_order["SL"]
                    
                    new_n = len([i for i in PTs if i is not None ])
                    if new_n != order['n_PTs']:
                        new_order['n_PTs']= new_n
                        new_order['PTs_Qty'] = [round(1/new_n,2) for i in range(new_n)]
                        new_order['PTs_Qty'][-1] = new_order['PTs_Qty'][-1] + (1- sum(new_order['PTs_Qty']))
                order = new_order
                pars = self.order_to_pars(order)
            else :
                break
            
        ord_chngd = ord_ori != order
        
        return resp, order, ord_chngd
        
    def close_waiting_order(open_trade):
        pass
    
    
    ######################################################################
    # STOCK TRADER
    ######################################################################
    
    def new_stock_alert(self, order:dict, pars:str, msg):
        """ get order from ```parser_alerts``` """

        open_trade = find_open_trade(order, self.portfolio)
        isOpen = 1 if open_trade != None else 0
        
        time_strf = "%Y-%m-%d %H:%M:%S.%f"
        date = datetime.now().strftime(time_strf) 
    
        log_alert = {"Date": date,
                     "Symbol": order['Symbol'],
                     "Trader" : order['Trader'],
                     "parsed" : pars,
                     "msg": msg
                     }
    
        if not isOpen and order["action"] == "BTO":
            # order["PTs"] = [order[f"PT{i}"] for i in range(1, order['n_PTs']+1)]
            order["PTs"] = [order["PT1"]]
            order['PTs_Qty'] = [1]
            order_response, order_id, order, ord_chngd = self.confirm_and_send(order, pars,
                                                       make_BTO_PT_SL_order)
            
            if order_response is None:  #Assume trade not accepted
                log_alert['action'] = "BTO-notAccepted"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])   
                print(Back.GREEN + "BTO not accepted by user")
                return
            
            ordered = eval(order_response['request_body'])

            order_info = self.TDsession.get_orders(account=self.accountId, 
                                              order_id=order_id)
            order_status = order_info['status']

            keys = ["PT", "SL"]
            Plan_ord = {k:[] for k in keys}  # TODO: change name to exit_sent_price
            planIDs =  {k:[] for k in keys}  # TODO: change name to exit_sent_ordIDs
            
            if 'childOrderStrategies' in order_info.keys():
                for child in order_info['childOrderStrategies']:
                    # if simple strategy
                    if child['orderStrategyType'] != "OCO":  # Maybe key not exists if not OCO   
                        ord_type = child['orderType']    
                        if ord_type == "LIMIT":
                            Plan_ord["PT"].append(child['price'])
                            planIDs["PT"].append(child['orderId'])
                        elif ord_type in ["STOP", "STOPLIMIT"]:
                            Plan_ord["SL"].append(child['stopPrice'])  
                            planIDs["SL"].append(child['orderId'])
                             
                    # empty if not complex strategy                            
                    for childStrat in child['childOrderStrategies']:
                        if childStrat['orderType'] == "LIMIT":
                            Plan_ord['PT'].append(childStrat['price'])
                            planIDs["PT"].append(childStrat['orderId'])
                        elif childStrat['orderType'] in ["STOP", "STOPLIMIT"]:
                            Plan_ord['SL'].append(childStrat['stopPrice'])
                            planIorder_infoDs["SL"].append(childStrat['orderId'])
                            
                assert(len(planIDs["PT"]) == len(order["PTs"]))  # check why diff N ord IDs

            
            plan_all = {}
            for p in [f"PT{i}" for i in range (1,4)] + ["SL"]:
                if order[p] is not None:
                    plan_all[p] = order[p]

            new_trade = {"Date": date,
                         "Symbol": order['Symbol'],
                         'isOpen': 1,
                         'BTO-Status' : order_status,
                         "uQty": order_info['quantity'],
                         "Asset" : "Stock",
                         "Type" : "BTO",
                         "Price" : ordered["price"],
                         "ordID" : order_id,
                         "Plan_ord" : Plan_ord,
                         "Plan_all"  : str(plan_all),
                         "plan_ordIds" : planIDs,
                         "Trader" : order['Trader']
                         }
            self.portfolio = self.portfolio.append(new_trade, ignore_index=True)
            #Log portfolio, trades_log
            log_alert['action'] = "BTO"
            log_alert["portfolio_idx"] = len(self.portfolio) - 1
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs()
            
            print(Back.GREEN + f"BTO {order['Symbol']} executed. Status: {order_status}")
            
        elif order["action"] == "BTO" and order['avg'] is not None:
            # if PT in order: cancel previous and make_BTO_PT_SL_order
            # else : BTO
            print(Back.BLUE +"BTO AVG not implemented yet")
            #Log portfolio, trades_log
            
        elif order["action"] == "BTO":
            str_act = "Repeated BTO"
            log_alert['action'] = "BTO-Null-Repeated"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(["alert"])
            print(Back.RED +str_act)
            
        elif order["action"] == "STC" and isOpen == 0:
            str_act = "STC without BTO, maybe alredy sold"
            log_alert['action'] = "STC-Null-notOpen"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(["alert"])
            print(Back.RED +str_act)
            
        elif order["action"] == "STC":
            position = self.portfolio.iloc[open_trade]
            # check if position already alerted and closed
            for i in range(1,4):
                STC = f"STC{i}"
                if pd.isnull(position[f"STC{i}-Alerted"]):
                    self.portfolio.loc[open_trade, f"STC{i}-Alerted"] = 1
                    if not pd.isnull(position[ f"STC{i}-Price"]):
                        print(Back.GREEN + "Already sold")
                        log_alert['action'] = "STC-DoneBefore"
                        log_alert["portfolio_idx"] = open_trade
                        self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                        self.save_logs(["alert"])
                        return
                    break
            else:
                str_STC = "How many STC already?"
                print (Back.RED + str_STC)
                log_alert['action'] = "STC-TooMany"
                log_alert["portfolio_idx"] = open_trade
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                return
            
            qty_bought = position["uQty"]
            #TODO: change qty from portfolio to getting TD account position
            qty_sold = np.nansum([position[f"STC{i}-uQty"] for i in range(1,4)])
            
            if order['xQty'] == 1:  # Sell all
                # TODO: close other waiting orders
                order['uQty'] = int(position["Qty"]) - qty_sold
            elif order['xQty'] < 1:  #portion 
                order['uQty'] = round(qty_bought * order['Qty'])

            assert(order['uQty'] + qty_sold <= qty_bought)
            
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
            self.portfolio.loc[open_trade, STC + "-xQty"] = order['xQty']
            self.portfolio.loc[open_trade, STC + "-uQty"] = sold_unts
            self.portfolio.loc[open_trade, STC + "-PnL"] = stc_PnL
            self.portfolio.loc[open_trade, STC + "-ordID"] = order_id
        
            str_STC = f"{STC} {order['Symbol']} @{order_info['price']} Qty:{order['uQty']} ({order['xQty']}), {stc_PnL:.2f}%"
                      
            #Log trades_log
            log_alert['action'] = "STC-partial" if order['xQty']<1 else "STC-ALL" 
            log_alert["portfolio_idx"] = open_trade
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(self)
            
            print(Back.GREEN + str_STC)


    ######################################################################
    # OPTION TRADER
    ######################################################################
    
    def new_option_alert(self, order:dict, pars:str, msg):
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
            # order["PTs"] = [order["PT1"]]
            # order['PTs_Qty'] = [1]
            
            order_response, order_id, order, ord_chngd = self.confirm_and_send(order, pars,
                                                       make_lim_option)
            
            if order_response is None:  #Assume trade not accepted
                log_alert['action'] = "BTO-notAccepted"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])  
                
                return
                
            ordered = eval(order_response['request_body'])

            order_info = self.TDsession.get_orders(account=self.accountId, 
                                              order_id=order_id)
            order_status = order_info['status']

            keys = ["PT", "SL"]
            Plan_ord = {k:[] for k in keys}
            planIDs =  {k:[] for k in keys}
            
             # if 'childOrderStrategies' in ordered.keys():           
            for child in order_info['childOrderStrategies']:
                # if simple strategy
                if child['orderStrategyType'] != "OCO":  # Maybe key not exists if not OCO      
                    ord_type = child['orderType']
                    if ord_type == "LIMIT":
                        Plan_ord["PT"].append(child['price'])
                        planIDs["PT"].append(child['orderId'])
                    elif ord_type in ["STOP", "STOPLIMIT"]:
                        Plan_ord["SL"].append(child['stopPrice'])  
                        planIDs["SL"].append(child['orderId'])
                         
                # empty if not complex strategy                            
                for childStrat in child['childOrderStrategies']:
                    if childStrat['orderType'] == "LIMIT":
                        Plan_ord['PT'].append(childStrat['price'])
                        planIDs["PT"].append(childStrat['orderId'])
                    elif childStrat['orderType'] in ["STOP", "STOPLIMIT"]:
                        Plan_ord['SL'].append(childStrat['stopPrice'])
                        planIDs["SL"].append(childStrat['orderId'])
                        

            plan_all = {}
            for p in [f"PT{i}" for i in range (1,4)] + ["SL"]:
                if order[p] is not None:
                    plan_all[p] = order[p]

            new_trade = {"Date": date,
                         "Symbol": order['Symbol'],
                         'isOpen': 1,
                         'BTC-Status': order_status,
                         "uQty": order_info['quantity'],
                         "Asset" : "Option",
                         "Type" : "BTO",
                         "Price" : ordered["price"],
                         "ordID" : order_id,
                         "Plan_ord" : Plan_ord,
                         "STC1-ordID" : planIDs,
                         "Plan_all"  : str(plan_all),
                         "Trader" : order['Trader']
                         }
            self.portfolio = self.portfolio.append(new_trade, ignore_index=True)
            #Log portfolio, trades_log
            log_alert['action'] = "BTO"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs( )
            
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
                        print(Back.GREEN + "Already sold")
                        log_alert['action'] = "STC-DoneBefore"
                        self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                        self.save_logs(["alert"])
                        return
                    break
            else:
                str_STC = "How many STC already?"
                print (Back.RED + str_STC)
                log_alert['action'] = "STC-TooMany"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                return
            
            qty_bought = position["uQty"]
            #TODO: change qty from portfolio to getting TD account position
            qty_sold = np.nansum([position[f"STC{i}-uQty"] for i in range(1,4)])
            
            if order['xQty'] == 1:  # Sell all
                # TODO: close other waiting orders
                order['uQty'] = int(position["uQty"]) - qty_sold
            elif order['xQty'] < 1:  #portion 
                order['uQty'] = int(round(qty_bought * order['xQty']))
                
            else:
                order['uQty'] =  order['uQty']
            
            assert(order['uQty'] + qty_sold <= qty_bought)
            
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
            self.portfolio.loc[open_trade, STC + "-xQty"] = order['xQty']
            self.portfolio.loc[open_trade, STC + "-uQty"] = sold_unts
            self.portfolio.loc[open_trade, STC + "-PnL"] = stc_PnL
            self.portfolio.loc[open_trade, STC + "-ordID"] = order_id
        
            str_STC = f"{STC} {order['Symbol']} @{order_info['price']} Qty:{order['uQty']}({int(order['xQty']*100)}%), {stc_PnL:.2f}%"
                      
            #Log trades_log
            log_alert['action'] = "STC-partial" if order['xQty']<1 else "STC-ALL" 
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(self)
            
            print(Back.GREEN + str_STC)

    def log_filled_STC(self, order_id, open_trade, STC):
        
        order_info = self.TDsession.get_orders(account=self.accountId, 
                                          order_id=order_id)

        sold_unts = order_info['orderLegCollection'][0]['quantity']
        
        bto_price = self.portfolio.loc[open_trade, "Price"]
        stc_PnL = float((order["price"] - bto_price)/bto_price) *100
        
        date = order_info["closeTime"]
        #Log portfolio
        self.portfolio.loc[open_trade, STC + "-Status"] = order_info['status']
        self.portfolio.loc[open_trade, STC + "-Price"] = order_info['price']
        self.portfolio.loc[open_trade, STC + "-Date"] = date
        self.portfolio.loc[open_trade, STC + "-xQty"] = order['xQty']
        self.portfolio.loc[open_trade, STC + "-uQty"] = sold_unts
        self.portfolio.loc[open_trade, STC + "-PnL"] = stc_PnL
        self.portfolio.loc[open_trade, STC + "-ordID"] = order_id
    
        str_STC = f"{STC} {order['Symbol']} @{order_info['price']} Qty:\
            {order['uQty']}({int(order['xQty']*100)}%), {stc_PnL:.2f}%"
                               
        print (Back.GREEN + f"Filled: {str_STC}")
        self.save_logs()
            
            
        
    def update_orders(self):
        
        for i in range(len(self.portfolio)):
            trade = self.portfolio.iloc[i]
            
            if trade["isOpen"] == 0:
                continue
            
            if trade["BTO-Status"]  in ["QUEUED", "WORKING"]:
                order_id = trade['ordID']
                order_status = self.TDsession.get_orders(account=self.accountId, 
                                                         order_id=order_id
                                                         )['status']
                
                self.portfolio.loc[i, "BTO-Status"] = order_status
                trade = self.portfolio.iloc[i]
                
            if trade["BTO-Status"] != "FILLED":
                continue

            plan_all = eval(trade["Plan_all"])
            if  plan_all == {}:
                continue

            # Calculate x/uQty:
            uQty_bought = trade['uQty']
            nPTs =  len([i for i in range(1,4) if plan_all[f"PT{i}"] is not None])
            uQty = [round(uQty_bought/nPTs)]*nPTs
            uQty[-1] = int(uQty_bought - sum(uQty[:-1]))
            
            xQty = [round(1/nPTs, 1)]*nPTs
            xQty[-1] = 1 - sum(xQty[:-1])
            
            # Go over exit plans and make orders
            for ii in range(1,4):
                STC = f"STC{ii}"
                order = {'Symbol': trade['Symbol']}

                # If Option add strike field
                ord_inf = trade['Symbol'].split("_")
                if len(ord_inf) == 2:
                    opt_type = "C" if "C" in ord_inf[1] else "P"
                    strike = str(re.split('C|P', ord_inf[1])[1]) + opt_type
                    order['strike'] = strike

                STC_ordID = trade[STC+"-ordID"]
                if np.isnan(STC_ordID):
                    SL = plan_all["SL"]
                    
                    ord_func = None
                    # Lim and Sl OCO order
                    if plan_all[f"PT{ii}"] is not None and SL is not None:
                        # Lim_SL order
                        ord_func = make_Lim_SL_order
                        order["PT"] = plan_all[f"PT{ii}"]
                        order["SL"] = plan_all["SL"]
                        order['uQty'] = uQty[ii]
                        order['xQty'] = xQty[ii]
                    # Lim order
                    elif plan_all[f"PT{i}"] is not None and SL is None:
                        ord_func = make_STC_lim
                        order["price"] = plan_all[f"PT{ii}"]
                        order['uQty'] = uQty[ii]
                        order['xQty'] = xQty[ii]
                    # SL order
                    elif i == 1 and SL is not None:
                        ord_func = make_STC_SL
                        order["SL"] = plan_all["SL"]
                        order['uQty'] = trade['uQty']
                        order['xQty'] = 1
                    else:
                        raise("Case not caught")

                    if ord_func is not None:
                        _, STC_ordID = send_order(ord_func(**order), self.TDsession)
                        self.portfolio.loc[i, STC+"-ordID"] = STC_ordID
                        trade = self.portfolio.iloc[i]
                    else:
                        break
                
                # Get status exit orders
                order_info = self.TDsession.get_orders(account=self.accountId, 
                                      order_id=STC_ordID)
                if order_info['orderStrategyType'] == "OCO":
                    order_status = [
                        order_info['childOrderStrategies'][0]['status'],
                        order_info['childOrderStrategies'][1]['status']]
                    assert(order_status[0]==order_status[1])
                    order_status = order_status[0]
                elif order_info['orderStrategyType'] == 'SINGLE':
                    order_status = order_info['status']
                else:
                    raise("Not sure type order. Check")
                
                self.portfolio.loc[i, STC+"-Status"] = order_status
                trade = self.portfolio.iloc[i]
                
                if order_status == "FILLED":
                    self.log_STC_info(STC_ordID, i, STC)

                    
                
                    
        
if 0 :
    
    order = {'action': 'BTO',
      'Symbol': 'DPW',
      'price': 3.7,
      'avg': None,
      'PT1': 3.72,
      'PT2': 4.39,
      'PT3': 5.95,
      'SL': 3.65,
      'n_PTs': 3,
      'PTs_Qty': [.33, .33, .34],
      'Trader': 'ScaredShirtless#0001',
      'PTs': [5.84],
      'uQty': 3}
    
    pars = "BTO DPW @3.7 PT1: 3.72 PT2: 4.39 PT3:5.96 SL: 3.01"
    msg = "BTO DPW @3.7 PT1 3.72 SL: 3.01"
    
    al = AlertTrader()
    al.new_stock_alert(order, pars, msg)
    
    # order = {'action': 'BTO',
    #   'Symbol': 'PLTR',
    #   'price': 23,
    #   'avg': None,
    #   'PT1': None,
    #   'PT2': 6.39,
    #   'PT3': 6.95,
    #   'SL': 3.01,
    #   'n_PTs': 3,
    #   'PTs_Qty': [.33, .33, .34],
    #   'Trader': 'ScaredShirtless#0001',
    #   'PTs': [5.84],
    #   'uQty': 2}
    
    
    
    # pars = "BTO DPW @3.1 PT1 5.84 SL: 3.01"
    
    # msg = "BTO DPW @3.1 PT1 5.84 SL: 3.01"
    
    
       
    # order = {'action': 'STC',
    #  'Symbol': 'DPW',
    #  'price': 5.84,
    #  'qty': 2}
    
    # pars = "STC DPW @ 5.84"
    
    order = {'action': 'BTO',
     'Symbol': 'KMPH_031921C7.5',
     'ticker': 'KMPH',
     'price': 1.75,
     'expDate': '3/19/21',
     'strike': '7.5C',
     'avg': None,
     'PT1': None,
     'PT2': None,
     'PT3': None,
     'SL': None,
     'n_PTs': 0,
     'PTs_Qty': [1],
     'uQty': 3,
     'Trader': 'ScaredShirtless#0001'}
    
    # pars = 'BTO KMPH 3/19/21 7.5C @1.75 PT1:None, PT2:None, PT3:None, SL:None'
    # msg = "@everyone BTO **KMPH** 3/19/21 7.5c @ 1.75 (swing)"
    # order = {'action': 'STC',
    #  'Symbol': 'CURLF',
    #  'price': 24.05,
    #  'Trader': 'ScaredShirtless#0001',
    #  'PTs': [5.84],
    #  'Qty': 1}
    
    # pars = "STC CURLF @  24.0"
    msg  = "STC CURLF @  24.0"
