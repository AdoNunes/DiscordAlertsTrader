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

def parser_alerts(msg, asset=None):
    msg = msg.replace("STc", "STC").replace("StC", "STC").replace("stC", "STC").replace("STc", "STC")
    msg = msg.replace("BtO", "BTO").replace("btO", "BTO").replace("bTO", "BTO").replace("BTo", "BTO")
    msg = msg.replace("spx", "SPX").replace("spy", "SPY").replace("Spx", "SPX")
    act = parse_action(msg)
    if act is None:
        if "ExitUpdate" in msg:
            order = {}
            order['action'] = "ExitUpdate"
            order['Symbol'], _ = parse_Symbol(msg, "ExitUpdate")
            pars = f"ExitUpdate: "
            if asset == "option":
                if "_" not in  order['Symbol']:
                    strike, optType = parse_strike(msg)
                    order["expDate"] = parse_date(msg)
                    order["strike"] = strike + optType
                    order['Symbol'] = make_optionID(**order)
            order, str_prt = make_order_exits(order, msg, pars, "stock") # price type dealt in disc_trader
            return pars, order
        return None, None
    
    Symbol, Symbol_info = parse_Symbol(msg, act)
    if Symbol is None:
        return None, None

    if asset != "stock":
        strike, optType = parse_strike(msg)
        if asset is None:
            asset="option" if strike is not None else "stock"
        elif asset == "option" and strike is None:
            return None, None

    if asset == "option":
        expDate = parse_date(msg)
        if expDate is None:
            return None, None

        mark = parse_mark_option(msg)

    elif asset == "stock":
        mark  = parse_mark_stock(msg, Symbol, act)

    amnt = parse_unit_amount(msg)
    risk_level = parse_risk(msg)

    order = {"action": act,
             "Symbol": Symbol,
             "price": mark,
             "asset": asset,
             "uQty": amnt,
             "risk": risk_level}

    str_prt = f"{act} {Symbol} @{mark} amount: {amnt}"

    if asset == "option":
        if Symbol == "SPX": 
            order['Symbol'] = "SPXW"
        elif Symbol == "NDX":
            order['Symbol'] = "NDXP"
        optType = optType.upper()
        order["expDate"] = expDate
        order["strike"] = strike + optType
        str_prt = f"{act} {order['Symbol']} {expDate} {strike + optType} @{mark} amount: {amnt}"
        order['Symbol'] = make_optionID(**order)

    if act == "BTO":
        if "avg" in msg.lower() or "average" in msg.lower():
            avg_price, _ = parse_avg(msg)
            str_prt = str_prt + f"AVG to {avg_price} "
            order["avg"] = avg_price
        else:
            order["avg"] = None

        pt1_v, pt2_v, pt3_v, sl_v = parse_exits(msg)
        n_pts = 3 if pt3_v else 2 if pt2_v else 1 if pt1_v else 0
        pts_qty = set_pt_qts(n_pts)
        order, str_prt = make_order_exits(order, msg, str_prt, asset)
        sl_mental = True if "mental" in msg.lower() else False
        if sl_mental: order["SL_mental"] = True
        order["n_PTs"] = n_pts
        order["PTs_Qty"] = pts_qty

    elif act == "STC":
        xamnt = parse_sell_ratio_amount(msg, asset)
        if order["uQty"] is None:
            str_prt = str_prt + f" xamount: {xamnt}"
        order["xQty"] = xamnt
    return str_prt, order

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
    if isinstance(exit_price, str): exit_price = eval(exit_price)

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
            for wrd in ["I", "ATH", "BTO", "STC", "ITM"]:
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
    re_comp= re.compile("(" + expr + "[:]?[ ]*[$]*(\d+[\.]*[\d]*))", re.IGNORECASE)
    exit_inf = re_comp.search(msg)

    if exit_inf is None:
        re_comp= re.compile("(" + expr.lower() + "[:]?[ ]*[$]*(\d+[\.]*[\d]*))")
        exit_inf = re_comp.search(msg)

        if exit_inf is None:
            return None

    exit_v = float(exit_inf.groups()[-1].replace("..", ""))
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

    partial = ['scaling out', 'selling more', 'trimming more off', "selling some more"]
    if any([True if m in msg.lower() else False for m in partial]):
        return .33

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
            'high risk': "high",
            'lotto': "very high",
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

