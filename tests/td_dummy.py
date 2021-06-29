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
# from pathlib import Path
# file = Path(__file__).resolve()
# parent, top = file.parent, file.parents[3]
# sys.path.append(str(top))
sys.path.append("/home/adonay/Dropbox (Partners HealthCare)/xtrades_repo/")
from place_order import (make_BTO_lim_order, send_order,
                         make_STC_lim, make_Lim_SL_order, make_STC_SL)

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
        quotes = {}
        for sym in instruments:
            sqt = self.quotes[self.quotes["symbol"] == sym]
            if sqt.size == 0:
                raise ValueError("quote not found, it needs to be created with self.make_quote")
            quotes[sym] = {'askPrice': sqt['askPrice'].iloc[0],
                           'bidPrice': sqt['bidPrice'].iloc[0]}
        return quotes


    def cancel_order(accountId, order_id):
        print(f"Order {order_id} cancelled")

    def get_orders(self, account, order_id):
        # BTO
        msk = self.order_log["ordID"]  == order_id
        inx = msk[msk].index.values
        if not inx.size:
            raise ValueError ("ordID not found")

        order_status, = self.order_log.loc[inx, "status"].values
        quantity, = self.order_log.loc[inx, "quantity"].values
        filledQuantity, = self.order_log.loc[inx, "filledQuantity"].values
        price, = self.order_log.loc[inx, "price"].values
        date, = self.order_log.loc[inx, "closeTime"].values

        order_info = {'orderLegCollection':[{'quantity': quantity}],
                      'quantity' :  quantity,
                      'filledQuantity': filledQuantity,
                      'status' : order_status,
                      'price' : price,
                      "closeTime" : date}

        return order_status, order_info


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

        # Strategy Order, e.g. OCO
        if order.template.get('orderStrategyType') =='OCO':

            chld_ord = order.child_order_strategies
            order_id = make_ordID(len(chld_ord))
            order_id_ret = order_id

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
                    "strategyType" : chld['orderStrategyType']
                   }
                print(ord_info)
                self.order_log = self.order_log.append(ord_info, ignore_index=True)
                order_id += 1
            return 'OK', order_id_ret

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
           }
        print(ord_info)

        self.order_log = self.order_log.append(ord_info, ignore_index=True)

        return 'OK', order_id



if 0:
    tdt = TDSession_test()
    tdt.make_quote("TSLA", 698, 696)
    quote = tdt.get_quotes(["TSLA"])

    order = {"Symbol" : "LimBuy",
             "uQty" : 3,
             "price" : 2.5
             }
    new_order = make_BTO_lim_order(**order)
    ord_status, ordID = tdt.place_order(tdt.accountId, new_order)

    order = {"Symbol" : "OCO",
             "uQty" : 3,
             "price" : 99,
             "PT" : 3.5,
             "SL" : 1.4,
             "SL_stop" : 1.6
             }
    new_order = make_Lim_SL_order(**order)
    tdt.place_order(tdt.accountId, new_order)

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


    tdt.make_quote("QUO", 99, 66)
    tdt.make_quote("QUO2", 999, 696)
    tdt.get_quotes(["QUO", "QUO2"])