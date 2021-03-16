#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  8 18:11:55 2021

@author: adonay
"""
import re

def parser_alerts(msg):
    if not '@everyone' in msg:
        str_prt = "not an alert"
        print(str_prt)
        return str_prt, None

    act = parse_action(msg)
    if act is None:
        return None, None

    Symbol, Symbol_info = parse_Symbol(msg, act)
    if Symbol is None:
        return None, None

    mark, mark_info = parse_mark(msg, Symbol, act)

    order = {"action": act,
             "Symbol": Symbol,
             "price": mark
             }

    str_prt = f"{act} {Symbol} @{mark} "
    if act == "BTO":
        if "avg" in msg:
            avg_price, _ = parse_avg(msg, Symbol)
            str_prt = str_prt + f"AVG to {avg_price} "
            order["avg"] = avg_price
        else:
            order["avg"] = None

        pt1_v, pt2_v, pt3_v, sl_v = parse_exits(msg)
        str_prt = str_prt + f"PT1:{pt1_v}, PT2:{pt2_v}, PT3:{pt3_v}, SL:{sl_v}"
        n_pts = 3 if pt3_v else 2 if pt2_v else 1 if pt1_v else 0
        pts_qty = set_pt_qts(n_pts)

        order["PT1"] = pt1_v
        order["PT2"] = pt2_v
        order["PT3"] = pt3_v
        order["SL"] = sl_v
        order["n_PTs"] = n_pts
        order["PTs_Qty"] = pts_qty

    elif act == "STC":
        amnt = parse_sell_amount(msg)
        str_prt = str_prt + f" amount: {amnt}"
        order["xQty"] = amnt
    print(str_prt)


    return str_prt, order

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
            return None, None

    Symbol = Symbol_info.groups()[-1]
    # print ("Symbol: ", Symbol)
    return Symbol, Symbol_info.span()


def parse_mark(msg, Symbol, act):
    re_mark = re.compile("\@[ ]*[$]*[ ]*(\d+(?:\.\d+)?)")
    mark_inf = re_mark.search(msg)
    if mark_inf is None:
        re_mark = re.compile(f"{act} "+ "([\*])?([\*])?" + f"{Symbol}" +"([\*])?([\*])? (\d+(?:\.\d+)?)")
        mark_inf = re_mark.search(msg)
        if mark_inf is None:
            return None, None
    mark = float(mark_inf.groups()[-1])
    return mark, mark_inf.span()


def parse_exits(msg):
    pt1_v, exit_info = parse_exits_vals(msg, "PT[1]?:")
    pt2_v, exit_info = parse_exits_vals(msg, "PT2:")
    pt3_v, exit_info = parse_exits_vals(msg, "PT3:")
    sl_v, sl_info = parse_exits_vals(msg, "SL:")

    return pt1_v, pt2_v, pt3_v, sl_v



def parse_avg(msg, Symbol):
    re_avg = re.compile("avg[ ]*[$]*(\d+(?:\.\d+)?)")
    avg_inf = re_avg.search(msg)
    if avg_inf is None:
        return None, None
    avg = float(avg_inf.groups()[-1])
    return avg, avg_inf.span()

def parse_exits_vals(msg, expr):
    re_comp= re.compile("(" + expr + "[ ]*[$]*(\d+[\.]*[\d]*))")
    exit_inf = re_comp.search(msg)
    if exit_inf is None:
        return None, None
    exit_v = float(exit_inf.groups()[-1])
    return exit_v, exit_inf


def parse_sell_amount(msg):
    if "partial" in msg:
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