def auhtor_parser(msg, author, asset):
    if author not in ['ScaredShirtless#0001', 'Kevin (Momentum)#4441']:
        new_order = {}
        def stc_amount(msg):
            ######### Leave N untis
            units = ["one", "two", "three"]
            units_left = f'(?:(?:L|l)eaving|leave)[ ]*(?:only|just)?[ ]*({"|".join(units)})'
            mtch = re.compile(units_left, re.IGNORECASE)
            mtch = mtch.search(msg)
            if mtch is not None:
                strnum = mtch.groups()[0]
                qty_left, = [i for i, v in enumerate(units) if v==strnum]
                return qty_left

            ######### Leave a few untis
            left_few = '(?:(?:L|l)eaving|leave)[ ]*(?:only|just)?[ ]*[a]? (few)'
            mtch = re.compile(left_few, re.IGNORECASE)
            mtch = mtch.search(msg)
            if mtch is not None:
                return "few"

            ######### Leave % amount
            left_perc = '(?:(?:L|l)eaving|leave) (?:about|only)?[ ]*(\d{1,2})%'
            mtch = re.compile(left_perc, re.IGNORECASE)
            mtch = mtch.search(msg)
            if mtch is not None:
                perc = mtch.groups()[0]
                return eval(perc)/100

            return None

        def match_exp(exp, msg):
            mtch = re.compile(exp, re.IGNORECASE)
            mtch = mtch.search(msg)
            if mtch is not None:
                return mtch.groups()[0]
            return None

        # in STC target might not be PT2
        if "STC" not in msg:
            pt1_exps = ['Target: (\d+[\.]*[\d]*)', 'target: (\d+[\.]*[\d]*)', 'target[a-zA-Z\s\,\.]*(\d+[\.]*[\d]*)',
                   '(\d+[\.]*[\d]*)[a-zA-Z\s\,\.]*target',
                   'looking for (\d+[\.]*[\d]*)']
            for exp in pt1_exps:
                pt1 = match_exp(exp, msg)
                if pt1:
                    pt1 = pt1[:-1] if pt1[-1] == '.' else pt1
                    new_order["PT1"] = pt1
                    msg = msg.replace(pt1, " ")
                    break

            pt2 = "target[a-zA-Z0-9\.\s\,]*then (\d+[\.]*[\d]*)"
            pt2 = match_exp(pt2, msg)
            if pt2:
                pt2 = pt2[:-1] if pt2[-1] == '.' else pt2
                new_order["PT2"] = pt2
                msg = msg.replace(pt2, " ")
        else:
            pt2 = "second target[a-zA-Z0-9\.\s\,]*(\d+[\.]*[\d]*)"
            pt2 = match_exp(pt2, msg)
            if pt2:
                new_order["PT2"] = pt2
                msg = msg.replace(pt2, " ")

        sl_exps = ['Stop: (\d+[\.]*[\d]*)', 'stop: (\d+[\.]*[\d]*)', '(\d+[\.]*[\d]*)[a-zA-Z\s\,\.]{0,5}?stop',
                   'stop[a-zA-Z\s\,\.]*(\d+[\.]*[\d]*)']
        for exp in sl_exps:
            sl = match_exp(exp, msg)
            if sl:
                sl = sl[:-1] if sl[-1] == '.' else sl
                new_order["SL"] = sl
                break

        if "BTO" not in msg:
            amnt_left = stc_amount(msg)
            if amnt_left:
                new_order["amnt_left"] = amnt_left

            if "STC" not in msg:
                stc = "([^a-z]selling|[^a-z]sold|all out|(:?(out|took)[a-zA-Z\s]*last)|sell here|took some off)"
                mtch = re.compile(stc, re.IGNORECASE)
                mtch = mtch.search(msg)
                no_Sell = ["not selling yet", "Over Sold", "contracts sold", "How many sold it?", 'No need to ask me if I’m selling']
                if mtch is not None and not any([True if s in msg else False for s  in no_Sell]):
                    new_order['action'] = "STC"
                    new_order["xQty"]  = parse_sell_ratio_amount(msg, asset)

        if len(list(new_order.values())):
            symbol, _ = parse_Symbol(msg, parse_action(msg))
            if symbol:
                new_order["Symbol"] = symbol
            return new_order
        else:
            return None
    return None

def get_symb_prev_msg(df_hist, msg_ix, author):
    # df_hist["Author"]  = df_hist["Author"].apply(lambda x: x.split("#")[0])

    df_hist_auth = df_hist[df_hist["Author"]==author]
    msg_inx_auth, = np.nonzero(df_hist_auth.index == msg_ix)
    indexes = df_hist_auth.index.values

    for n in range(1,6):
        inx = indexes[msg_inx_auth - n]
        msg, = df_hist_auth.loc[inx, 'Content'].values
        if pd.isnull(msg):
            continue
        symbol, _ = parse_Symbol(msg, parse_action(msg))
        if symbol is not None:
            return symbol, inx
    return None, None

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
    if strike == int(strike):
        return f"{Symbol}_{date_frm}{opt_type}{int(strike)}"
    return f"{Symbol}_{date_frm}{opt_type}{strike}"

def combine_new_old_orders(msg, order_old, pars, author, asset="option"):
    order_author = auhtor_parser(msg, author, asset)
    if order_author is None:
        return order_old, pars

    if order_old is not None:
        for k in order_author.keys():
            # If
            if order_author[k] == order_old.get(k) and k != "Symbol" or \
                order_author[k] != order_old.get(k) and k == "Symbol":
                if k == "Symbol":
                    # in case of ticker vs option symbol ID
                    if order_author[k] == order_old[k][:len(order_author[k])]:
                        order_author[k] = order_old[k]
                        continue
                resp = input(f"Found diff vals for {k}: new= {order_author[k]}, old= {order_old[k]} " +
                             "[1- new, 2- old, 0- break and fix]")
                if resp == '2':
                    order_author[k] = order_old.get(k)
                elif resp == '0':
                    raise "error"
        order = {**order_old, **order_author}
    else:
        order = order_author

    if order.get("action") is None:
        order["asset"] = asset
        exits = ["PT1", "PT2", "PT3", "SL"]
        if any([order.get(k) for k in exits]):
            order['action'] = "ExitUpdate"
            pars = f"ExitUpdate: {pars}"
            for ex in exits:
                val = order.get(ex)
                if val is not None:
                    pars = pars + f" {ex}:{val},"
    return order, pars