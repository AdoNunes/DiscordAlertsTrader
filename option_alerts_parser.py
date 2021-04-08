import pandas as pd
import re
import numpy as np
import os.path as op
from message_parser import parser_alerts, auhtor_parser, get_symb_prev_msg
from place_order import make_optionID


def get_author_option_alerts():
    file = 'data/option_alerts_message_history.csv'

    alerts = pd.read_csv(file)
    alerts.drop(labels=['Attachments', 'Reactions'], axis=1, inplace=True)

    authors = alerts["Author"].unique()
    author = 'Xtrades Option Guru'

    # author = "Kevin Wan#0083"

    alerts_author = alerts[alerts["Author"].str.contains(author)]


    alerts_author = alerts_author.dropna(subset=["Content"])
    alerts_author.reset_index(drop=True, inplace=True)

    return alerts_author, author


def option_trader(order, trades_log):

    order["Symbol"] = make_optionID(**order)

    openTrade = find_open_option(order, trades_log)

    if openTrade is None and order["action"] == "BTO":
        trades_log, str_act = make_BTO_option(order, trades_log)
        openTrade = find_open_option(order, trades_log)

    elif order["action"] == "BTO" and order['avg'] is not None:
        trades_log, str_act = make_BTO_option_Avg(order, trades_log, openTrade)

    elif order["action"] == "BTO":
        str_act = "Repeated BTO"

    elif order["action"] == "STC" and openTrade is None:
        str_act = "STC without BTO"

    elif order["action"] == "STC":
        trades_log, str_act = make_STC_option(order, trades_log, openTrade)

    print(str_act)
    return trades_log, str_act, openTrade


def find_open_option(order, trades_log):
    if len(trades_log) == 0:
        return None

    msk_symbol = trades_log["Symbol"].str.contains(order['Symbol'])
    if sum(msk_symbol) == 0:
       return None

    symbol_trades = trades_log[msk_symbol]
    sold_Qty =  symbol_trades[[f"STC{i}-xQty" for i in range(1,2)]].sum(1)
    open_trade = sold_Qty< .99

    if sum(open_trade) == 0:
       return None

    if sum(open_trade)> 1:
       raise "Traded more than once open"
    open_trade, = open_trade[open_trade].index.values
    return open_trade


def make_BTO_option(order, trades_log):

    PTs = [order["PT1"], order["PT2"], order["PT3"]]
    Qts = order["PTs_Qty"]

    planned = [[PTs[i], Qts[i]] for i in range(order['n_PTs'])]

    sl_mental = True if "mental" in msg.lower() else False

    trades_log = trades_log.append({
        "BTO-Date": order['date'],
        "Symbol" : order['Symbol'],
        "BTO": order['price'],
        "Strike" : order['strike'],
        "ExpDate" : order['expDate'],
        "Planned_PT": planned,
        "Planned_SL": order['SL'],
        "SL_mental" : sl_mental,
        "Risk": order['risk']
        }, ignore_index=True)
    str_act = f"BTO {order['Symbol']} {order['price']} {order['expDate']} {order['strike']}, Plan PT:{order['PT1']}, SL:{order['SL']}"

    return trades_log, str_act


def make_BTO_option_Avg(order, trades_log, openTrade):

    current_Avg = trades_log.loc[openTrade, "BTO-avg"]
    if np.isnan(current_Avg):
        current_Avg = 1
        trades_log.loc[openTrade, "BTO-avg"] = current_Avg
    else:
        current_Avg = int(current_Avg + 1)
        trades_log.loc[openTrade, "BTO-avg"] = current_Avg


    str_act =f"BTO {order['Symbol']} {current_Avg}th averging down @ {order['price']}"

    trades_log.loc[openTrade, "BTO"] = order["avg"]

    planned = trades_log.loc[openTrade, "Planned_PT"]

    PTs = [order["PT1"], order["PT2"], order["PT3"]]
    Qts = order["PTs_Qty"]
    planned = [[PTs[i], Qts[i]] for i in range(order['n_PTs'])]

    if len(planned):
        trades_log.loc[openTrade, "Planned_PT"] = [planned]

    if order["SL"] is not None:
        trades_log.loc[openTrade, "Planned_SL"] = order["SL"]
        str_act = str_act + f" update SL: {order['SL']}"

    return trades_log, str_act


