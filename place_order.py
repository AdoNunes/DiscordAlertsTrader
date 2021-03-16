#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 16 17:52:31 2021

@author: adonay
"""

import td
import json
import pandas as pd
from datetime import datetime
from secrets_api import auth
from td.client import TDClient
from td.orders import Order, OrderLeg



def get_TDsession(account_n=0, accountId=None):

    """Provide either:
        - account_n: indicating the orinal position from the accounts list
        (if only one account, it will be 0)
        - accountId: Number of the account

    auth is a dict with login info loaded from config.py
    """


    # Create a new session, credentials path is required.
    TDSession = TDClient(
        client_id=auth['client_id'],
        redirect_uri=auth['redirect_url'],
        credentials_path='secrets_td.json'
    )

    # Login to the session
    TDSession.login()

    if accountId is not None:
        TDSession.accountId = accountId
    else:
        account_n = 0
        accounts_info = TDSession.get_accounts(account="all")[account_n]
        TDSession.accountId = accounts_info['securitiesAccount']['accountId']

    return TDSession



# TDSession = get_TDsession()

# acc_inf = TDSession.get_accounts(TDSession.accountId, ['orders','positions'])


def get_positions_orders(TDSession):
    acc_inf = TDSession.get_accounts(TDSession.accountId, ['orders','positions'])

    df_pos = pd.DataFrame(columns=["symbol", "asset", "type", "Qty",
                                    "Avg Price", "PnL", "PnL %"])

    for pos in acc_inf['securitiesAccount']['positions']:

        long = True if pos["longQuantity"]>0 else False

        pos_inf = {
             "symbol":pos["instrument"]["symbol"],
             "asset":pos["instrument"]["assetType"],
             "type": "long" if  long else "short",
             "Avg Price": pos['averagePrice'],
             "PnL": pos["currentDayProfitLoss"],
             }
        pos_inf["Qty"] = pos[f"{pos_inf['type']}Quantity"]
        pos_inf["PnL %"] = pos_inf["PnL"]/(pos_inf["Avg Price"]*pos_inf["Qty"])

        df_pos = df_pos.append(pos_inf, ignore_index=True)


    df_ordr = pd.DataFrame(columns=["symbol", "asset", "type", "Qty",
                                    "Price", "action"])
    if 'orderStrategies' not in acc_inf['securitiesAccount'].keys():
        return df_pos, df_ordr

    for ordr in acc_inf['securitiesAccount']['orderStrategies']:
        pass

    return df_pos, df_ordr




def make_BTO_lim_order(Symbol:str, uQty:int, price:float, **kwarg):

    new_order=Order()
    new_order.order_strategy_type("TRIGGER")
    new_order.order_type("LIMIT")
    new_order.order_session('NORMAL')
    new_order.order_duration('GOOD_TILL_CANCEL')
    new_order.order_price(price)

    order_leg = OrderLeg()
    order_leg.order_leg_instruction(instruction="BUY")
    order_leg.order_leg_quantity(quantity=uQty)
    order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
    new_order.add_order_leg(order_leg=order_leg)

    return new_order



def make_BTO_PT_SL_order(Symbol:str, uQty:int, price:float, PTs:list=None,
                         PTs_Qty:list=None, SL:float=None, SL_stop:float=None, **kwarg):

    new_order= make_BTO_lim_order(Symbol, uQty, price)

    if PTs == [None]:
        return new_order

    PTs_Qty = [ round(uQty * pqty) for pqty in PTs_Qty]

    for PT, pqty in zip(PTs, PTs_Qty):
        new_child_order = new_order.create_child_order_strategy()
        new_child_order = make_Lim_SL_order(Symbol, pqty, PT, SL, SL_stop, new_child_order)
        new_order.add_child_order_strategy(child_order_strategy=new_child_order)

    return new_order


def make_Lim_SL_order(Symbol:str, uQty:int,  PT:float, SL:float, SL_stop:float=None, new_order=None, strike=None, **kwarg):

    if new_order is None:
        new_order = Order()
    new_order.order_strategy_type("OCO")

    child_order1 = new_order.create_child_order_strategy()
    child_order1.order_strategy_type("SINGLE")
    child_order1.order_type("LIMIT")
    child_order1.order_session('NORMAL')
    child_order1.order_duration('GOOD_TILL_CANCEL')
    child_order1.order_price(float(PT))

    child_order_leg = OrderLeg()
    
    child_order_leg.order_leg_quantity(quantity=uQty)
    if strike is not None:
        child_order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
        child_order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    else:
        child_order_leg.order_leg_instruction(instruction="SELL")
        child_order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)

    child_order1.add_order_leg(order_leg=child_order_leg)
    new_order.add_child_order_strategy(child_order_strategy=child_order1)

    child_order2 = new_order.create_child_order_strategy()
    child_order2.order_strategy_type("SINGLE")
    child_order2.order_session('NORMAL')
    child_order2.order_duration('GOOD_TILL_CANCEL')

    if SL_stop is not None:
        child_order2.order_type("STOP_LIMIT")
        child_order2.order_price(float(SL))
        child_order2.stop_price(float(SL_stop))
    else:
        child_order2.order_type("STOP")
        child_order2.stop_price(float(SL))
        
    child_order2.add_order_leg(order_leg=child_order_leg)
    new_order.add_child_order_strategy(child_order_strategy=child_order2)

    return new_order


def make_STC_lim(Symbol:str, uQty:int, price:float, strike=None, **kwarg):
    
    new_order=Order()
    new_order.order_strategy_type("SINGLE")
    new_order.order_type("LIMIT")
    new_order.order_session('NORMAL')
    new_order.order_duration('GOOD_TILL_CANCEL')
    new_order.order_price(float(price))

    order_leg = OrderLeg()
    order_leg.order_leg_quantity(quantity=int(uQty))

    if strike is not None:
        order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
        order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    else:
        order_leg.order_leg_instruction(instruction="SELL")
        order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
    new_order.add_order_leg(order_leg=order_leg)
    
    return new_order

def make_STC_SL(Symbol:str, uQty:int, price:float, SL:float, strike=None,
                SL_stop:float=None, new_order=Order(), **kwarg):
    
    new_order=Order()
    new_order.order_strategy_type("SINGLE")

    if SL_stop is not None:
        new_order.order_type("STOP_LIMIT")
        new_order.stop_price(float(SL_stop))
        new_order.order_price(float(SL))
    else:
        new_order.order_type("STOP")
        new_order.stop_price(float(SL))

    new_order.order_session('NORMAL')
    new_order.order_duration('GOOD_TILL_CANCEL')

    order_leg = OrderLeg()
    order_leg.order_leg_quantity(quantity=int(uQty))
    if strike is not None:
        order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
        order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    else:
        order_leg.order_leg_instruction(instruction="SELL")
        order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
    new_order.add_order_leg(order_leg=order_leg)

    return new_order

def make_lim_option(Symbol:str, uQty:int, price:float, **kwarg):
    """ Symbol : is optionID from ```make_optionID```
    """
    new_order=Order()
    new_order.order_strategy_type("SINGLE")
    new_order.order_type("LIMIT")
    new_order.order_session('NORMAL')
    new_order.order_duration('GOOD_TILL_CANCEL')
    new_order.order_price(float(price))

    order_leg = OrderLeg()
    order_leg.order_leg_instruction(instruction="BUY_TO_OPEN")
    order_leg.order_leg_quantity(quantity=int(uQty))
    order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    new_order.add_order_leg(order_leg=order_leg)

    return new_order



def make_optionID(Symbol:str, expDate:str, strike=str, **kwarg):
    """
    date: "[M]M/[D]D" or "[M]M/[D]D/YY[YY]"
    """
    strike, opt_type = float(strike[:-1]), strike[-1]
    date_elms = expDate.split("/")
    date_frm = f"{int(date_elms[0]):02d}{int(date_elms[1]):02d}"
    if len(date_elms) == 2: # MM/DD, year = current year
        year = str(datetime.today().year)[-2:]
        date_frm = date_frm + year
    elif len(date_elms) == 3:
        date_frm = date_frm + f"{int(date_elms[2][-2:]):02d}"
    
    # Strike in interger if no decimals
    if strike / int(strike) == 1:
        return f"{Symbol}_{date_frm}{opt_type}{int(strike)}"
    return f"{Symbol}_{date_frm}{opt_type}{strike}"


def send_order(new_order, TDSession):
    order_response = TDSession.place_order(account=TDSession.accountId,
                                       order=new_order)
    order_id = order_response["order_id"]
    return order_response, order_id



#
#msft_quotes = TDSession.get_quotes(instruments=['MSFT'])
#
#
#optID= make_optionID('PLTR', '3/26', 27, 'C')
#opt_order = make_lim_option(optID, 1, 3.1)
#
#order_response = TDSession.place_order(account=self.TDsession.accountId,
#                                       order=opt_order)
#order_id = order_response["order_id"]
#order_info = TDSession.get_orders(account=accountId, order_id=order_id)
#order_status = order_info['status']
#
#
#TDSession.get_options_chain({"symbol":"PLTR", "contractType":"CALL", "strike":27,
#                             "fromDate":"2021-03-26", "toDate":"2021-03-26"})
#
#
#new_order = make_BTO_PT_SL_order("PLTR", 1, BTO=26.0, PT=30.0, SL=24.0, SL_stop=24.5)
#
#order_response = TDSession.place_order(account=accountId,
#                                       order=new_order)
#order_id = order_response["order_id"]
#order_info = TDSession.get_orders(account=accountId, order_id=order_id)
#order_status = order_info['childOrderStrategies'][0]['status']
#
#
#
#accounts_info = TDSession.get_accounts(account="all", fields=['orders'])[account_n]
#
#
#TDSession.cancel_order(self.TDsession.accountId, order_id)
#




