#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  8 18:11:55 2021

@author: adonay
"""
import re
from place_order import make_optionID
import pandas as pd

def option_alerts_parser(msg):
    # if not '@everyone' in msg:
    #     str_prt = "not an alert"
    #     print(str_prt)
    #     return str_prt, None

    act = parse_action(msg)
    if act is None:
        return None, None

    Symbol = parse_Symbol(msg, act)
    if Symbol is None:
        return None, None
    
    expDate = parse_date(msg)
    
    strike, optType = parse_strike(msg)

    mark = parse_mark(msg)

    order = {"action": act,
             "Symbol": Symbol,
             "ticker": Symbol,
             "price": mark,
             "expDate": expDate,
             "strike" : strike + optType,        
             "asset": "option"
             }

    str_prt = f"{act} {Symbol} {expDate} {strike + optType} @{mark}"

    if act == "BTO":
        if "avg" in msg:
            avg_price = parse_avg(msg, Symbol)
            str_prt = str_prt + f"AVG to {avg_price} "
            order["avg"] = avg_price
        else:
            order["avg"] = None

        pt1_v, pt2_v, pt3_v, sl_v = parse_exits(msg)
        n_pts = 3 if pt3_v else 2 if pt2_v else 1 if pt1_v else 0
        pts_qty = set_pt_qts(n_pts)

        order["PT1"] =  set_exit_price_type(pt1_v, order)
        order["PT2"] = set_exit_price_type(pt2_v, order)
        order["PT3"] = set_exit_price_type(pt3_v, order)
        order["SL"] = set_exit_price_type(sl_v, order)
        order["n_PTs"] = n_pts
        order["PTs_Qty"] = pts_qty
        
        str_prt = str_prt + f' PT1:{order["PT1"]}, PT2:{order["PT2"]}, PT3:{order["PT3"]}, SL:{order["SL"] }'
        
    elif act == "STC":
        amnt = parse_sell_amount(msg)
        str_prt = str_prt + f" amount: {amnt}"
        order["xQty"] = amnt
    # print(str_prt)

    order['Symbol'] = make_optionID(**order)
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
        re_Symbol = re.compile(f"{act}[ ]+([A-Z]+)")
        Symbol_info = re_Symbol.search(msg)
        if Symbol_info is None:
            return None

    Symbol = Symbol_info.groups()[-1]
    # print ("Symbol: ", Symbol)
    return Symbol

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
            crx
            return None
        else:
            dt_1 = months.index(date_inf.groups()[0])
            dt_2 = date_inf.groups()[1]
            dt_3 = date_inf.groups()[2]
            date = f"{dt_1}/{dt_2}/{dt_3}"
            return date
        
    date = date_inf.groups()[0]
    return date
    
def parse_strike(msg):
    re_strike = re.compile("(\d+(?:\.\d+)?)[ ]?(C|c|P|p)")
    strike_inf = re_strike.search(msg)
    if strike_inf is None and "BTO" in msg:
        sym = parse_Symbol(msg, "BTO")
        re_strike = re.compile(f"{sym} (\d+(?:\.\d+)?)")
        strike_inf = re_strike.search(msg)             
        # if strike_inf is None: 
        #     return None, None
        return strike_inf.groups()[0] , "C"  
    
    if strike_inf is None: 
        return None, None   
    strike = strike_inf.groups()[0]
    optType = strike_inf.groups()[1].capitalize()
    return strike, optType

def parse_mark(msg):
    re_mark = re.compile("(?:@|at)[ ]*[$]?[ ]*([.]?\d+(?:\.\d+)?)")
    mark_inf = re_mark.search(msg)
    if mark_inf is None:
        date = parse_date(msg)
        re_mark = re.compile(f"{date}[ ]*[$]?[ ]*([.]?\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)
    mark = float(mark_inf.groups()[-1])
    return mark


def parse_exits(msg):
    pt1_v = parse_exits_vals(msg, "PT[1]?")
    pt2_v = parse_exits_vals(msg, "PT2")
    pt3_v = parse_exits_vals(msg, "PT3")
    sl_v = parse_exits_vals(msg, "SL")

    return pt1_v, pt2_v, pt3_v, sl_v

# (BTO|STC)[ ]*[\*]*([A-Z]+)[\*]*[ ]*(\d+[.\d+]?)

def parse_avg(msg, Symbol):
    re_avg = re.compile("avg[ ]*[$]*(\d+(?:\.\d+)?)")
    avg_inf = re_avg.search(msg)
    if avg_inf is None:
        return None
    avg = float(avg_inf.groups()[-1])
    return avg

def parse_exits_vals(msg, expr):
    re_comp= re.compile("(" + expr + "[:]?[ ]*[$]*(\d+[\.]*[\d]*))")
    exit_inf = re_comp.search(msg)
    
    if exit_inf is None:
        re_comp= re.compile("(" + expr.lower() + "[:]?[ ]*[$]*(\d+[\.]*[\d]*))")
        exit_inf = re_comp.search(msg)
        
        if exit_inf is None:
            return None
        
    exit_v = float(exit_inf.groups()[-1])
    return exit_v


def parse_sell_amount(msg):
    
    exprs = "(?:sold|sell) (\d\/\d)"    
    re_comp= re.compile(exprs)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None: 
        return round(eval(amnt_inf.groups()[0]), 2)
        
    exprs = "(?:sold|sell)(\d of \d)"    
    re_comp= re.compile(exprs)
    amnt_inf = re_comp.search(msg)
    if amnt_inf is not None: 
        return round(eval(amnt_inf.groups()[0].replace(" of ", "/")), 2)
    
    if any(subs in msg.lower() for subs in ["sold half", "sold another half", "half"]): 
        return 0.5
    
      
    
    if "partial" in msg.lower():
        amnt = .33
    else:
        amnt = 1
    return amnt


if __name__ == "__main__":


    file = 'Xtrades.net - 🔹Stock-Trading🔸 - 🔹stock-alerts🔹 [592829298038276096].csv'

    alerts = pd.read_csv(file)
    alerts.drop(labels=['Attachments', 'Reactions'], axis=1, inplace=True)

    authors = alerts["Author"].unique()
    author = 'ScaredShirtless#0001'

    alerts_author = alerts[alerts["Author"].str.contains(author)]


    alerts_author = alerts_author.dropna(subset=["Content"])
    alerts_author.reset_index(drop=True, inplace=True)
    alerts_author.loc[:,"Parsed"] ="Nan"

    for i in range(len(alerts_author)):
        msg = alerts_author["Content"].iloc[i]
        pars, order =  parser_alerts(msg)
        alerts_author.loc[i, "Parsed"] = pars

    alerts_author.to_csv("alerts_author_parsed.csv")