#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  8 18:11:55 2021

@author: adonay
"""
import re
import pandas as pd
from datetime import datetime
import numpy as np

def parse_trade_alert(msg, asset=None):
    # BTO 10 AAPL @ 120
    pattern = r'\b(BTO|STC|STO|BTC)\b\s*(\d+)?\s*([A-Z]+)\s*(\d+[.\d+]*[cp]?)?\s*(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)?\s*@\s*[$]*[ ]*(\d+(?:[,.]\d+)?|\.\d+)'
    match = re.search(pattern, msg, re.IGNORECASE)
    strike_date = True
    if match is None:
        pattern = r'\b(BTO|STC|STO|BTC)\b\s*(\d+)?\s*([A-Z]+)\s*(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)?\s*(\d+[.\d+]*[CP]?)?\s@*[$]*[ ]*(\d+(?:[,.]\d+)?|\.\d+)'
        match = re.search(pattern, msg, re.IGNORECASE)
        strike_date = False
    if match:
        if strike_date:
            action, quantity, ticker, strike, expDate, price = match.groups()
        else:
            action, quantity, ticker, expDate, strike, price = match.groups()

        asset_type = 'option' if strike and expDate else 'stock'
        symbol =  ticker.upper()
        order = {
            'action': action.upper(),
            'Symbol': symbol,
            'Qty': int(quantity) if quantity else None,
            'price': float(price.replace(',', '.')) if price else None,
            'asset': asset_type
        }
        str_ext = ""
        if asset_type == 'option':
            # fix missing strike, assume Call
            if "c" not in strike.lower() and "p" not in strike.lower():
                strike = strike + "c"
                order['strike'] = strike.upper()
                str_ext = " No direction found in option strike, assuming Call"

            order['strike'] = strike.upper()
            order['expDate'] = expDate
            order['Symbol'] = fix_index_symbols(symbol)
            order['Symbol'] = make_optionID(**order)

        risk_level = parse_risk(msg)
        order['risk'] = risk_level

        pars = []
        for el in [action, quantity, ticker, strike, expDate]:
            if el is not None:
                pars.append(el)
        pars = " ".join(pars)
        pars += f" @{price}"
        for el in [risk_level, str_ext]:
            if el is not None:
                pars += f" {el}"

        if action.upper() in ["BTO", "STO"]:
            if "avg" in msg.lower() or "average" in msg.lower():
                avg_price, _ = parse_avg(msg)
                pars = pars + f"AVG to {avg_price} "
                order["avg"] = avg_price
            else:
                order["avg"] = None

            order['open_trailingstop'] = trailingstop(msg)
            if order.get('open_trailingstop'):
                pars += f" {order['open_trailingstop']}"

            try:
                pt1_v, pt2_v, pt3_v, sl_v = parse_exits(msg)
                n_pts = 3 if pt3_v else 2 if pt2_v else 1 if pt1_v else 0
                pts_qty = set_pt_qts(n_pts)
                order, pars = make_order_exits(order, msg, pars, asset_type)
                order["n_PTs"] = n_pts
                order["PTs_Qty"] = pts_qty
            except:
                order["PT1"] =  None
                order["PT2"] = None
                order["PT3"] = None
                order["SL"] = None

        elif action.upper() in ["STC", "BTC"]:
            xamnt = parse_sell_ratio_amount(msg, asset_type)
            if order["Qty"] is None:
                pars = pars + f" xamount: {xamnt}"
            order["xQty"] = xamnt

        return pars, order
    else:
        # try exit update
        pattern = r'\b(exit[ ]?update)\b\s*([A-Z]+)\s*(\d+[.\d+]*[cp]?)?\s*(\d{1,2}\/\d{1,2})?(?:\/202\d|\/2\d)?\s*'
        match = re.search(pattern, msg, re.IGNORECASE)
        if match:
            action, ticker, strike, expDate = match.groups()

            asset_type = 'option' if strike and expDate else 'stock'
            symbol =  ticker.upper()

            order = {
            'action': "ExitUpdate",
            'Symbol': symbol,
            'asset': asset_type
            }
            str_ext = f'ExitUpdate: {symbol} '
            if asset_type == 'option':
                # fix missing strike, assume Call
                if "c" not in strike.lower() and "p" not in strike.lower():
                    strike = strike + "c"
                    order['strike'] = strike.upper()
                    str_ext = " No direction found in option strike, assuming Call"

                order['strike'] = strike.upper()
                order['expDate'] = expDate
                order['Symbol'] = fix_index_symbols(symbol)
                order['Symbol'] = make_optionID(**order)
                str_ext += f"{strike.upper()} {expDate}"
            order, str_ext = make_order_exits(order, msg, str_ext, asset_type)

            if "isopen:no" in msg.lower():
                order["isopen"] = False
                str_ext += " isopen:no"
            elif "cancelavg" in msg.lower():
                order["cancelavg"] = True
                str_ext += " cancelAvg"

            return str_ext, order
        return None, None


def fix_index_symbols(symbol):
    if symbol.upper() == "SPX":
        symbol = "SPXW"
    elif symbol.upper() == "NDX":
        symbol = "NDXP"
    return symbol


def trailingstop(msg):
    # inverse TSbuy
    expc = r"invTSbuy [:]?\s*([\d]{1,2}[%]?)"
    match = re.search(expc, msg, re.IGNORECASE)
    if match:
        ts = match.groups()[0]
        return f"invTSbuy {ts}"
    exprs = ['tsbuy', 'trailstop', 'trailingstop', 'trailing stop']
    for exp in exprs:
        expc = exp + r"[:]?\s*([\d]{1,2}[%]?)"
        match = re.search(expc, msg, re.IGNORECASE)
        if match:
            ts = match.groups()[0]
            return f"TSbuy {ts}"



    return False
def ordersymb_to_str(symbol):
    "Symbol format AAA_YYMMDDCCPXXX"
    if "_" in symbol:
        # option
        exp = r"(\w+)_(\d{6})([CP])([\d.]+)"
        match = re.search(exp, symbol, re.IGNORECASE)
        if match:
            symbol, date, type, strike = match.groups()
            symbol = f"{symbol} {strike}{type} {date[:2]}/{date[2:4]}"
    return symbol


def make_order_exits(order, msg, str_prt, asset):
    pt1_v, pt2_v, pt3_v, sl_v = parse_exits(msg)
    if asset == "option":
        order["PT1"] =  set_exit_price_type(pt1_v, order)
        order["PT2"] = set_exit_price_type(pt2_v, order)
        order["PT3"] = set_exit_price_type(pt3_v, order)
        order["SL"] = set_exit_price_type(sl_v, order)
    elif asset == "stock":
        order["PT1"] = pt1_v
        order["PT2"] = pt2_v
        order["PT3"] = pt3_v
        order["SL"] = sl_v

    exits = ["PT1","PT2","PT3","SL"]
    for ext in exits:
            if order["PT1"] is not None:
                str_prt = str_prt + f', {ext}:{order[ext]}'
    return order, str_prt

def set_exit_price_type(exit_price, order):
    """Option or stock price decided with smallest distance"""
    if exit_price is None:
        return exit_price
    if (isinstance(exit_price, str) and ("TS" in exit_price or "%" in exit_price)) or \
        (isinstance(exit_price, str) and not exit_price):
        return exit_price
    if isinstance(exit_price, str):
        exit_price = eval(exit_price)

    price_strk = float(order['strike'][:-1])
    order_price = order.get('price', exit_price )  # IF NO ORDER PRICE TAKE EXIT!
    rtio_stock = abs(price_strk - exit_price)
    rtio_option = abs(order_price - exit_price)

    if rtio_stock < rtio_option:
        exit_price = str(exit_price)
    elif rtio_stock > rtio_option:
        exit_price = exit_price
    else:
        raise("Not sure if price of option or stock")
    return exit_price

def set_pt_qts(n_pts):
    if n_pts == 3:
        amnts = [.33, .33, .34]
    elif  n_pts == 2:
        amnts = [.5, .5]
    elif  n_pts in range(2):
        amnts = [1]
    return amnts

def parse_action(msg):
    if pd.isnull(msg):
        return None
    actions = ["BTO", "STC"]
    act =  actions[0] if actions[0] in msg  else actions[1] if actions[1] in msg else None
    return act

def parse_Symbol(msg, act):
    re_Symbol = re.compile("\*\*([A-Z]*?)\*\*")
    Symbol_info = re_Symbol.search(msg)

    if Symbol_info is None:
        re_Symbol = re.compile(f"{act} ([A-Z]+)")
        Symbol_info = re_Symbol.search(msg)

        if Symbol_info is None:
            for wrd in [ "ATH", "BTO", "STC", "ITM"]:
                msg = msg.replace(wrd+" ", " ")
            msg = msg.replace('VWAP', " ")
            msg = msg.replace("I'", "i'")

            re_Symbol = re.compile("([A-Z]+)(?![a-z])")
            Symbol_info = re_Symbol.search(msg)
            if Symbol_info is None:
                return None, None
            Symbol = Symbol_info.groups()[-1].replace(" ",'')

    Symbol = Symbol_info.groups()[-1]
    # print ("Symbol: ", Symbol)
    return Symbol, Symbol_info.span()

def parse_mark_stock(msg, Symbol, act):
    re_mark = re.compile("\@[ ]*[$]*[ ]*(\d+(?:\.\d+)?|\.\d+)")
    mark_inf = re_mark.search(msg)
    if mark_inf is None:
        re_mark = re.compile(f"{act} "+ "([\*])?([\*])?" + f"{Symbol}" +"([\*])?([\*])? (\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)
        if mark_inf is None:
            return None
    mark = float(mark_inf.groups()[-1])
    return mark

def parse_mark_option(msg):
    re_mark = re.compile("(?:@|at)[a-zA-Z]?[ ]*[$]?[ ]*([.]?\d+(?:\.\d+)?)")
    mark_inf = re_mark.search(msg)
    if mark_inf is None:
        re_mark = re.compile("(?:@|at)[a-zA-Z]?[ ]*[$]?[ ]*([,]?\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)

    if mark_inf is None:
        date = parse_date(msg)
        re_mark = re.compile(f"{date}[ ]*[$]?[ ]*([.]?\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)
        if mark_inf is None:
            return None
    if mark_inf.groups()[-1].count(".") > 1:
        if mark_inf.groups()[-1].startswith("."):
            return float(mark_inf.groups()[-1][1:].replace(",","."))
    mark = float(mark_inf.groups()[-1].replace(",","."))
    return mark

def parse_strike(msg):
    re_strike = re.compile(" [$]?(\d+(?:\.\d+)?)(C|c|P|p)")
    strike_inf = re_strike.search(msg)
    # avoid "BTO 1 COIN 73c" detected 1C
    if strike_inf is None:
        re_strike = re.compile(" [$]?(\d+(?:\.\d+)?)[ ]?(C|c|P|p)")
        strike_inf = re_strike.search(msg)
    elif strike_inf is None and "BTO" in msg:
        sym = parse_Symbol(msg, "BTO")[0]
        re_strike = re.compile(f"{sym} (\d+(?:\.\d+)?)")
        strike_inf = re_strike.search(msg)
        if strike_inf is None:
            return None, None
        return strike_inf.groups()[0], "C"

    if strike_inf is None:
        return None, None
    strike = strike_inf.groups()[0]
    optType = strike_inf.groups()[1].capitalize()
    return strike, optType

def parse_date(msg):
    # deal with 4 digit year
    re_date = re.compile("((\d{1,2}\/\d{1,2})\/(20\d{2}))")
    date_inf = re_date.search(msg)
    if date_inf is not None:
            dt_1 = date_inf.groups()[1]
            dt_2 = date_inf.groups()[2]
            date = f"{dt_1}/{dt_2[2:]}"
            return date

    re_date = re.compile("(\d{1,2}\/\d{1,2}(?:\/\d{1,2})?)")
    date_inf = re_date.search(msg)
    if date_inf is None:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                  "Sep", "Oct", "Nov", "Dec"]

        exp= f"({'|'.join(months)})" + " (\d{1,2}) (20\d{2})"
        re_date = re.compile(exp)
        date_inf = re_date.search(msg)

        if date_inf is None:
            # crx
            return None
        else:
            dt_1 = months.index(date_inf.groups()[0])
            dt_2 = date_inf.groups()[1]
            dt_3 = date_inf.groups()[2]
            date = f"{dt_1}/{dt_2}/{dt_3}"
            return date

    date = date_inf.groups()[0]
    return date

def parse_exits(msg):
    pt1_v = parse_exits_vals(msg, "PT[1]?")
    pt2_v = parse_exits_vals(msg, "PT2")
    pt3_v = parse_exits_vals(msg, "PT3")
    sl_v = parse_exits_vals(msg, "SL(?: below)?")
    return pt1_v, pt2_v, pt3_v, sl_v

def parse_avg(msg):
    re_avg = re.compile("(?:avg[.]?|new average)[ ]*[$]*(\d+(?:\.\d+)?)", re.IGNORECASE)
    avg_inf = re_avg.search(msg.lower())
    if avg_inf is None:
        return None, None
    avg = float(avg_inf.groups()[-1])
    return avg, avg_inf.span()

def parse_exits_vals(msg, expr):
    re_comp= re.compile("\s" +expr + "[:]?[ ]*[$]*(\d*[\.]*[\d]*[%]?)(TS[\d+\.]*[%]?)?", re.IGNORECASE)
    exit_inf = re_comp.search(msg)

    if exit_inf is None:
        re_comp= re.compile("(\s" + expr.lower() + "[:]?[ ]*[$]*(\d*[\.]*[\d]*[%]?))", re.IGNORECASE)
        exit_inf = re_comp.search(msg)

        if exit_inf is None or exit_inf.groups()[-1] =='':
            return None
        elif "%" in exit_inf.groups()[-1]:
            return exit_inf.groups()[-1]
        return float(exit_inf.groups()[-1].replace("..", ""))
    exit_v = exit_inf.group(1) + (exit_inf.group(2) if exit_inf.group(2) else "")
    return exit_v

def parse_unit_amount(msg):
    act = parse_action(msg)
    Symbol, _ = parse_Symbol(msg, act)

    exprs = f"{act}\s+(\d+) {Symbol}"
    re_comp= re.compile(exprs, re.IGNORECASE)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None:
        return round(eval(amnt_inf.groups()[0]), 2)
    return

def parse_sell_ratio_amount(msg, asset):
    exprs = "(?:sold|sell) (\d\/\d)"
    re_comp= re.compile(exprs, re.IGNORECASE)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None:
        return round(eval(amnt_inf.groups()[0]), 2)

    exprs = "(?:sold|sell)(\d of \d)"
    re_comp= re.compile(exprs, re.IGNORECASE)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None:
        return round(eval(amnt_inf.groups()[0].replace(" of ", "/")), 2)

    exprs = "(?:sold|sell) (\d{1,2})%"
    re_comp= re.compile(exprs, re.IGNORECASE)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None:
        return round(float(amnt_inf.groups()[0])/100, 2)

    if any(subs in msg.lower() for subs in ["half off my remaining position", "selling half off"]):
        return 0.25

    if any(subs in msg.lower() for subs in ["sold half", "sold another half", "half"]):
        return 0.5

    exprs = "\((\d(?:\/| of )\d)\)"
    re_comp= re.compile(exprs)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None:
        return round(eval(amnt_inf.groups()[0].replace(" of ", "/")), 2)

    partial = ['scaling out', 'selling more', 'trimming more off', "selling some more", 'trim']
    if any([True if m in msg.lower() else False for m in partial]):
        return .25

    if "partial" in msg.lower():
        if asset == "stock":
            amnt = .33
        elif asset == "option":
            amnt = .5
    else:
        amnt = 1
    return amnt

def parse_risk(msg):
    risk = {'very high risk':"very high",
            'risk very high':"very high",
            'very risky':"very high",
            'risk high': "high",
            'high': "high",
            'lotto': "lotto",
            'risky': "medium",
            'yolo':"yolo"}
    risk_level = None
    if "BTO" in msg:
        for k, rsk in risk.items():
            if k in msg.lower():
                risk_level = rsk
                break
    return risk_level

def parse_exit_plan(order):
    exit_plan = {}
    for p in [f"PT{i}" for i in range (1,4)] + ["SL"]:
            exit_plan[p] = order.get(p)
    return exit_plan


def make_optionID(Symbol:str, expDate:str, strike=str, **kwarg):
    """
    date: "[M]M/[D]D" or "[M]M/[D]D/YY[YY]"
    """
    strike, opt_type = float(strike[:-1]), strike[-1]
    date_elms = expDate.split("/")
    date_frm = f"{int(date_elms[0]):02d}{int(date_elms[1]):02d}"
    if len(date_elms) == 2: # MM/DD, year = actual year
        year = str(datetime.today().year)[-2:]
        date_frm = date_frm + year
    elif len(date_elms) == 3:
        date_frm = date_frm + f"{int(date_elms[2][-2:]):02d}"

    # Strike in interger if no decimals
    if strike == int(strike):
        return f"{Symbol}_{date_frm}{opt_type}{int(strike)}"
    return f"{Symbol}_{date_frm}{opt_type}{strike}"


def parse_symbol(symbol:str):
    # symbol: APPL_092623P426
    match = re.match(r"^([A-Z]+)_(\d{2})(\d{2})(\d{2})([CP])((?:\d+)(?:\.\d+)?)", symbol)

    if match:
        option ={
            "symbol": match.group(1),
            "exp_month": int(match.group(2)),
            "exp_day": int(match.group(3)),
            "exp_year": 2000+int(match.group(4)),
            "put_or_call": match.group(5),
            "strike": eval(match.group(6))
            }
        return option

def parse_option_under(symbol:str):
    # symbol: APPL_092623P426
    match = re.match(r"^([A-Z]+)_(\d{2})(\d{2})(\d{2})([CP])((?:\d+)(?:\.\d+)?)", symbol)

    if match:
        option ={
            "symbol": match.group(1),
            "exp_month": int(match.group(2)),
            "exp_day": int(match.group(3)),
            "exp_year": 2000+int(match.group(4)),
            "put_or_call": match.group(5),
            "strike": eval(match.group(6))
            }
        return option

    # try matching stock symbol: AAPL
    match = re.match(r"^([A-Z]+)", symbol)
    if match:
        stock = {
            "symbol": match.group(1),
        }
        return stock
