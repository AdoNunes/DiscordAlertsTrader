#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 15 10:05:24 2021
@author: adonay
"""
from datetime import datetime
import pandas as pd
import os.path as op
import sys
import queue

# from pathlib import Path
# file = Path(__file__).resolve()
# parent, top = file.parent, file.parents[3]
# sys.path.append(str(top))
sys.path.append("/data/Dropbox (Partners HealthCare)/xtrades_repo/")
from place_order import (make_BTO_lim_order, send_order,
                         make_STC_lim, make_Lim_SL_order, make_STC_SL)
from disc_trader import AlertTrader
from message_parser import parser_alerts, get_symb_prev_msg, combine_new_old_orders
import config as cfg



class TDSession_test():

    def __init__(self, order_log_fname="test_order_log.csv"):

        self.order_log_fname = order_log_fname
        if op.exists(self.order_log_fname):
            self.order_log = pd.read_csv(self.order_log_fname)
        else:
            self.order_log = pd.DataFrame(columns=[ "ordID",
                "symbol", "quantity", 'status', 'price', "closeTime", 'filledQuantity'])

        self.accountId = "19283746"
        self.quotes= pd.DataFrame(columns=["symbol", "askPrice", "bidPrice"])

    def make_quote(self, sym, ask, bid):
        inx_sym = self.quotes["symbol"].str.contains(sym)
        if any(inx_sym):
            self.quotes.loc[inx_sym,:] = [sym, ask, bid]
        else:
            self.quotes = self.quotes.append({"symbol":sym, "askPrice":ask,
                                          "bidPrice":bid}, ignore_index=True)

    def get_quotes(self, instruments):
        if isinstance(instruments, str): instruments = [instruments]

        quotes = {}
        for sym in instruments:
            sqt = self.quotes[self.quotes["symbol"] == sym]
            if sqt.size == 0:
                raise ValueError("quote not found, it needs to be created with self.make_quote")
            quotes[sym] = {'askPrice': sqt['askPrice'].iloc[0],
                           'bidPrice': sqt['bidPrice'].iloc[0]}
        return quotes


    def cancel_order(self, accountId, order_id):
        order_bool =  self.order_log['ordID'] == order_id
        assert sum(order_bool)==1

        order = self.order_log.loc[order_bool]
        if order["status"] == "WORKING":
            self.order_log.loc[order_bool, "status"] = "CANCELLED"
            print(f"Order {order_id} cancelled")

    def get_orders(self, account, order_id):
        # BTO
        msk = self.order_log["ordID"]  == order_id
        inx = msk[msk].index.values
        if not inx.size:
            raise ValueError ("ordID not found")
        elif inx.size >1:
            raise ValueError ("ordID found more than once")
        else:
            inx, = inx

        order_status = self.order_log.loc[inx, "status"]
        quantity = self.order_log.loc[inx, "quantity"]
        filledQuantity = self.order_log.loc[inx, "filledQuantity"]
        price = self.order_log.loc[inx, "price"]
        date = self.order_log.loc[inx, "closeTime"]

        order_info = {'orderLegCollection':[{'quantity': quantity}],
                      'quantity' :  quantity,
                      'filledQuantity': filledQuantity,
                      'status' : order_status,
                      'price' : price,
                      "closeTime" : date}

        if not pd.isnull(self.order_log.loc[inx, "OCO"]):
            order_info['orderStrategyType'] = "OCO"
            order_info['childOrderStrategies'] = [{"status": order_info['status']},
                                                  {"status": order_info['status']}]
        else:
            order_info['orderStrategyType'] = "SINGLE"

        return order_info


    def place_order(self, account, order):
        def make_ordID(n=1):
            # n = num ordIds
            ords = self.order_log["ordID"].to_numpy()
            inx = 0
            while True:
                if n > 1:
                    inxs = [inx + i for i in range(n)]
                    if not any(True for i in inxs if i in ords):
                        order_id = inx
                        break
                else:
                    if inx not in ords:
                        order_id = inx
                        break
                inx += 1
            return order_id

        order_response ={}
        # Strategy Order, e.g. OCO
        if order.template.get('orderStrategyType') =='OCO':

            chld_ord = order.child_order_strategies
            order_id = make_ordID(len(chld_ord))
            order_id_ret = order_id
            oco_inx = len(self.order_log)

            for chld in chld_ord.values():
                price = chld.get("price")
                stprice = chld.get("stopPrice")
                # If SL order with no stopPrice
                if price is None:
                    price = chld.get("stopPrice")
                    stprice = None

                ord_info = {
                    "ordID" : order_id,
                    "symbol" : chld['orderLegCollection'][0]["instrument"]['symbol'],
                    "quantity" : chld['orderLegCollection'][0]['quantity'],
                    "closeTime" : datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "price" : price,
                    "stopPrice": stprice,
                    "status" : "WORKING",
                    "filledQuantity" : 0,
                    "session" : chld["session"],
                    "orderType" : chld['orderType'],
                    "duration" :  chld["duration"],
                    "instruction" :chld['orderLegCollection'][0]["instruction"],
                    "strategyType" : chld['orderStrategyType'],
                    "OCO" : oco_inx
                   }
                # print(ord_info)
                self.order_log = self.order_log.append(ord_info, ignore_index=True)
                order_id += 1
            order_response["order_id"] = order_id_ret
            return order_response

        order_id = make_ordID(1)
        price = order.template.get('price')
        stprice = order.template.get('stopPrice')
        if price is None:
            price = order.template.get('stopPrice')
            stprice = None

        ord_info = {
            "ordID" : order_id,
            "symbol" : order.order_legs_collection['order_leg_1']['instrument']['symbol'],
            "quantity" : order.order_legs_collection['order_leg_1']['quantity'],
            "closeTime" : datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "price" : price,
            "stopPrice": stprice,
            "status" : "WORKING",
            "filledQuantity" : 0,
            "session" :  order.template["session"],
            "orderType" :  order.template['orderType'],
            "duration" :   order.template["duration"],
            "instruction" : order.order_legs_collection['order_leg_1']["instruction"],
            "strategyType" : order.template['orderStrategyType'],
            "OCO" : None
           }
        # print(ord_info)

        self.order_log = self.order_log.append(ord_info, ignore_index=True)
        order_response["order_id"] = order_id
        return order_response

    def execute_orders(self):
        def fill_order(ix):
            self.order_log.loc[ix, "status"] = "FILLED"
            self.order_log.loc[ix, "filledQuantity"] = order["quantity"]
            close_OCO(ix)
        def close_OCO(ix):
            if not pd.isnull(self.order_log.loc[ix, "OCO"]):
                inx_oco = self.order_log.loc[ix, "OCO"]
                if inx_oco == ix: inx_oco +=1
                self.order_log.loc[inx_oco, "status"] = "CANCELLED"

        for ix, order in self.order_log.iterrows():
            if order["status"] != "WORKING":
                continue
            quote = self.get_quotes([order["symbol"]])[order["symbol"]]
            ask, bid = quote['askPrice'], quote['bidPrice']
            if order["instruction"] == "BUY" and  ask <= order["price"]:
                fill_order(ix)
            elif order["instruction"] == "SELL":
                if order["orderType"] == "LIMIT" and  bid >= order["price"]:
                    fill_order(ix)
                elif order["orderType"] == "STOP" and  bid <= order["price"]:
                    fill_order(ix)
                elif order["orderType"] == "STOP_LIMIT" and \
                    bid <= order["price"] and bid > order["stopPrice"]:
                    fill_order(ix)

if 0:
    tdt = TDSession_test()
    sym, ask, bid ='TSLA', 698, 696
    tdt.make_quote(sym,ask, bid)
    quote = tdt.get_quotes(sym)
    assert(list(quote.keys())[0] == sym)
    assert(quote[sym]["askPrice"] == ask)
    assert(quote[sym]["bidPrice"] == bid)


    Altrader = AlertTrader(portfolio_fname="trader_portfolio_simulated.csv",
                alerts_log_fname="trader_logger_simulated.csv",
                queue_prints=queue.Queue(maxsize=10),
                test_TDsession=tdt, update_portfolio=False)

    Altrader.price_now(sym, pflag=1)
    msg = "BTO TSLA @ 698 PT1 700 SL 690"
    pars, order =  parser_alerts(msg, "stock")
    order["Trader"] = "tester1"
    Altrader.new_trade_alert(order, pars,msg)

    tdt.make_quote('TSLA', 698, 699)
    tdt.execute_orders()
    Altrader.update_orders()

    order = {"Symbol" : "TSLA",
             "uQty" : 3,
             "price" : 690
             }
    new_order = make_BTO_lim_order(**order)
    ord_status, ordID = tdt.place_order(tdt.accountId, new_order)
    tdt.execute_orders()
    ord_status, ord_info = tdt.get_orders(tdt.accountId , ordID)

    tdt.make_quote("TSLA", 690, 686)
    tdt.execute_orders()
    ord_status, ord_info = tdt.get_orders(tdt.accountId , ordID)

    order = {"Symbol" : "TSLA",
             "uQty" : 3,
             "PT" : 695,
             "SL" : 680,
             "SL_stop" : 670
             }
    new_order = make_Lim_SL_order(**order)
    ord_status, ordID = tdt.place_order(tdt.accountId, new_order)

    tdt.make_quote("TSLA", 698, 696)
    tdt.execute_orders()
    ord_status, ord_info = tdt.get_orders(tdt.accountId, ordID)


    order = {"Symbol" : "STC-lim",
             "uQty" : 3,
             "price" : 3.5,
             "PT" : 99,
             "SL" : 99,
             "SL_stop" : 99
              }

    new_order = make_STC_lim(**order)
    tdt.place_order(tdt.accountId, new_order)


    order = {"Symbol" : "STC-SL",
             "uQty" : 3,
             "price" : 99,
             "PT" : 99,
             "SL" : 1.4,
             "SL_stop" : 1.6
              }
    new_order =  make_STC_SL(**order)
    tdt.place_order(tdt.accountId, new_order)


    order = {"Symbol" : "STC-SL",
             "uQty" : 3,
             "price" : 99,
             "PT" : 99,
             "SL" : 1.4,
              }
    new_order =  make_STC_SL(**order)
    tdt.place_order(tdt.accountId, new_order)

