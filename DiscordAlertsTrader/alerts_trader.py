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
from datetime import datetime, date
import time
import threading
import queue
from colorama import Fore, Back

from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.message_parser import parse_exit_plan, set_exit_price_type, ordersymb_to_str


def find_last_trade(order, trades_log, open_only=True):
    trades_authr = trades_log["Trader"] == order["Trader"]
    trades_log = trades_log.loc[trades_authr]

    msk_ticker = trades_log["Symbol"].str.match(f"{order['Symbol']}$")

    # Order ticker without dates and strike
    if sum(msk_ticker) == 0 and order['asset'] == 'option':
        trades_log = trades_log[trades_log["Asset"] == "option"]
        trade_symb = trades_log["Symbol"].apply(lambda x: x.split("_")[0])

        msk_ticker = trade_symb.str.match(f"{order['Symbol']}$")

    if sum(msk_ticker) == 1:
        last_trade, = trades_log[msk_ticker].index.values
    # Either take open trade or last
    elif sum(msk_ticker) > 1:
        open_trade = trades_log.loc[msk_ticker, "isOpen"]
        if open_trade.sum() == 1:
            last_trade, = open_trade.index[open_trade==1]
        elif open_trade.sum() > 1:
            # raise ValueError ("Trade with more than one open position")
            last_trade = open_trade.index[open_trade==1][-1]
        elif open_trade.sum() == 0:
            last_trade = open_trade.index[-1]
    else:
        return None, 0

    isOpen = trades_log.loc[last_trade, 'isOpen']

    if open_only and isOpen == 0:
        return None, 0
    else:
        return last_trade, isOpen


