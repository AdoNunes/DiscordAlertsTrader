import pandas as pd
import re
import numpy as np
import os.path as op
from message_parser import parser_alerts

def get_author_alerts():
    file = 'data/stock_alerts_message_history_2021.csv'

    alerts = pd.read_csv(file)
    alerts.drop(labels=['Attachments', 'Reactions'], axis=1, inplace=True)

    authors = alerts["Author"].unique()
    author = 'ScaredShirtless#0001'

    # author = "Kevin Wan#0083"

    alerts_author = alerts[alerts["Author"].str.contains(author)]


    alerts_author = alerts_author.dropna(subset=["Content"])
    alerts_author.reset_index(drop=True, inplace=True)

    return alerts_author


def trader(order, trades_log):

    openTrade = find_open_trade(order, trades_log)

    if openTrade is None and order["action"] == "BTO":
        trades_log, str_act = make_BTO(order, trades_log)

    elif order["action"] == "BTO" and order['avg'] is not None:
        trades_log, str_act = make_BTO_Avg(order, trades_log, openTrade)

    elif order["action"] == "BTO":
        str_act = "Repeated BTO"

    elif order["action"] == "STC" and openTrade is None:
        str_act = "STC without BTO"

    elif order["action"] == "STC":
        trades_log, str_act = make_STC(order, trades_log, openTrade)

    print(str_act)
    return trades_log, str_act


def find_open_trade(order, trades_log):
    if len(trades_log) == 0:
        return None

    msk_symbol = trades_log["Symbol"].str.contains( order['Symbol'])
    if sum(msk_symbol) == 0:
       return None

    symbol_trades = trades_log[msk_symbol]
    sold_Qty =  symbol_trades[[f"STC{i}-Qty" for i in range(1,4)]].sum(1)
    open_trade = sold_Qty< .99

    if sum(open_trade) == 0:
       return None

    if sum(open_trade)> 1:
       raise "Traded more than once open"
    open_trade, = open_trade[open_trade].index.values
    return open_trade


def make_BTO(order, trades_log):

    PTs = [order["PT1"], order["PT2"], order["PT3"]]
    Qts = order["PTs_Qty"]

    planned = [[PTs[i], Qts[i]] for i in range(order['n_PTs'])]

    trades_log = trades_log.append({
        "BTO-Date": order['date'],
        "Symbol" : order['Symbol'],
        "BTO": order['price'],
        "Planned_PTs": planned,
        "Planned_SL": order['SL']
        }, ignore_index=True)
    str_act = f"BTO {order['Symbol']}  {order['price']}, Plan PT:{planned}, SL:{order['SL']} %"

    return trades_log, str_act


def make_BTO_Avg(order, trades_log, openTrade):

    current_Avg = trades_log.loc[openTrade, "BTO-avg"]
    if np.isnan(current_Avg):
        current_Avg = 1
        trades_log.loc[openTrade, "BTO-avg"] = current_Avg
    else:
        current_Avg = int(current_Avg + 1)
        trades_log.loc[openTrade, "BTO-avg"] = current_Avg


    str_act =f"BTO {order['Symbol']} {current_Avg}th averging down @ {order['price']}"

    trades_log.loc[openTrade, "BTO"] = order["avg"]

    planned = trades_log.loc[openTrade, "Planned_PTs"]
    for i in range(1, order['n_PTs']+1):
        pt_Str = order[f'PT{i}']
        str_act = str_act + f" update PL{i}: {pt_Str}"
        planned[i-1][0] = pt_Str
    trades_log.loc[openTrade, "Planned_PTs"] = [planned]

    if order["SL"] is not None:
        trades_log.loc[openTrade, "Planned_SL"] = order["SL"]
        str_act = str_act + f" update SL: {order['SL']}"

    return trades_log, str_act


def make_STC(order, trades_log, openTrade):

    if np.isnan(trades_log.loc[openTrade, "STC1"]):
        STC = "STC1"
    elif np.isnan(trades_log.loc[openTrade, "STC2"]):
        STC = "STC2"
    elif np.isnan(trades_log.loc[openTrade, "STC3"]):
        STC = "STC3"
    else:
        str_STC = "How many STC already?"
        # print (str_STC)
        return trades_log, str_STC

    # reap, str_STC = check_repeat_STC(order, trades_log, openTrade, STC)
    # if reap:
    #     return trades_log, str_STC

    bto_price = trades_log.loc[openTrade, "BTO"]
    stc_price = float((order["price"] - bto_price)/bto_price) *100

    trades_log.loc[openTrade, STC] = order["price"]
    trades_log.loc[openTrade, STC + "-Date"] = order["date"]
    trades_log.loc[openTrade, STC + "-Qty"] = order['Qty']
    trades_log.loc[openTrade, STC + "-PnL"] = stc_price

    str_STC = f"{STC} {order['Symbol']}  ({order['Qty']}), {stc_price:.2f}%"

    Qty_sold = trades_log.loc[openTrade,[f"STC{i}-Qty" for i in range(1,4)]].sum()
    if order['Qty'] == 1 or Qty_sold > .98:
        trades_log.loc[openTrade, "Open"] = 0
        str_STC = str_STC + " Closed"

    # print(str_STC)
    return trades_log, str_STC


def check_repeat_STC(order, trades_log, openTrade, STC):

    STC_prev = [trades_log.loc[openTrade, f"STC{i}"] for i in range(1, 4)]

    if order["price"] in STC_prev:
        rep_ix = [i for i, v in enumerate(STC_prev) if v == order["price"]]
        str_STC = f"Repeated STC{rep_ix} order"
        return True, str_STC
    else:
        return False, None


trade_log_file = "data/trade_history.csv"

# if op.exists(trade_log_file):
#     trades_log = pd.read_csv(trade_log_file)
# else:
trades_log = pd.DataFrame(columns = ["BTO-Date", "Symbol", "Open", "BTO", "BTO-avg",
                                         "Planned_PTs", "Planned_SL",
                                         "STC1", "STC1-Qty", "STC1-PnL","STC1-Date",
                                         "STC2", "STC2-Qty", "STC2-PnL","STC2-Date",
                                         "STC3", "STC3-Qty", "STC3-PnL","STC3-Date",])
    # trades_log.to_csv(trade_log_file, index=False)

alerts_author = get_author_alerts()
alerts_author["parsed"] = "nan"
alerts_author["trade_act"] = "nan"

# from disc_trader import portfolio

# self = portfolio()
bad_msg = []
for i in range(len(alerts_author)):
    msg = alerts_author["Content"].iloc[i]
    msg = msg.replace("~~2.99~~", "")
    trade_date = alerts_author["Date"].iloc[i]
    pars, order =  parser_alerts(msg)
    if order  is None:
        continue
    order['Trader'] = alerts_author["Author"].iloc[i]
    # if order['Symbol'] == "DPW":
    #     self.notify_alert(order, pars)

    alerts_author.loc[i, "parsed"] = pars

    # if "reached pre-market" in msg:
    #     alerts_author.loc[i, "parsed"] = "pre-market repeated alert"
    #     continue

    if order['price'] is None:
        bad_msg.append((msg, trade_date))
        continue

    order["date"] = trade_date
    trades_log, str_act = trader(order, trades_log)

    alerts_author.loc[i,"trade_act"] = str_act

alerts_author.to_csv("data/alerts_author_parsed.csv")
trades_log.to_csv(trade_log_file)


