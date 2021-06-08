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
import config as cfg
import threading
from pprint import pprint
from td.exceptions import GeneralError, ServerError
from place_order import (get_TDsession, make_BTO_lim_order, send_order,
                         make_STC_lim,
                         make_Lim_SL_order, make_STC_SL)
# import dateutil.parser.parse as date_parser
from colorama import Fore, Back, Style
from message_parser import parse_exit_plan, set_exit_price_type
import queue

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


class AlertTrader():

    def __init__(self,
                 portfolio_fname=cfg.portfolio_fname,
                 alerts_log_fname=cfg.alerts_log_fname,
                 queue_prints=queue.Queue(maxsize=10),
                 test_TDsession=None, update_portfolio=True):

        self.portfolio_fname = portfolio_fname
        self.alerts_log_fname = alerts_log_fname
        self.queue_prints = queue_prints
        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=[
                "Date", "Symbol", "Trader", "isOpen", "BTO-Status", "Asset", "Type", "Price", "Alert-Price",
                "uQty", "filledQty", "Avged", "Avged-prices" "exit_plan", "ordID", "Risk", "SL_mental"] + [
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

        self.update_portfolio = update_portfolio
        self.update_paused = False
        if update_portfolio:
            # first do a synch process, then thread it
            self.update_orders()
            self.activate_trade_updater()


    def activate_trade_updater(self, refresh_rate=30):
        self.update_portfolio = True
        self.updater = threading.Thread(target=self.trade_updater, args=[refresh_rate])
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
                except: # (GeneralError, ConnectionError, KeyError):
                    print(Back.RED + "General error raised, trying again")
                    self.queue_prints.put(["General error raised, trying again", "", "red"])
            time.sleep(refresh_rate)
        print(Back.GREEN + "Closing portfolio updater")
        self.queue_prints.put(["Closed portfolio updater", "", "green"])

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


    def price_now(self, Symbol, price_type="BTO", pflag=0):
        if price_type in ["BTO", "BTC"]:
            ptype = 'askPrice'
        else:
            ptype= 'bidPrice'
        try:
            resp = self.TDsession.get_quotes(
                instruments=[Symbol])
            if resp[Symbol].get('description' ) == 'Symbol not found':
                print (Back.RED + f"{Symbol} not found during price quote")
                self.queue_prints.put([f"{Symbol} not found during price quote", "", "red"])
                quote = -1
            else:
                quote = resp[Symbol][ptype]
        except KeyError as e:
                print (Back.RED + f"price_now ERROR: {e}.\n Trying again")
                self.queue_prints.put([f"price_now ERROR: {e}.\n Trying again", "", "red"])
                quote = self.TDsession.get_quotes(
                instruments=[Symbol])[Symbol][ptype]
        if pflag:
            return quote
        else:
            return "CURRENTLY @%.2f"% quote

    def confirm_and_send(self, order, pars, order_funct):
            resp, order, ord_chngd = self.notify_alert(order, pars)
            if resp in ["yes", "y"]:

                ord_resp, ord_id = send_order(order_funct(**order), self.TDsession)
                if ord_resp is None:
                    raise("Something wrong with order response")

                print(Back.GREEN + f"Sent order {pars}")
                self.queue_prints.put([f"Sent order {pars}", "", "green"])
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
            question = f"{pars_ori} {price_now(symb, act)}"
            # If symbol not found, quote val returned is -1
            if price_now(symb, act, 1 ) == -1:
                return "no", order, False

            pdiff = (price_now(symb, act, 1 ) - ord_ori['price'])/ord_ori['price']
            pdiff = round(pdiff*100,1)

            if cfg.sell_current_price:
                if pdiff < cfg.max_price_diff[order["asset"]]:
                    order['price'] = price_now(symb, act, 1)
                    pars = self.order_to_pars(order)
                    question += f"\n new price: {pars}"
                else:
                    if cfg.auto_trade is True and order['action'] == "BTO":

                        print(Back.GREEN + f"BTO alert price diff too high: {pdiff}")
                        self.queue_prints.put([f"BTO alert price diff too high: {pdiff}, keeping original price", "", "green"])
                        # return "no", order, False

            if cfg.auto_trade is True:
                if cfg.do_BTO is False and order['action'] == "BTO":
                    print(Back.GREEN + f"BTO not accepted by config options")
                    self.queue_prints.put([f"BTO not accepted by config options", "", "green"])
                    return "no", order, False

                if 'uQty' not in order.keys():
                    price = order['price']
                    price = price*100 if order["asset"] == "option" else price
                    order['uQty'] =  max(round(cfg.trade_capital/price), 1)

                    if price * order['uQty'] > cfg.trade_capital_max:
                        print(Back.GREEN + f"BTO trade exeedes trade_capital_max of ${cfg.trade_capital_max}")
                        self.queue_prints.put([f"BTO trade exeedes trade_capital_max of ${cfg.trade_capital_max}", "", "green"])
                        return "no", order, False
                return "yes", order, False


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
                                      Leave blank if NO, respnd eg [1, 2, None] \n")
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

            if ord_stat not in ["FILLED", 'CANCELED', 'REJECTED']:
                print(Back.GREEN + f"Cancelling {position['Symbol']} STC{i}")
                self.queue_prints.put([f"Cancelling {position['Symbol']} STC{i}", "", "green"])
                _ = self.TDsession.cancel_order(self.TDsession.accountId, order_id)

                self.portfolio.loc[open_trade, f"STC{i}-Status"] = np.nan
                self.portfolio.loc[open_trade, f"STC{i}-ordID"] = np.nan
                self.save_logs("port")


    def get_order_info(self, order_id):
        try:
            order_info = self.TDsession.get_orders(account=self.accountId,
                                              order_id=order_id)
        except:
            print("Caught Error, skipping order info retr.")
            self.queue_prints.put(["Caught TD Server Error, skipping order info retr.", "", "red"])
            return None, None

        if order_info['orderStrategyType'] == "OCO":
            order_status = [
                order_info['childOrderStrategies'][0]['status'],
                order_info['childOrderStrategies'][1]['status']]
            if not order_status[0]==order_status[1]:
                print("OCO order status are different: ",
                      f"{order_status[0]} vs {order_status[1]}")
            order_status = order_status[0]
        elif order_info['orderStrategyType'] == 'SINGLE':
            order_status = order_info['status']
        else:
            raise("Not sure type order. Check")

        return order_status, order_info


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

            order_response, order_id, order, ord_chngd = self.confirm_and_send(order, pars,
                                                       make_BTO_lim_order)
            self.save_logs("port")
            if order_response is None:  #Assume trade not accepted
                log_alert['action'] = "BTO-notAccepted"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                print(Back.GREEN + "BTO not accepted by user")
                self.queue_prints.put(["BTO not accepted by user", "", "green"])

                return

            ordered = eval(order_response['request_body'])
            order_status, order_info = self.get_order_info(order_id)

            exit_plan = parse_exit_plan(order)

            new_trade = {"Date": date,
                         "Symbol": order['Symbol'],
                         'isOpen': 1,
                         'BTO-Status' : order_status,
                         "uQty": order_info['quantity'],
                         "Asset" : order["asset"],
                         "Type" : "BTO",
                         "Price" : order_info["price"],
                         "Alert-Price" : alert_price,
                         "ordID" : order_id,
                         "exit_plan" : str(exit_plan),
                         "Trader" : order['Trader'],
                         "Risk" : order['risk'],
                         "SL_mental" : order.get("SL_mental")
                         }

            self.portfolio = self.portfolio.append(new_trade, ignore_index=True)

            if order_status == "FILLED":
                ot, _ = find_last_trade(order, self.portfolio)
                self.portfolio.loc[ot, "Price"] = order_info['price']
                self.portfolio.loc[ot, "filledQty"] = order_info['filledQuantity']

            print(Back.GREEN + f"BTO {order['Symbol']} executed @ {order_info['price']}. Status: {order_status}")
            self.queue_prints.put([f"BTO {order['Symbol']} executed. Status: {order_status}", "", "green"])

            #Log portfolio, trades_log
            log_alert['action'] = "BTO"
            log_alert["portfolio_idx"] = len(self.portfolio) - 1
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs()


        elif order["action"] == "BTO" and order['avg'] is not None:
            # if PT in order: cancel previous and make_BTO_PT_SL_order
            # else : BTO
            alert_price = order['price']
            order_response, order_id, order, ord_chngd = self.confirm_and_send(order, pars,
                                                       make_BTO_lim_order)
            # TODO: uQty should be the same
            self.save_logs("port")
            if order_response is None:  #Assume trade not accepted
                log_alert['action'] = "BTO-Avg-notAccepted"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
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
                av_qt = self.portfolio.loc[open_trade, "Avged-Qty"]
                self.portfolio.loc[open_trade, "Avged-prices-alert"] = f"{al_pr},{alert_price}"
                self.portfolio.loc[open_trade, "Avged-prices"] = f"{av_pr},{order_info['price']}"
                self.portfolio.loc[open_trade, "Avged-uQty"] = f"{av_qt},{order_info['quantity']}"

            avg = self.portfolio.loc[open_trade, "Avged"]
            price = order_info['price']

            self.portfolio.loc[open_trade, "uQty"] += order_info['quantity']
            if order_status == "FILLED":
                self.portfolio.loc[open_trade, "filledQty"] += order_info['filledQuantity']
                self.close_open_exit_orders(open_trade)

            print(Back.GREEN + f"BTO {avg} th AVG, {order['Symbol']} executed. Status: {order_status}")
            self.queue_prints.put([f"BTO {avg} th AVG, {order['Symbol']} executed. Status: {order_status}", "", "green"])

            #Log portfolio, trades_log
            log_alert['action'] = "BTO-avg"
            log_alert["portfolio_idx"] = len(self.portfolio) - 1
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs()

        elif order["action"] == "BTO":
            str_act = "Repeated BTO"
            log_alert['action'] = "BTO-Null-Repeated"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
            self.save_logs(["alert"])
            print(Back.RED + str_act)
            self.queue_prints.put([str_act, "", "red"])


        elif order["action"] == "STC" and isOpen == 0:
            open_trade, _ = find_last_trade(order, self.portfolio, open_only=False)
            if open_trade is None:
                log_alert['action'] = f"STC-alerted without position"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs()
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
                        self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                        self.save_logs()
                    return

            str_act = "STC without BTO, maybe alredy sold"
            log_alert['action'] = "STC-Null-notOpen"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
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
                    self.portfolio.loc[open_trade, f"{STC}-Alerted"] = 1  # TODO: put current price

                    # If alerted and already sold
                    if not pd.isnull(position[ f"{STC}-Price"]):
                        print(Back.GREEN + "Already sold")
                        self.queue_prints.put(["Already sold", "", "green"])

                        log_alert['action'] = f"{STC}-DoneBefore"
                        log_alert["portfolio_idx"] = open_trade
                        self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                        self.save_logs(["alert"])

                        if order['xQty'] != 1:  # if partial and sold, leave
                            return
                    break

                # # Make sure the previous alert executed STC
                # assert(not pd.isnull(position[f"STC{i}-Alerted"]) and
                #        not pd.isnull(position[ f"STC{i}-Price"]))
            else:
                str_STC = "How many STC already?"
                print (Back.RED + str_STC)
                self.queue_prints.put([str_STC, "", "red"])
                log_alert['action'] = "STC-TooMany"
                log_alert["portfolio_idx"] = open_trade
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                return

            qty_bought = position["filledQty"]

            if position["BTO-Status"] == "CANCELED":
                log_alert['action'] = "STC-already cancelled"
                log_alert["portfolio_idx"] = open_trade
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                return

            # Close position of STC All or STC SL
            if qty_bought == 0 and order['xQty'] == 1:

                order_id = position['ordID']
                _ = self.TDsession.cancel_order(self.TDsession.accountId, order_id)

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
                print(Back.GREEN + f"Exit Plan {order['Symbol']} updated, with PT{STC[-1]}: {order['price']}")
                self.queue_prints.put([f"Exit Plan {order['Symbol']} updated, with PT{STC[-1]}: {order['price']}","", "green"])

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
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                return

            if order['xQty'] == 1:
                # Stop updater to avoid overlapping
                self.update_paused = True
                # Sell all and close waiting stc orders
                self.close_open_exit_orders(open_trade)

                position = self.portfolio.iloc[open_trade]
                order['uQty'] = int(position["uQty"]) - qty_sold

            elif order['xQty'] < 1:  # portion
                # Stop updater to avoid overlapping
                self.update_paused = True
                self.close_open_exit_orders(open_trade)
                order['uQty'] = max(round(qty_bought * order['xQty']), 1)

            if order['uQty'] + qty_sold > qty_bought:
                order['uQty'] = qty_bought - qty_sold
                print(Back.RED + Fore.BLACK +
                      f"Order {order['Symbol']} Qty exceeded, changed to {order['uQty']}")
                self.queue_prints.put([f"Order {order['Symbol']} Qty exceeded, changed to {order['uQty']}",
                                "", "red"])


            order_response, order_id, order, _ = self.confirm_and_send(order, pars,
                           make_STC_lim)

            log_alert["portfolio_idx"] = open_trade

            if order_response is None:  # Assume trade rejected by user
                log_alert['action'] = "STC-notAccepted"
                self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
                self.save_logs(["alert"])
                print(Back.GREEN + "STC not accepted by user")
                self.queue_prints.put(["STC not accepted by user", "", "green"])
                self.update_paused = False
                return

            order_status, order_info = self.get_order_info(order_id)
            self.portfolio.loc[open_trade, STC + "-ordID"] = order_id

            # Check if STC price changed
            if order_status == "FILLED":
                self.log_filled_STC(order_id, open_trade, STC)
            else:
                str_STC = f"Submitted: {STC} {order['Symbol']} @{order['price']} Qty:{order['uQty']} ({order['xQty']})"
                print(Back.GREEN + str_STC)
                self.queue_prints.put([str_STC, "", "green"])

            #Log trades_log
            log_alert['action'] = "STC-partial" if order['xQty']<1 else "STC-ALL"
            self.alerts_log = self.alerts_log.append(log_alert, ignore_index=True)
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
        stc_PnL = float((stc_price - bto_price)/bto_price) *100

        xQty = sold_unts/ self.portfolio.loc[open_trade, "uQty"]

        date = order_info["closeTime"]
        #Log portfolio
        self.portfolio.loc[open_trade, STC + "-Status"] = order_status
        self.portfolio.loc[open_trade, STC + "-Price"] = stc_price
        self.portfolio.loc[open_trade, STC + "-Date"] = date
        self.portfolio.loc[open_trade, STC + "-xQty"] =xQty
        self.portfolio.loc[open_trade, STC + "-uQty"] = sold_unts
        self.portfolio.loc[open_trade, STC + "-PnL"] = stc_PnL
        self.portfolio.loc[open_trade, STC + "-ordID"] = order_id

        symb = self.portfolio.loc[open_trade, 'Symbol']

        sold_Qty =  self.portfolio.loc[open_trade, [f"STC{i}-xQty" for i in range(1,4)]].sum()

        str_STC = f"{STC} {symb} @{stc_price} Qty:" + \
            f"{sold_unts}({int(xQty*100)}%), for {stc_PnL:.2f}%"

        if sold_Qty == 1:
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

            if trade["BTO-Status"]  in ["QUEUED", "WORKING"]:
                _, order_info = self.get_order_info(trade['ordID'])

                # Check if number filled Qty changed
                qty_fill = order_info['filledQuantity']
                qty_fill_old = self.portfolio.loc[i, "filledQty"]
                # If so, redo orders
                if not (pd.isnull(qty_fill_old) or qty_fill_old == 0) and \
                    qty_fill_old != qty_fill:
                    redo_orders = True

                self.portfolio.loc[i, "filledQty"] = order_info['filledQuantity']
                self.portfolio.loc[i, "BTO-Status"] = order_info['status']
                trade = self.portfolio.iloc[i]
                self.save_logs("port")

            if pd.isnull(trade["filledQty"]) or trade["filledQty"] == 0:
                continue

            if trade["BTO-avg-Status"] in ["QUEUED", "WORKING"]:
                ordID = trade['ordID'].split(",")[-1]
                _, order_info = self.get_order_info(ordID)
                if order_info['status'] == 'FILLED' :
                    self.portfolio.loc[i, "BTO-avg-Status"] = order_info['status']
                    self.portfolio.loc[i, "filledQty"] += order_info['filledQuantity']
                    redo_orders = True
                    trade = self.portfolio.iloc[i]
                    self.save_logs("port")

            if redo_orders:
                self.close_open_exit_orders(i)

            exit_plan = eval(trade["exit_plan"])
            if  exit_plan != {}:
                # If strings in exit values, stock price for option
                if any([isinstance(e, str) for e in exit_plan.values()]):
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

                order_status, _ =  self.get_order_info(STC_ordID)

                if order_status == 'CANCELED':
                    # Try next order number. probably went through
                    order_status, _ =  self.get_order_info(STC_ordID + 1)

                    if order_status == 'FILLED':
                        STC_ordID = STC_ordID + 1
                        self.portfolio.loc[i, STC + "-ordID"] =  STC_ordID

                self.portfolio.loc[i, STC+"-Status"] = order_status
                trade = self.portfolio.iloc[i]

                if order_status == "FILLED" and np.isnan(trade[STC+"-xQty"]):
                    self.log_filled_STC(STC_ordID, i, STC)

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
            elif v[:2] == "SL" and float(pt) >= quote:
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
        for ii in range(1, nPTs+1):
            STC = f"STC{ii}"
            order = {'Symbol': trade['Symbol']}

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
                    uQty = uQty[:ii] + [round(uleft/nPts)]*nPts
                    uQty[-1] = int(uQty_bought - sum(uQty[:-1]))
                    xQty = [round(u/uQty_bought,1) for u in uQty]

            else:
                SL = exit_plan["SL"]
                # Check if exit prices are strings (stock price for option)
                if isinstance(SL, str): SL = None
                if isinstance(exit_plan[f"PT{ii}"], str): exit_plan[f"PT{ii}"] = None

                ord_func = None
                # Lim and Sl OCO order
                if exit_plan[f"PT{ii}"] is not None and SL is not None:
                    # Lim_SL order
                    ord_func = make_Lim_SL_order
                    order["PT"] = exit_plan[f"PT{ii}"]
                    order["SL"] = exit_plan["SL"]
                    order['uQty'] = uQty[ii - 1]
                    order['xQty'] = xQty[ii - 1]

                # Lim order
                elif exit_plan[f"PT{ii}"] is not None and SL is None:
                    ord_func = make_STC_lim
                    order["price"] = exit_plan[f"PT{ii}"]
                    order['uQty'] = uQty[ii - 1]
                    order['xQty'] = xQty[ii - 1]

                # SL order
                elif ii == 1 and SL is not None:
                    ord_func = make_STC_SL
                    order["price"] = exit_plan["SL"]
                    order['uQty'] = int(trade['uQty'])
                    order['xQty'] = 1

                elif ii > 1 and SL is not None:
                    break

                else:
                    raise("Case not caught")

                # Check that is below current price
                if order.get("SL") is not None:
                    order = self.SL_below_market(order)

                if ord_func is not None and order['uQty'] > 0:
                    _, STC_ordID = send_order(ord_func(**order), self.TDsession)
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

            str_prt = f"{trade['Symbol']} option expired -100% uQty: {trade['filledQty']}"
            print(Back.GREEN + str_prt)
            self.queue_prints.put([str_prt,"", "green"])





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
            error
        return order, True
    else:
        return order, False


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

    self = AlertTrader(update_portfolio=False)
    self.plot_portfolio()
    self.new_stock_alert(order, pars, msg)

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