class AlertsTrader():
    def __init__(self,
                 brokerage,
                 portfolio_fname=cfg['portfolio_names']['portfolio_fname'] ,
                 alerts_log_fname=cfg['portfolio_names']['alerts_log_fname'],
                 queue_prints=queue.Queue(maxsize=10),
                 update_portfolio=True,
                 send_alert_to_discord=cfg['discord'].getboolean('notify_alerts_to_discord')
                 ):
        self.bksession = brokerage
        self.portfolio_fname = portfolio_fname
        self.alerts_log_fname = alerts_log_fname
        self.queue_prints = queue_prints
        self.send_alert_to_discord = send_alert_to_discord
        self.discord_channel = None # discord channel object to post trade alerts, passed on_ready discord
        
        # load port and log
        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=cfg["col_names"]['portfolio'].split(",") )
            self.portfolio.to_csv(self.portfolio_fname, index=False)
        if op.exists(self.alerts_log_fname):
            self.alerts_log = pd.read_csv(self.alerts_log_fname)
        else:
            self.alerts_log = pd.DataFrame(columns=cfg["col_names"]['alerts_log'].split(","))
            self.alerts_log.to_csv(self.alerts_log_fname, index=False)

        self.update_portfolio = update_portfolio
        self.update_paused = False
        if update_portfolio:
            # first do a synch, then thread it
            self.update_orders()
            self.activate_trade_updater()

    def activate_trade_updater(self, refresh_rate=30):
        self.update_portfolio = True
        self.updater = threading.Thread(target=self.trade_updater, args=[refresh_rate], daemon=True)
        self.updater.start()
        self.queue_prints.put([f"Updating portfolio orders every {refresh_rate} secs", "", "green"])
        print(Back.GREEN + f"Updating portfolio orders every {refresh_rate} secs")

    def trade_updater_reset(self, refresh_rate=30):
        """ Will stop threding updater and restart.
        To avoid delays or parallel updatings. """
        self.update_portfolio = False
        time.sleep(refresh_rate)
        self.activate_trade_updater(refresh_rate)

    def _stop(self):
        "Lazy trick to stop updater threading"
        self.update_portfolio = False

    def trade_updater(self, refresh_rate=30):
        while self.update_portfolio is True:
            if self.update_paused is False:
                try:
                    self.update_orders()
                except Exception as ex:
                    str_msg = f"Error raised during port update, trying again later. Error: {ex}"
                    print(Back.RED + str_msg)
                    self.queue_prints.put([str_msg, "", "red"])
            if self.update_portfolio:
                time.sleep(refresh_rate)
        str_msg = "Closed portfolio updater"
        print(Back.GREEN + str_msg)
        self.queue_prints.put([str_msg, "", "green"])

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

    
    def disc_notifier(self,order_info):
        from discord_webhook import DiscordWebhook
        if not self.send_alert_to_discord:
            return
        
        if order_info['status'] not in ['FILLED', 'EXECUTED', 'INDIVIDUAL_FILLS']:
            print("order in notifier not filled")
            return
        
        action = "BTO" if order_info['orderLegCollection'][0]['instruction'].startswith("BUY") else "STC"
        symbol = ordersymb_to_str(order_info['orderLegCollection'][0]['instrument']['symbol'])
        msg = f"{action} {order_info['filledQuantity']} {symbol} @{order_info['price']}"
        
        if len(cfg['discord']['webhook']):
            webhook = DiscordWebhook(
                url=cfg['discord']['webhook'], 
                username=cfg['discord']['webhook_name'], 
                content=f'{msg.upper()}', 
                rate_limit_retry=True)
            response = webhook.execute()
            print("webhook sent, response:", response.json())
        
        if self.discord_channel is not None:
            self.discord_channel.send(msg.upper())
            print("discord channel message sent")

    def price_now(self, symbol, price_type="BTO", pflag=0):
        if price_type in ["BTO", "BTC"]:
            ptype = 'askPrice'
        else:
            ptype= 'bidPrice'
        try:
            resp = self.bksession.get_quotes([symbol])
            if resp is None or len(resp) == 0 or symbol not in resp.keys() or resp[symbol].get('description' ) == 'Symbol not found' :
                str_msg =  f"{symbol} not found during price quote"
                print (Back.RED + str_msg)
                self.queue_prints.put([str_msg, "", "red"])
                quote = -1
            else:
                quote = resp[symbol][ptype]
        except KeyError as e:
            str_msg= f"price_now error for symbol {symbol}: {e}.\n Try again later"
            print (Back.RED + str_msg)
            self.queue_prints.put([str_msg, "", "red"])
            quote = self.bksession.get_quotes(symbol)[symbol][ptype]
        if pflag:
            return quote
        else:
            return "CURRENTLY @%.2f"% quote

    def confirm_and_send(self, order, pars, order_funct):
            resp, order, ord_chngd = self.notify_alert(order, pars)
            if resp in ["yes", "y"]:
                try:
                    ord_resp, ord_id = self.bksession.send_order(order_funct(**order))
                except Exception as e:
                    str_msg = f"Error in order {e}"
                    print(Back.GREEN + str_msg)
                    self.queue_prints.put([str_msg, "", "red"])
                    return None, None, order, None
                
                if ord_resp is None:
                    raise("Something wrong with order response")

                str_msg = f"Sent order {pars}"
                print(Back.GREEN + str_msg)
                color = "green" if order['action'] == "BTO" else "yellow"
                self.queue_prints.put([str_msg, "", color])
                return ord_resp, ord_id, order, ord_chngd

            elif resp in ["no", "n"]:
                return None, None, order, None

    def notify_alert(self, order, pars):
        price_now = self.price_now
        symb = order['Symbol']
        ord_ori = order.copy()
        pars_ori = pars
        act = order['action']

        while True:
            # If symbol not found, quote val returned is -1
            if price_now(symb, act, 1 ) == -1:
                return "no", order, False

            current_price = price_now(symb, act, 1 )
            order["price_current"] = current_price
            pdiff = (current_price - ord_ori['price'])/ord_ori['price']
            pdiff = round(pdiff*100,1)

            question = f"{pars_ori} {price_now(symb, act)}"
            if cfg['order_configs'].getboolean('sell_current_price'):
                if pdiff < eval(cfg['order_configs']['max_price_diff'])[order["asset"]]:
                    order['price'] = price_now(symb, act, 1)
                    pars = self.order_to_pars(order)
                    question += f"\n new price: {pars}"
                else:
                    if cfg['order_configs'].getboolean('auto_trade') is True and order['action'] == "BTO":
                        str_msg = f"BTO alert price diff too high: {pdiff}% at {current_price}, keeping original price of {ord_ori['price']}"
                        print(Back.GREEN + str_msg)
                        self.queue_prints.put([str_msg, "", "green"])

            if cfg['order_configs'].getboolean('auto_trade') is True:
                if cfg['general'].getboolean('DO_BTO_TRADES') is False and order['action'] == "BTO":
                    str_msg = f"BTO not accepted by config options: DO_BTO_TRADES = False"
                    print(Back.GREEN + str_msg)
                    self.queue_prints.put([str_msg, "", "green"])
                    return "no", order, False
                elif order['action'] == "BTO":
                    price = order['price']
                    if price == 0:
                        str_msg = f"Order not accepted price is 0"
                        print(Back.GREEN + str_msg)
                        self.queue_prints.put([str_msg, "", "red"])
                        return "no", order, False
                    price = price*100 if order["asset"] == "option" else price
                    max_trade_val = float(cfg['order_configs']['max_trade_capital'])

                    if 'uQty' not in order.keys() or order['uQty'] is None:
                        if cfg['order_configs']['default_bto_qty'] == "buy_one":
                            order['uQty'] = 1                    
                        elif cfg['order_configs']['default_bto_qty'] == "trade_capital":
                            order['uQty'] =  int(max(round(float(cfg['order_configs']['trade_capital'])/price), 1))

                    if price * order['uQty'] > max_trade_val:
                        uQty_ori = order['uQty']
                        order['uQty'] =  int(max(max_trade_val//price, 1))
                        if price * order['uQty'] <= max_trade_val:
                            str_msg = f"BTO trade exeeded max_trade_capital of ${max_trade_val}, order quantity reduced to {order['uQty']} from {uQty_ori}"
                            print(Back.GREEN + str_msg)
                            self.queue_prints.put([str_msg, "", "green"])
                        else:
                            str_msg = f"cancelled BTO: trade exeeded max_trade_capital of ${max_trade_val}"
                            print(Back.RED + str_msg)
                            self.queue_prints.put([str_msg, "", "red"])
                            return "no", order, False
                return "yes", order, False

            # Manual trade 
            resp = input(Back.RED  + question + "\n Make trade? (y, n or (c)hange) \n").lower()

            if resp in [ "c", "change", "y", "yes"] and 'uQty' not in order.keys():
                order['uQty'] = int(input("Order qty not available." +
                                          f" How many units to buy? {price_now(symb, act)} \n"))

            if resp in [ "c", "change"]:
                new_order = order.copy()
                new_order['price'] = float(input(f"Change price @{order['price']}" +
                                        f" {price_now(symb, act)}? Leave blank if NO \n")
                                      or order['price'])

                if order['action'] == 'BTO':
                    PTs = [order[f'PT{i}'] for i in range(1,4)]
                    PTs = eval(input(f"Change PTs @{PTs} {price_now(symb, act)}? \
                                      Leave blank if NO, respond eg [1, 2, None] \n")
                                      or str(PTs))

                    new_n = len([i for i in PTs if i is not None ])
                    if new_n != order['n_PTs']:
                        new_order['n_PTs']= new_n
                        new_order['PTs_Qty'] = [round(1/new_n,2) for i in range(new_n)]
                        new_order['PTs_Qty'][-1] = new_order['PTs_Qty'][-1] + (1- sum(new_order['PTs_Qty']))

                    new_order["SL"] = (input(f"Change SL @{order['SL']} {price_now(symb, act)}?"+
                                             " Leave blank if NO \n")
                                       or order['SL'])

                    new_order["SL"] = eval(new_order["SL"]) if isinstance(new_order["SL"], str) else new_order["SL"]
                order = new_order
                pars = self.order_to_pars(order)
            else :
                break
        ord_chngd = ord_ori != order
        return resp, order, ord_chngd


    def close_open_exit_orders(self, open_trade, STCn=range(1,4)):
        # close STCn waiting orders
        position = self.portfolio.iloc[open_trade]
        if type(STCn) == int: STCn = [STCn]

        for i in STCn:
            if pd.isnull(position[ f"STC{i}-ordID"]):
                continue

            order_id =  int(position[ f"STC{i}-ordID"])
            ord_stat, _ = self.get_order_info(order_id)

            if ord_stat not in ["FILLED", "EXECUTED", 'CANCELED','CANCEL_REQUESTED','REJECTED', 'EXPIRED']:
                print(Back.GREEN + f"Cancelling {position['Symbol']} STC{i}")
                self.queue_prints.put([f"Cancelling {position['Symbol']} STC{i}", "", "green"])
                _ = self.bksession.cancel_order(order_id)

                self.portfolio.loc[open_trade, f"STC{i}-Status"] = np.nan
                self.portfolio.loc[open_trade, f"STC{i}-ordID"] = np.nan
                self.save_logs("port")


    def get_order_info(self, order_id):
        try:
             order_status, order_info = self.bksession.get_order_info(order_id)
             return order_status, order_info
        except Exception as ex:
            print(f"Caught Error in order info, skipping order info retr. Error: {ex}")
            self.queue_prints.put([f"Caught Error, skipping order info retr. Error: {ex}", "", "red"])
            return None, None


    ######################################################################
    # ALERT TRADER
    ######################################################################

    def new_trade_alert(self, order:dict, pars:str, msg):
        """ get order from ```parser_alerts``` """

        open_trade, isOpen = find_last_trade(order, self.portfolio)

        time_strf = "%Y-%m-%d %H:%M:%S.%f"
        date = datetime.now().strftime(time_strf)

        log_alert = {"Date": date,
                     "Symbol": order['Symbol'],
                     "Trader" : order['Trader'],
                     "parsed" : pars,
                     "msg": msg
                     }

        if order['action'] == "ExitUpdate" and isOpen:
            #TODO : REMOVE
            # Pause updater to avoid overlapping
            self.update_paused = True

            old_plan = self.portfolio.loc[open_trade, "exit_plan"]
            new_plan = parse_exit_plan(order)

            # check if asset if price stock or contract
            if self.portfolio.loc[open_trade, "Asset"] == "option":
                new_plan["price"] = self.portfolio.loc[open_trade, "Price"]
                sym_inf = self.portfolio.loc[open_trade, "Symbol"].split("_")[1]
                strike = re.split("C|P", sym_inf)[1]
                new_plan["strike"] = strike + "C"
                for i in range(1,4):
                    exit_price = new_plan.get(f"PT{i}")
                    if exit_price is not None:
                        new_plan[f"PT{i}"] = set_exit_price_type(exit_price, new_plan)
                    if new_plan.get("SL"):
                        new_plan[f"SL"] = set_exit_price_type(new_plan.get("SL"), new_plan)
                _ = [new_plan.pop(k) for k in ['price', 'strike']]

            # Update PT is already STCn
            istc = None
            for i in range(1,3):
                if not pd.isnull(self.portfolio.loc[open_trade, f"STC{i}-Alerted"]):
                    istc = i+1
            if istc is not None and any(["PT" in k for k in new_plan.keys()]):
                new_plan_c = new_plan.copy()
                for i in range(1,4):
                    if new_plan.get(f"PT{i}"):
                        del new_plan_c[f"PT{i}"]
                        new_plan_c[f"PT{istc}"] = new_plan[f"PT{i}"]
                        # Cancel orders previous plan if any
                        self.close_open_exit_orders(open_trade, istc)
                new_plan = new_plan

            renew_plan = eval(old_plan)
            if renew_plan is not None or renew_plan != {}:
                for k in new_plan.keys():
                    renew_plan[k] = new_plan[k]
            else:
                renew_plan = new_plan

            self.portfolio.loc[open_trade, "exit_plan"] = str(renew_plan)
            self.update_paused = False

            log_alert['action'] = "ExitUpdate"
            self.save_logs()

            symb = self.portfolio.loc[open_trade, "Symbol"]
            print(Back.GREEN + f"Updated {symb} exit plan from :{old_plan} to {renew_plan}")
            self.queue_prints.put([f"Updated {symb} exit plan from :{old_plan} to {renew_plan}", "", "green"])
            return

        if not isOpen and order["action"] == "BTO":
            alert_price = order['price']

            order_response, order_id, order, _ = self.confirm_and_send(order, pars, self.bksession.make_BTO_lim_order)
            self.save_logs("port")
            if order_response is None:  #Assume trade not accepted
                log_alert['action'] = "BTO-notAccepted"                
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                str_msg = "BTO not accepted by user, order response is none"
                print(Back.GREEN + str_msg)
                self.queue_prints.put([str_msg, "", "green"])
                return

            order_status, order_info = self.get_order_info(order_id)
            if order_status == 'REJECTED':                
                log_alert['action'] = "REJECTED"
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                print(Back.GREEN + "BTO REJECTED")
                self.queue_prints.put(["BTO REJECTED", "", "green"])
                return
            
            exit_plan = parse_exit_plan(order)
            new_trade = {"Date": date,
                         "Symbol": order['Symbol'],
                         'isOpen': 1,
                         'BTO-Status' : order_status,
                         "uQty": order_info['quantity'],
                         "Asset" : order["asset"],
                         "Type" : "BTO",
                         "Price" : order_info["price"],
                         "Price-Alert" : alert_price,
                         "Price-Current": order["price_current"],
                         "ordID" : order_id,
                         "exit_plan" : str(exit_plan),
                         "Trader" : order['Trader'],
                         "Risk" : order['risk'],
                         "SL_mental" : order.get("SL_mental")
                         }

            self.portfolio = pd.concat([self.portfolio, pd.DataFrame.from_records(new_trade, index=[0])], ignore_index=True)
            
            if order_status in ["FILLED", "EXECUTED"]:
                ot, _ = find_last_trade(order, self.portfolio)
                self.portfolio.loc[ot, "Price"] = order_info['price']
                self.portfolio.loc[ot, "filledQty"] = order_info['filledQuantity']
                self.disc_notifier(order_info)
            str_msg = f"BTO {order['Symbol']} executed @ {order_info['price']}. Status: {order_status}"
            print(Back.GREEN + str_msg)
            self.queue_prints.put([str_msg, "", "green"])
            
            #Log portfolio, trades_log
            log_alert['action'] = "BTO"
            log_alert["portfolio_idx"] = len(self.portfolio) - 1
            self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
            self.save_logs()

        elif order["action"] == "BTO" and order['avg'] is not None:
            # if PT in order: cancel previous and make_BTO_lim_rder
            # else : BTO
            alert_price = order['price']
            order_response, order_id, order, _ = self.confirm_and_send(order, pars,
                                                                       self.bksession.make_BTO_lim_order)
            self.save_logs("port")
            if order_response is None:  #Assume trade not accepted
                log_alert['action'] = "BTO-Avg-notAccepted"
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                print(Back.GREEN + "BTO avg not accepted by user")
                self.queue_prints.put(["BTO avg not accepted by user", "", "green"])
                return

            order_status, order_info = self.get_order_info(order_id)
            self.portfolio.loc[open_trade,'BTO-avg-Status'] = order_status
            self.portfolio.loc[open_trade,"ordID"] += f',{order_id}'

            if pd.isnull(self.portfolio.loc[open_trade, "Avged"]):
                self.portfolio.loc[open_trade, "Avged"] = 1
                self.portfolio.loc[open_trade, "Avged-prices-alert"] = alert_price
                self.portfolio.loc[open_trade, "Avged-prices"] = order_info["price"]
                self.portfolio.loc[open_trade, "Avged-uQty"] = order_info['quantity']

            else:
                self.portfolio.loc[open_trade, "Avged"] += 1
                al_pr = self.portfolio.loc[open_trade, "Avged-prices-alert"]
                av_pr = self.portfolio.loc[open_trade, "Avged-prices"]
                av_qt = self.portfolio.loc[open_trade, "Avged-uQty"]
                self.portfolio.loc[open_trade, "Avged-prices-alert"] = f"{al_pr},{alert_price}"
                self.portfolio.loc[open_trade, "Avged-prices"] = f"{av_pr},{order_info['price']}"
                self.portfolio.loc[open_trade, "Avged-uQty"] = f"{av_qt},{order_info['quantity']}"

            avg = self.portfolio.loc[open_trade, "Avged"]

            self.portfolio.loc[open_trade, "uQty"] += order_info['quantity']
            if  order_status in ["FILLED", "EXECUTED"]:
                self.portfolio.loc[open_trade, "filledQty"] += order_info['filledQuantity']
                self.disc_notifier(order_info)
                self.close_open_exit_orders(open_trade)
            str_msg =  f"BTO {avg} th AVG, {order['Symbol']} executed @{order_info['price']}. Status: {order_status}"
            print(Back.GREEN + str_msg)
            self.queue_prints.put([str_msg, "", "green"])

            #Log portfolio, trades_log
            log_alert['action'] = "BTO-avg"
            log_alert["portfolio_idx"] = len(self.portfolio) - 1
            self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
            self.save_logs()

        elif order["action"] == "BTO":
            str_act = "Repeated BTO"
            log_alert['action'] = "BTO-Null-Repeated"
            self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
            self.save_logs(["alert"])
            print(Back.RED + str_act)
            self.queue_prints.put([str_act, "", "red"])

        elif order["action"] == "STC" and isOpen == 0:
            open_trade, _ = find_last_trade(order, self.portfolio, open_only=False)
            if open_trade is None:
                log_alert['action'] = str_msg = f"STC-alerted without open position"
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs()
                if cfg['general'].getboolean('DO_BTO_TRADES'):
                    print(Back.GREEN + str_msg)
                    self.queue_prints.put([str_msg, "", "green"])
                return

            position = self.portfolio.iloc[open_trade]
            # Check if closed position was not alerted
            for i in range(1,4):
                STC = f"STC{i}"
                if pd.isnull(position[f"{STC}-Alerted"]):
                    self.portfolio.loc[open_trade, f"{STC}-Alerted"] = 1
                    # If alerted and already sold
                    if not pd.isnull(position[ f"{STC}-Price"]):
                        print(Back.RED + "Position already closed")
                        self.queue_prints.put(["Position already closed", "", "red"])
                        log_alert['action'] = f"{STC}-alerterdAfterClose"
                        log_alert["portfolio_idx"] = open_trade
                        self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                        self.save_logs()
                    return

            str_act = "STC without BTO, maybe alredy sold"
            log_alert['action'] = "STC-Null-notOpen"
            self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
            self.save_logs(["alert"])
            print(Back.RED + str_act)
            self.queue_prints.put([str_act, "", "red"])

        elif order["action"] == "STC":
            position = self.portfolio.iloc[open_trade]
            if order.get("amnt_left"):
                order, changed = amnt_left(order, position)
                print(Back.GREEN + f"Based on alerted amnt left, Updated order: " +
                      f"xQty: {order['xQty']} and uQty: {order['uQty']}")
                self.queue_prints.put([f"Based on alerted amnt left, Updated order: " +
                      f"xQty: {order['xQty']} and uQty: {order['uQty']}", "", "green"])

            # check if position already alerted and closed
            for i in range(1,4):
                STC = f"STC{i}"

                # If not alerted, mark it
                if pd.isnull(position[f"{STC}-Alerted"]):
                    self.portfolio.loc[open_trade, f"{STC}-Alerted"] = 1 
                    self.portfolio.loc[open_trade, STC + "-Price-Alerted"] = order["price"]
                    # If alerted and already sold
                    if not pd.isnull(position[ f"{STC}-Price"]):
                        print(Back.GREEN + "Already sold")
                        self.queue_prints.put(["Already sold", "", "green"])

                        log_alert['action'] = f"{STC}-DoneBefore"
                        log_alert["portfolio_idx"] = open_trade
                        self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                        self.save_logs(["alert"])

                        if order['xQty'] != 1:  # if partial and sold, leave
                            return
                    break

            else:
                str_STC = "How many STC already?"
                print (Back.RED + str_STC)
                self.queue_prints.put([str_STC, "", "red"])
                log_alert['action'] = "STC-TooMany"
                log_alert["portfolio_idx"] = open_trade
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                return

            qty_bought = position["filledQty"]

            if position["BTO-Status"] in ["CANCELED", "REJECTED", "EXPIRED", "CANCEL_REQUESTED"]:
                log_alert['action'] = "Trade-already cancelled"
                log_alert["portfolio_idx"] = open_trade
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                return

            # Close position of STC All or STC SL
            if qty_bought == 0 and order['xQty'] == 1:

                order_id = position['ordID']
                _ = self.bksession.cancel_order(order_id)

                self.portfolio.loc[open_trade, "isOpen"] = 0

                order_status, _ =  self.get_order_info(order_id)
                self.portfolio.loc[open_trade, "BTO-Status"] = order_status

                print(Back.GREEN + f"Order Cancelled {order['Symbol']}, closed before fill")
                self.queue_prints.put([f"Order Cancelled {order['Symbol']}, closed before fill", "", "green"])

                log_alert['action'] = "STC-ClosedBeforeFill"
                log_alert["portfolio_idx"] = open_trade
                self.save_logs()
                # self.activate_trade_updater()
                return
            # Set STC as exit plan
            elif qty_bought == 0:
                exit_plan = eval(self.portfolio.loc[open_trade, "exit_plan"])
                exit_plan[f"PT{STC[-1]}"] = order["price"]
                self.portfolio.loc[open_trade, "exit_plan"] = str(exit_plan)
                str_msg = f"Exit Plan {order['Symbol']} updated, with PT{STC[-1]}: {order['price']}"
                print(Back.GREEN + str_msg)
                self.queue_prints.put([str_msg,"", "green"])
                log_alert['action'] = "STC-partial-BeforeFill-ExUp"
                log_alert["portfolio_idx"] = open_trade
                return

            qty_sold = np.nansum([position[f"STC{i}-uQty"] for i in range(1,4)])
            if position["uQty"] - qty_sold == 0:
                self.portfolio.loc[open_trade, "isOpen"] = 0
                print(Back.GREEN + "Already sold")
                self.queue_prints.put(["Already sold", "", "green"])

                log_alert['action'] = f"{STC}-DoneBefore"
                log_alert["portfolio_idx"] = open_trade
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                return

            # Sell all and close waiting stc orders
            if order['xQty'] == 1:                
                # Stop updater to avoid overlapping
                self.update_paused = True
                # Sell all and close waiting stc orders
                self.close_open_exit_orders(open_trade)
                
                # if no uQty get all remaining
                if order['uQty'] is None:
                    position = self.portfolio.iloc[open_trade]
                    order['uQty'] = int(position["uQty"]) - qty_sold

            elif order['xQty'] < 1:  # portion
                # Stop updater to avoid overlapping
                self.update_paused = True
                self.close_open_exit_orders(open_trade)
                order['uQty'] = round(max(qty_bought * order['xQty'], 1))

            if order['uQty'] + qty_sold > qty_bought:
                order['uQty'] = int(qty_bought - qty_sold)
                str_msg = f"Order {order['Symbol']} Qty exceeded, changed to {order['uQty']}"
                print(Back.RED + Fore.BLACK + str_msg)
                self.queue_prints.put([str_msg, "", "red"])

            order_response, order_id, order, _ = self.confirm_and_send(order, pars, self.bksession.make_STC_lim)
            log_alert["portfolio_idx"] = open_trade

            if order_response is None:  # Assume trade rejected by user
                log_alert['action'] = "STC-notAccepted"
                self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
                self.save_logs(["alert"])
                print(Back.GREEN + "STC not accepted by user, order response null")
                self.queue_prints.put(["STC not accepted by user, order response null", "", "green"])
                self.update_paused = False
                return

            order_status, order_info = self.get_order_info(order_id)
            self.portfolio.loc[open_trade, STC + "-ordID"] = order_id
            self.portfolio.loc[open_trade, STC + "-Price-Current"] = order["price_current"]

            # Check if STC price changed
            if order_status in ["FILLED", 'EXECUTED', 'INDIVIDUAL_FILLS']:
                self.disc_notifier(order_info)
                self.log_filled_STC(order_id, open_trade, STC)
            else:
                str_STC = f"Submitted: {STC} {order['Symbol']} @{order['price']} Qty:{order['uQty']} ({order['xQty']})"
                print(Back.GREEN + str_STC)
                self.queue_prints.put([str_STC, "", "green"])

            #Log trades_log
            log_alert['action'] = "STC-partial" if order['xQty']<1 else "STC-ALL"
            self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)
            self.save_logs()

            self.update_paused = False


    def log_filled_STC(self, order_id, open_trade, STC):

        order_status, order_info = self.get_order_info(order_id)
        sold_unts = order_info['orderLegCollection'][0]['quantity']

        if 'price' in order_info.keys():
            stc_price = order_info['price']
        elif 'stopPrice' in order_info.keys():
            stc_price = order_info['stopPrice']
        elif "orderActivityCollection" in order_info.keys():
            prics = []
            for ind in order_info["orderActivityCollection"]:
                prics.append([ind['quantity'], ind['executionLegs'][0]['price']])
                n_tot= sum([i[0] for i in prics])
            stc_price =  sum([i[0]*i[1] for i in prics])/ n_tot

        bto_price = self.portfolio.loc[open_trade, "Price"]
        bto_price_alert = self.portfolio.loc[open_trade, "Price-Alert"]
        bto_price_current = self.portfolio.loc[open_trade, "Price-Current"]
        stc_PnL = float((stc_price - bto_price)/bto_price) *100

        xQty = sold_unts/ self.portfolio.loc[open_trade, "uQty"]

        date = order_info["closeTime"]
        #Log portfolio
        self.portfolio.loc[open_trade, STC + "-Status"] = order_status
        self.portfolio.loc[open_trade, STC + "-Price"] = stc_price
        self.portfolio.loc[open_trade, STC + "-Date"] = date
        self.portfolio.loc[open_trade, STC + "-xQty"] = xQty
        self.portfolio.loc[open_trade, STC + "-uQty"] = sold_unts
        self.portfolio.loc[open_trade, STC + "-PnL"] = stc_PnL
        self.portfolio.loc[open_trade, STC + "-ordID"] = order_id

        trade = self.portfolio.loc[open_trade]
        sold_tot = np.nansum([trade[f"STC{i}-uQty"] for i in range(1,4)])
        stc_PnL_all = np.nansum([trade[f"STC{i}-PnL"]*trade[f"STC{i}-uQty"] for i in range(1,4)])/sold_tot
        self.portfolio.loc[open_trade, "PnL"] = stc_PnL_all
        stc_PnL_all_alert =  np.nansum([(float((trade[f"STC{i}-Price-Alerted"] - bto_price_alert)/bto_price_alert) *100) * trade[f"STC{i}-uQty"] for i in range(1,4)])/sold_tot
        stc_PnL_all_curr = np.nansum([(float((trade[f"STC{i}-Price-Current"] - bto_price_current)/bto_price_current) *100) * trade[f"STC{i}-uQty"] for i in range(1,4)])/sold_tot
        self.portfolio.loc[open_trade, "PnL-Alert"] = stc_PnL_all_alert
        self.portfolio.loc[open_trade, "PnL-Current"] = stc_PnL_all_curr
        
        mutipl = 1 if trade['Asset'] == "option" else .01  # pnl already in %
        self.portfolio.loc[open_trade, "$PnL"] =  stc_PnL_all* bto_price *mutipl*sold_tot
        self.portfolio.loc[open_trade, "$PnL-Alert"] =  stc_PnL_all_alert* bto_price_alert *mutipl*sold_tot
        self.portfolio.loc[open_trade, "$PnL-Current"] =  stc_PnL_all_curr* bto_price_current *mutipl*sold_tot
        
        symb = self.portfolio.loc[open_trade, 'Symbol']

        sold_Qty =  self.portfolio.loc[open_trade, [f"STC{i}-uQty" for i in range(1,4)]].sum()

        str_STC = f"{STC} {symb} @{stc_price} Qty:" + \
            f"{sold_unts}({int(xQty*100)}%), for {stc_PnL:.2f}%"

        if sold_Qty == self.portfolio.loc[open_trade, "uQty"]:
            str_STC += " (Closed)"
            self.portfolio.loc[open_trade, "isOpen"] = 0

        print (Back.GREEN + f"Filled: {str_STC}")
        self.queue_prints.put([f"Filled: {str_STC}","", "green"])
        self.save_logs()


    def update_orders(self):

        for i in range(len(self.portfolio)):
            self.close_expired(i)
            trade = self.portfolio.iloc[i]
            redo_orders = False

            if trade["isOpen"] == 0:
                continue

            if trade["BTO-Status"]  in ["QUEUED", "WORKING", 'OPEN']:
                order_status, order_info = self.get_order_info(trade['ordID'])

                # Check if number filled Qty changed
                qty_fill = order_info['filledQuantity']
                qty_fill_old = self.portfolio.loc[i, "filledQty"]
                # If so, redo orders
                if not (pd.isnull(qty_fill_old) or qty_fill_old == 0) and \
                    qty_fill_old != qty_fill:
                    redo_orders = True
                
                if order_status in ["FILLED", "EXECUTED"]:
                    self.portfolio.loc[i, "Price"] = order_info['price']
                    self.disc_notifier(order_info)
                    str_msg = f"BTO {order_info['Symbol']} executed @ {order_info['price']}. Status: {order_status}"
                    print(Back.GREEN + str_msg)
                    self.queue_prints.put([str_msg, "", "green"])
                self.portfolio.loc[i, "filledQty"] = order_info['filledQuantity']
                self.portfolio.loc[i, "BTO-Status"] = order_info['status']

                trade = self.portfolio.iloc[i]
                self.save_logs("port")

            if pd.isnull(trade["filledQty"]) or trade["filledQty"] == 0:
                continue

            if trade.get("BTO-avg-Status") in ["QUEUED", "WORKING", 'OPEN']:
                ordID = trade['ordID'].split(",")[-1]
                order_status, order_info = self.get_order_info(ordID)
                if order_info['status'] in ["FILLED", "EXECUTED"]:
                    self.portfolio.loc[i, "BTO-avg-Status"] = order_info['status']
                    self.portfolio.loc[i, "filledQty"] += order_info['filledQuantity']
                    redo_orders = True
                    trade = self.portfolio.iloc[i]
                    self.save_logs("port")
                    
                    str_msg = f"BTO-avg {order_info['Symbol']} executed @ {order_info['price']}. Status: {order_status}"
                    print(Back.GREEN + str_msg)
                    self.queue_prints.put([str_msg, "", "green"])
                    self.disc_notifier(order_info)

            if redo_orders:
                self.close_open_exit_orders(i)

            exit_plan = eval(trade["exit_plan"])
            if  exit_plan != {}:                
                if any([isinstance(e, str) and "%" not in e for e in exit_plan.values()]) and trade['Asset'] == 'option':
                    self.check_opt_stock_price(i, exit_plan, "STC")
                else:
                    self.make_exit_orders(i, exit_plan)

            # Go over STC orders and check status
            for ii in range(1, 4):
                STC = f"STC{ii}"
                trade = self.portfolio.iloc[i]
                STC_ordID = trade[STC+"-ordID"]

                if pd.isnull(STC_ordID):
                    continue

                # Get status exit orders
                STC_ordID = int(float(STC_ordID))  # Might be read as a float

                order_status, order_info =  self.get_order_info(STC_ordID)

                if order_status == 'CANCELED':
                    # Try next order number. OCO gets chancelled when one of child ordergets filled.
                    # This is for TDA OCO
                    order_status, _ =  self.get_order_info(STC_ordID + 1)
                    if order_status == 'FILLED':
                        STC_ordID = STC_ordID + 1
                        self.portfolio.loc[i, STC + "-ordID"] =  STC_ordID
                    else: # try the other one
                        order_status, _ =  self.get_order_info(STC_ordID + 2)
                        if order_status == 'FILLED':
                            STC_ordID = STC_ordID + 2
                            self.portfolio.loc[i, STC + "-ordID"] =  STC_ordID

                self.portfolio.loc[i, STC+"-Status"] = order_status
                trade = self.portfolio.iloc[i]

                if order_status in ["FILLED", "EXECUTED"] and np.isnan(trade[STC+"-xQty"]):
                    self.log_filled_STC(STC_ordID, i, STC)                    
                    self.disc_notifier(order_info)

        self.save_logs("port")


    def check_opt_stock_price(self, open_trade, exit_plan, act="STC"):
        "Option exits in stock price"
        i = open_trade
        exit_plan_ori = exit_plan.copy()
        trade = self.portfolio.iloc[i]

        ord_inf = trade['Symbol'].split("_")
        if len(ord_inf) != 2: return
        symb_stock = ord_inf[0]

        quote = self.price_now(symb_stock, act, 1)
        quote_opt = self.price_now(trade['Symbol'], act, 1)

        for v, pt in exit_plan.items():
            if not isinstance(pt, str): continue
            if v[:2] == "PT" and float(pt) <= quote:
                exit_plan[v] = quote_opt
                # Add another exit plan for x2
                STCn = int(v[2])
                if STCn < 3 and exit_plan[f"PT{STCn+1}"] is None:
                    exit_plan[f"PT{STCn+1}"] = quote_opt * 2
            elif v[:2] == "SL" and "%" not in pt and float(pt) >= quote:
                 exit_plan[v] = quote

        if exit_plan_ori != exit_plan:
            self.portfolio.loc[i, "exit_plan"] = str(exit_plan)
            self.save_logs("port")
            self.make_exit_orders(i, exit_plan)


    def SL_below_market(self, order, new_SL_ratio=.95):
        SL = order.get("SL")
        price_now = self.price_now(order["Symbol"], "STC", 1)

        if SL > price_now:
            new_SL = round(price_now * new_SL_ratio, 2)
            print(Back.RED + f"{order['Symbol']} SL below bid price, changed from {SL} to {new_SL}")
            self.queue_prints.put([f"{order['Symbol']} SL below bid price, changed from {SL} to {new_SL}",
                            "", "red"])
            order["SL"] = new_SL
        return order


    def make_exit_orders(self, open_trade, exit_plan):
        i = open_trade
        trade = self.portfolio.iloc[i]

        # Calculate x/uQty:
        uQty_bought = trade['filledQty']
        nPTs =  len([i for i in range(1,4) if exit_plan[f"PT{i}"] is not None])
        if nPTs != 0:
            uQty = [round(uQty_bought/nPTs)]*nPTs
            uQty[-1] = int(uQty_bought - sum(uQty[:-1]))

            xQty = [round(1/nPTs, 1)]*nPTs
            xQty[-1] = 1 - sum(xQty[:-1])

        # Go over exit plans and make orders
        order = {'Symbol': trade['Symbol']}
        for ii in range(1, nPTs+1):
            STC = f"STC{ii}"           

            # If Option add strike field
            ord_inf = trade['Symbol'].split("_")
            if len(ord_inf) == 2:
                opt_type = "C" if "C" in ord_inf[1] else "P"
                strike = str(re.split('C|P', ord_inf[1])[1]) + opt_type
                order['strike'] = strike

            STC_ordID = trade[STC+"-ordID"]
            if not pd.isnull(STC_ordID):
                # Adjust if necessary uQty based on remaining shares
                if nPTs < 2:
                    continue
                ord_stat, ord_inf = self.get_order_info(int(STC_ordID))
                iord_qty = ord_inf.get('quantity')
                if iord_qty is None:
                    iord_qty = ord_inf['childOrderStrategies'][0]['quantity']
                if uQty[ii - 1] != iord_qty:
                    uQty[ii - 1] = int(iord_qty)
                    uleft = uQty_bought - sum(uQty[:ii])
                    if uleft == 0:
                        break
                    nPts = len(uQty) - ii
                    if nPts !=0:
                        uQty = uQty[:ii] + [round(uleft/nPts)]*nPts
                        uQty[-1] = int(uQty_bought - sum(uQty[:-1]))
                    else:
                        uQty[-1] = int(uleft)
                    xQty = [round(u/uQty_bought,1) for u in uQty]

            else:
                SL = exit_plan["SL"]
                # Check if exit prices are strings (stock price for option)
                if isinstance(SL, str) and "%" not in SL: SL = None
                if isinstance(exit_plan[f"PT{ii}"], str): exit_plan[f"PT{ii}"] = None

                ord_func = None
                # Lim and Sl OCO order
                if exit_plan[f"PT{ii}"] is not None and SL is not None:
                    # Lim_SL order
                    ord_func = self.bksession.make_Lim_SL_order
                    order["PT"] = exit_plan[f"PT{ii}"]
                    order["SL"] = exit_plan["SL"]
                    order['uQty'] = uQty[ii - 1]
                    order['xQty'] = xQty[ii - 1]

                # Lim order
                elif exit_plan[f"PT{ii}"] is not None and SL is None:
                    ord_func = self.bksession.make_STC_lim
                    order["price"] = exit_plan[f"PT{ii}"]
                    order['uQty'] = uQty[ii - 1]
                    order['xQty'] = xQty[ii - 1]

                # SL order
                elif ii == 1 and SL is not None:
                    if "%" in SL:
                        ord_func = self.bksession.make_STC_SL_trailstop
                        order = self.calculate_stoploss(order, trade, exit_plan["SL"])
                    else:
                        ord_func =self.bksession.make_STC_SL
                        order["price"] = exit_plan["SL"]
                    
                    order['uQty'] = int(trade['uQty'])
                    order['xQty'] = 1

                elif ii > 1 and SL is not None:
                    break

                else:
                    raise("Case not caught")

                # Check that is below current price
                if order.get("SL") is not None and isinstance(order.get("SL"), (int, float)):
                    order = self.SL_below_market(order)

                if ord_func is not None and order['uQty'] > 0:
                    _, STC_ordID = self.bksession.send_order(ord_func(**order))
                    if order.get("price"):
                        str_prt = f"{STC} {order['Symbol']} @{order['price']}(Qty:{order['uQty']}) sent during order update"
                    else:
                        str_prt = f"{STC} {order['Symbol']} @{order.get('PT')}/{order.get('SL')} (Qty:{order['uQty']}) sent during order update"
                    print (Back.GREEN + str_prt)
                    self.queue_prints.put([str_prt,"", "green"])
                    self.portfolio.loc[i, STC+"-ordID"] = STC_ordID
                    trade = self.portfolio.iloc[i]
                    self.save_logs("port")
                else:
                    break
        # no PTs but trailing stop
        if nPTs == 0 and exit_plan["SL"] is not None and "%" in exit_plan["SL"] and pd.isnull(trade["STC1-ordID"]):            
            order = self.calculate_stoploss(order, trade, exit_plan["SL"])
            order['uQty'] = int(trade['uQty'])
            order['xQty'] = 1
            _, STC_ordID = self.bksession.send_order(self.bksession.make_STC_SL_trailstop(**order))
            str_prt = f"STC1 {order['Symbol']} Trailing stop of {exit_plan['SL']} constant $ sent during order update"            
            print(Back.GREEN + str_prt)
            self.queue_prints.put([str_prt,"", "green"])
            self.portfolio.loc[i, "STC1-ordID"] = STC_ordID
            trade = self.portfolio.iloc[i]
            self.save_logs("port")


    def close_expired(self, open_trade):
        i = open_trade
        trade = self.portfolio.iloc[i]
        if trade["Asset"] != "option" or trade["isOpen"] == 0:
            return
        optdate = option_date(trade['Symbol'])
        if optdate.date() < date.today():
            expdate = date.today().strftime("%Y-%m-%dT%H:%M:%S+0000")
            usold = np.nansum([trade[f"STC{i}-uQty"] for i in range(1,4)])
            for stci in range(1,4):
                if pd.isnull(trade[f"STC{stci}-uQty"]):
                    STC = f"STC{stci}"
                    break

            #Log portfolio
            self.portfolio.loc[open_trade, STC + "-Status"] = 'EXPIRED'
            self.portfolio.loc[open_trade, STC + "-Price"] = 0
            self.portfolio.loc[open_trade, STC + "-Date"] = expdate
            self.portfolio.loc[open_trade, STC + "-xQty"] = 1
            self.portfolio.loc[open_trade, STC + "-uQty"] = trade['filledQty'] - usold
            self.portfolio.loc[open_trade, STC + "-PnL"] = -100
            self.portfolio.loc[open_trade, "isOpen"] = 0
            
            bto_price = self.portfolio.loc[open_trade, "Price"]
            bto_price_alert = self.portfolio.loc[open_trade, "Price-Alert"]
            bto_price_current = self.portfolio.loc[open_trade, "Price-Current"]
            
            trade = self.portfolio.loc[open_trade]
            sold_tot = np.nansum([trade[f"STC{i}-uQty"] for i in range(1,4)])
            stc_PnL_all = np.nansum([trade[f"STC{i}-PnL"]*trade[f"STC{i}-uQty"] for i in range(1,4)])/sold_tot
            self.portfolio.loc[open_trade, "PnL"] = stc_PnL_all
            stc_PnL_all_alert =  np.nansum([(float((trade[f"STC{i}-Price-Alerted"] - bto_price_alert)/bto_price_alert) *100) * trade[f"STC{i}-uQty"] for i in range(1,4)])/sold_tot
            stc_PnL_all_curr = np.nansum([(float((trade[f"STC{i}-Price-Current"] - bto_price_current)/bto_price_current) *100) * trade[f"STC{i}-uQty"] for i in range(1,4)])/sold_tot
            self.portfolio.loc[open_trade, "PnL-Alert"] = stc_PnL_all_alert
            self.portfolio.loc[open_trade, "PnL-Current"] = stc_PnL_all_curr
            
            mutipl = 1 if trade['Asset'] == "option" else .01  # pnl already in %
            self.portfolio.loc[open_trade, "$PnL"] =  stc_PnL_all* bto_price *mutipl*sold_tot
            self.portfolio.loc[open_trade, "$PnL-Alert"] =  stc_PnL_all_alert* bto_price_alert *mutipl*sold_tot
            self.portfolio.loc[open_trade, "$PnL-Current"] =  stc_PnL_all_curr* bto_price_current *mutipl*sold_tot
        
            str_prt = f"{trade['Symbol']} option expired -100% uQty: {trade['filledQty']}"
            print(Back.GREEN + str_prt)
            self.queue_prints.put([str_prt,"", "green"])
            self.save_logs("port")

    def calculate_stoploss(self, order, trade, SL:str):
        "Calculate stop loss price with increment, SL: e.g. '40%"        
        stop_loss_price =  trade['Price']*float(SL.replace("%", ""))/100        
        if trade['Symbol'] in ["SPY", "QQQ", "IWM"] and self.bksession.name == 'etrade':
            increment = 0.01  # ETFs trade in penny increments
        else:
            if trade['Price'] < 3.0:
                increment = 0.05
            else:
                increment = 0.10
        rounded_stop_loss_price = round(stop_loss_price / increment) * increment
        order["trail_stop_const"] = rounded_stop_loss_price
        return order
        
def option_date(opt_symbol):
    sym_inf = opt_symbol.split("_")[1]
    opt_date = re.split("C|P", sym_inf)[0]
    return datetime.strptime(opt_date, "%m%d%y")

def amnt_left(order, position):
    # Calculate amnt to sell based on alerted left amount
    available = position["uQty"]
    if order.get("amnt_left"):
        left = order["amnt_left"]
        if left == "few":
            order['xQty'] =  1 - .2
            order['uQty'] = max(round(available * order['xQty']), 1)
        elif left > .99:  # unit left
            order['uQty'] = max(available - left, 1)
            order['xQty'] = (available - order['uQty'])/available
        elif left < .99:  # percentage left
            order['xQty'] = 1 - left
            order['uQty'] = max(round(available * order['xQty']), 1)
        else:
            raise ValueError
        return order, True
    else:
        return order, False


if __name__ == "__main__":
    from DiscordAlertsTrader.brokerages import get_brokerage
    
    bksession = get_brokerage()
    at = AlertsTrader(bksession)
