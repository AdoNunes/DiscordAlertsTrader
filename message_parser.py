#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  8 18:11:55 2021

@author: adonay
"""
import re
import pandas as pd
from place_order import make_optionID

def parser_alerts(msg, asset=None):
    # if not '@everyone' in msg:
    #     str_prt = "not an alert"
    #     print(str_prt)
    #     return str_prt, None

    act = parse_action(msg)
    if act is None:
        return None, None

    Symbol, Symbol_info = parse_Symbol(msg, act)
    if Symbol is None:
        return None, None

    if asset != "stock":
        strike, optType = parse_strike(msg)
        optType = optType.upper()
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
        mark,  = parse_mark_stock(msg, Symbol, act)

    order = {"action": act,
             "Symbol": Symbol,
             "price": mark,
             "asset": asset
             }
    
    str_prt = f"{act} {Symbol} @{mark} "

    if asset == "option":
        order["expDate"] = expDate
        order["strike"] = strike + optType
        str_prt = f"{act} {Symbol} {expDate} {strike + optType} @{mark}"
        order['Symbol'] = make_optionID(**order)
        
    
    if act == "BTO":
        if "avg" in msg or "average" in msg:
            avg_price, _ = parse_avg(msg)
            str_prt = str_prt + f"AVG to {avg_price} "
            order["avg"] = avg_price
        else:
            order["avg"] = None

        pt1_v, pt2_v, pt3_v, sl_v = parse_exits(msg)
        n_pts = 3 if pt3_v else 2 if pt2_v else 1 if pt1_v else 0
        pts_qty = set_pt_qts(n_pts)

        if asset == "option":
            order["PT1"] =  set_exit_price_type(pt1_v, order)
            order["PT2"] = set_exit_price_type(pt2_v, order)
            order["PT3"] = set_exit_price_type(pt3_v, order)
            order["SL"] = set_exit_price_type(sl_v, order)
            str_prt = str_prt + f' PT1:{order["PT1"]}, PT2:{order["PT2"]}, PT3:{order["PT3"]}, SL:{order["SL"] }'

        elif asset == "stock":
            order["PT1"] = pt1_v
            order["PT2"] = pt2_v
            order["PT3"] = pt3_v
            order["SL"] = sl_v
            str_prt = str_prt + f"PT1:{pt1_v}, PT2:{pt2_v}, PT3:{pt3_v}, SL:{sl_v}"
            
        order["n_PTs"] = n_pts
        order["PTs_Qty"] = pts_qty

    elif act == "STC":
        amnt = parse_sell_amount(msg, asset)
        str_prt = str_prt + f" amount: {amnt}"
        order["xQty"] = amnt
    print(str_prt)

    return str_prt, order


def set_exit_price_type(exit_price, order):
    """Option or stock price decided with smallest distance"""
    if exit_price is None:
        return exit_price
    
    price_strk = float(order['strike'][:-1])

    rtio_stock = abs(price_strk - exit_price)
    rtio_option = abs(order['price'] - exit_price) 
                             
    if rtio_stock < rtio_option:
        exit_price = str(exit_price) + 's'
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


# def parse_sl_up(msg):

#     if "stop loss up" in msg or "SL" in msg:
#         Symbol, Symbol_info = parse_Symbol(msg)

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
            for wrd in ["I", "ATH", "BTO", "STC", 'VWAP']:
                msg = msg.replace(wrd+" ", " ")
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
    re_mark = re.compile("\@[ ]*[$]*[ ]*(\d+(?:\.\d+)?)")
    mark_inf = re_mark.search(msg)
    if mark_inf is None:
        re_mark = re.compile(f"{act} "+ "([\*])?([\*])?" + f"{Symbol}" +"([\*])?([\*])? (\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)
        if mark_inf is None:
            return None, None
    mark = float(mark_inf.groups()[-1])
    return mark, mark_inf.span()


def parse_mark_option(msg):
    re_mark = re.compile("(?:@|at)[ ]*[$]?[ ]*([.]?\d+(?:\.\d+)?)")
    mark_inf = re_mark.search(msg)
    if mark_inf is None:
        date = parse_date(msg)
        re_mark = re.compile(f"{date}[ ]*[$]?[ ]*([.]?\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)
        if mark_inf is None:
            return None
    mark = float(mark_inf.groups()[-1])
    return mark


def parse_strike(msg):
    re_strike = re.compile(" [$]?(\d+(?:\.\d+)?)[ ]?(C|c|P|p)")
    strike_inf = re_strike.search(msg)
    if strike_inf is None and "BTO" in msg:
        sym = parse_Symbol(msg, "BTO")[0]
        re_strike = re.compile(f"{sym} (\d+(?:\.\d+)?)")
        strike_inf = re_strike.search(msg)             
        # if strike_inf is None: 
        #     return None, None
        return strike_inf.groups()[0], "C"
    
    if strike_inf is None: 
        return None, None   
    strike = strike_inf.groups()[0]
    optType = strike_inf.groups()[1].capitalize()
    return strike, optType

def parse_date(msg):
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
    pt1_v = parse_exits_vals(msg, "PT[1]?:")
    pt2_v = parse_exits_vals(msg, "PT2:")
    pt3_v = parse_exits_vals(msg, "PT3:")
    sl_v = parse_exits_vals(msg, "SL:")

    return pt1_v, pt2_v, pt3_v, sl_v



def parse_avg(msg):
    re_avg = re.compile("(?:avg|new average)[ ]*[$]*(\d+(?:\.\d+)?)", re.IGNORECASE)
    avg_inf = re_avg.search(msg.lower())
    if avg_inf is None:
        return None, None
    avg = float(avg_inf.groups()[-1])
    return avg, avg_inf.span()

def parse_exits_vals(msg, expr):
    re_comp= re.compile("(" + expr + "[:]?[ ]*[$]*(\d+[\.]*[\d]*))", re.IGNORECASE)
    exit_inf = re_comp.search(msg)

    if exit_inf is None:
        return None

    exit_v = float(exit_inf.groups()[-1])
    return exit_v


def parse_sell_amount(msg, asset):
    
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
    
    if any(subs in msg.lower() for subs in ["sold half", "sold another half", "half"]): 
        return 0.5
          
    
    exprs = "\((\d(?:\/| of )\d)\)"    
    re_comp= re.compile(exprs)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None: 
        return round(eval(amnt_inf.groups()[0].replace(" of ", "/")), 2)

    partial = ['scaling out', 'selling more', 'trimming more off']
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


def auhtor_parser(msg, order, author):
    
    new_order = {}
    if author == 'Xtrades Option Guru':
        
        def stc_amount(msg):
            ######### Leave N untis
            units = ["one", "two", "three"]            
            units_left = f'(?:leaving|leave)[ ]*(?:only )?[ ]*({"|".join(units)})'
            mtch = re.compile(units_left, re.IGNORECASE)
            mtch = mtch.search(msg)
            if mtch is not None:
                strnum = mtch.groups()[0]
                qty_left, = [i for i, v in enumerate(units) if v==strnum]
                return qty_left

            ######### Leave a few untis
            left_few = '(?:leaving|leave)[ ]*(?:only|just)?[ ]*[a]? (few)'
            mtch = re.compile(left_few, re.IGNORECASE)
            mtch = mtch.search(msg)
            if mtch is not None:
                return "few"
            
            ######### Leave % amount
            left_perc = '(?:leaving|leave) (?:about|only) (\d{1,2})%'
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
            pt1_exps = ['target[a-zA-Z\s\,\.]*(\d+[\.]*[\d]*)',
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

        sl_exps = ['(\d+[\.]*[\d]*)[a-zA-Z\s\,\.]*stop',
                   'stop[a-zA-Z\s\,\.]*(\d+[\.]*[\d]*)']
        for exp in sl_exps:
            sl = match_exp(exp, msg)
            if sl:
                sl = sl[:-1] if sl[-1] == '.' else sl
                new_order["SL"] = sl
                break
            
        sl_mental = True if "mental" in msg.lower() else False
        if sl_mental:
            new_order["SL_mental"] = True

        risk = ['very high risk', 'very risky', 'risk high', 'risky', 'yolo']
        risk_level = None
        if "BTO" in msg:
            for rsk in risk:
                if rsk in msg.lower():
                    risk_level = rsk
                    break
            if risk_level:
                new_order["risk"] = risk_level
                
        else:
            amnt_left = stc_amount(msg)
            if amnt_left:
                new_order["amnt_left"] = amnt_left
            
            if "STC" not in msg:
                stc = "([^a-z]selling|[^a-z]sold|all out|(:?(out|took)[a-zA-Z\s]*last))"
                mtch = re.compile(stc, re.IGNORECASE)
                mtch = mtch.search(msg)
                if mtch is not None:
                    new_order['act'] = "STC"

        if len(list(new_order.values())):
            symbol, _ = parse_Symbol(msg, parse_action(msg))
            if symbol:
                new_order["Symbol"] = symbol
            return new_order
        else:
            return None