def make_STC_option(order, trades_log, openTrade):

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

    if order.get("amnt_left"):
        left = order["amnt_left"]
        if left == "few":
            order['xQty'] =  .1
        elif left > .99:  # unit left
            order['xQty'] =  .05
        elif left < .99:  # percentage left
            order['xQty'] = left

    trades_log.loc[openTrade, STC] = order["price"]
    trades_log.loc[openTrade, STC + "-Date"] = order["date"]
    trades_log.loc[openTrade, STC + "-xQty"] = order['xQty']
    trades_log.loc[openTrade, STC + "-PnL"] = stc_price

    str_STC = f"{STC} {order['Symbol']}  ({order['xQty']}), {stc_price:.2f}%"

    Qty_sold = trades_log.loc[openTrade,[f"STC{i}-xQty" for i in range(1,4)]].sum()
    if order['xQty'] == 1 or Qty_sold > .98:
        trades_log.loc[openTrade, "Open"] = 0
        str_STC = str_STC + " Closed"

    return trades_log, str_STC


def check_repeat_STC(order, trades_log, openTrade, STC):

    STC_prev = [trades_log.loc[openTrade, f"STC{i}"] for i in range(1, 4)]

    if order["price"] in STC_prev:
        rep_ix = [i for i, v in enumerate(STC_prev) if v == order["price"]]
        str_STC = f"Repeated STC{rep_ix} order"
        return True, str_STC
    else:
        return False, None



alerts_author, author = get_author_option_alerts()
alerts_author["parsed"] = "nan"
alerts_author["trade_act"] = "nan"


trade_log_file = f"data/options_portfolio_history_{author}.csv"

# if op.exists(trade_log_file):
#     trades_log = pd.read_csv(trade_log_file)
# else:
trades_log = pd.DataFrame(columns = ["BTO-Date", "Symbol", "Open", "BTO",
                                     "Strike", "ExpDate", "BTO-avg",
                                     "Planned_PT", "Planned_SL",
                                     "STC1", "STC1-xQty", "STC1-PnL","STC1-Date",
                                     "STC2", "STC2-xQty", "STC2-PnL","STC2-Date",
                                     "STC3", "STC3-xQty", "STC3-PnL","STC3-Date",
                                     "Total PnL", "Portfolio_inx"])
    # trades_log.to_csv(trade_log_file, index=False)




bad_msg = []
not_msg = pd.DataFrame(columns=["MSG"])
for i in range(1,len(alerts_author)):
    msg = alerts_author["Content"].iloc[i]
    msg = msg.replace("~~2.99~~", "")
    trade_date = alerts_author["Date"].iloc[i]
    print("\n")
    print(f"msg {i}: ", msg)
    pars, order =  parser_alerts(msg, 'option')
    print(order)

    # if "reached pre-market" in msg:
    #     alerts_author.loc[i, "parsed"] = "pre-market repeated alert"
    #     continue
    author = alerts_author["Author"].iloc[i].split("#")[0]
    new_order = auhtor_parser(msg, order, author)

    if new_order is None:
        continue

    if new_order.get("Symbol") ==  None:
        symbol, prev_msg_inx = get_symb_prev_msg(alerts_author, i, author)
        # new_order["Symbol"] = symbol
    else:
        symbol, prev_msg_inx = None, None


    if symbol is not None:
        print("NEW: ", new_order)
        print(f"Symb {symbol} from: ", alerts_author.loc[prev_msg_inx, "Content"])
        resp = input("press o to stop")
        if resp == "o":
            print(f"stopped at {i}")
            break

    if order  is None:
        not_msg = not_msg.append({"MSG":msg}, ignore_index=True)
        continue

    order["uQty"] = 3
    alerts_author.loc[i, "parsed"] = pars
    order['Trader'] = alerts_author["Author"].iloc[i]

    # order['Trader'] = alerts_author["Author"].iloc[i]
    # if order['Symbol'] == "DPW":
    #     crh

    if order['price'] is None:
        bad_msg.append((msg, trade_date))
        continue

    order["date"] = trade_date
    trades_log, str_act, trade_ix = option_trader(order, trades_log)

    alerts_author.loc[i,"trade_act"] = str_act
    alerts_author.loc[i, "Portfolio_inx"] = trade_ix

alerts_author.to_csv(f"data/option_alerts_parsed_{author}.csv")
trades_log.to_csv(trade_log_file)

not_msg.to_csv(f"data/not_understood_{author}.csv")



Exits = not_msg[not_msg["MSG"].str.contains("target|stop")]

not_msg_exit = not_msg[~not_msg["MSG"].str.contains("target|stop")]
not_msg_exit.to_csv(f"data/not_understood_notexit_{author}.csv")


