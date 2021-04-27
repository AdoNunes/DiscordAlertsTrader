import pandas as pd
import re
import numpy as np
import os.path as op
from message_parser import parser_alerts, auhtor_parser, get_symb_prev_msg, combine_new_old_orders
from place_order import make_optionID
from disc_trader import  find_last_trade
from config import (data_dir, CHN_NAMES, chn_IDS, UPDATE_PERIOD)


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


class Trades_Tracker():

    def __init__(self, TDSession=None,
                 portfolio_fname=data_dir + "/trade_tracker_portfolio.csv",
                 alerts_log_fname=data_dir + "/trade_tracker_logger.csv"):

        self.portfolio_fname = portfolio_fname
        self.alerts_log_fname = alerts_log_fname

        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=[
                "Date", "Symbol", "Trader", "isOpen", "BTO-Status", "Asset", "Type", "Price", "Alert-Price",
                "uQty", "filledQty", "Avged", "exit_plan", "ordID", "Risk", "SL_mental"] + [
                    "STC%d-%s"% (i, v) for v in
                    ["Alerted", "Status", "xQty", "uQty", "Price", "PnL","Date", "ordID"]
                    for i in range(1,4)] )

        if op.exists(self.alerts_log_fname):
            self.alerts_log = pd.read_csv(self.alerts_log_fname)
        else:
            self.alerts_log = pd.DataFrame(columns=["Date", "Symbol", "Trader",
                                                "action", "parsed", "msg", "portfolio_idx"])
        self.TDSession = TDSession


    def price_now(self, Symbol, price_type="BTO"):
        if self.TDsession is None:
            return None

        if price_type in ["BTO", "BTC"]:
            ptype = 'askPrice'
        else:
            ptype= 'bidPrice'
        try:
            quote = self.TDsession.get_quotes(
                instruments=[Symbol])[Symbol][ptype]
        except KeyError as e:
                print (Back.RED + f"price_now ERROR: {e}.\n Trying again later")
                quote = self.TDsession.get_quotes(
                instruments=[Symbol])[Symbol][ptype]

        return quote

        
    def trade_alert(self, order):

        openTrade, isOpen = find_last_trade(order, self.portfolio, open_only=True)

        if openTrade is None and order["action"] == "BTO":
            str_act = make_BTO_option(order, self.portfolio)
            openTrade, isOpen = find_last_trade(order, self.portfolio)
    
        elif order["action"] == "BTO" and order['avg'] is not None:
            str_act = make_BTO_option_Avg(order, self.portfolio, openTrade)
    
        elif order["action"] == "BTO":
            str_act = "Repeated BTO"
    
        elif order["action"] == "STC" and openTrade is None:
            str_act = "STC without BTO"
    
        elif order["action"] == "STC":
            str_act = make_STC_option(order, self.portfolio, openTrade)
    
        elif order["action"] == "ExitUpdate" and openTrade is not None:
            planned = eval(str(self.portfolio.loc[openTrade, "Planned_PT"]))
            str_act = "ExitUpdate: "
            for i in range(1,4):
                if order.get(f"PT{i}"):
                    planned.append(order.get(f"PT{i}"))
                    str_act = str_act + f"PT{i}, "
            if len(planned):
                self.portfolio.loc[openTrade, "Planned_PT"] = str(planned)

            SL = eval(str(self.portfolio.loc[openTrade, "Planned_SL"]))
            if SL is None: SL = []
            if order.get("SL"):
                SL.append(order.get("SL"))
                str_act = str_act + f"SL",
                self.portfolio.loc[openTrade, "Planned_SL"] = SL
        else:
            str_act = "Nothing"

        return  str_act


    def make_BTO_option(self, order):
    
        PTs = [order["PT1"], order["PT2"], order["PT3"]]
        Qts = order["PTs_Qty"]
    
        planned = [[PTs[i], Qts[i]] for i in range(order['n_PTs'])]
    
        sl_mental = True if "mental" in msg.lower() else False
        alert_price = self.price_now(order['Symbol'])
        
        self.portfolio = self.portfolio.append({
            "BTO-Date": order['date'],
            'Trader': order['Trader'],
            "Symbol" : order['Symbol'],
            "BTO": order['price'],
            'Asset': order['asset'],
            'isOpen': 1,
            "Strike" : order['strike'],
            "ExpDate" : order['expDate'],
            "Planned_PT": planned,
            "Planned_SL": order['SL'],
            "SL_mental" : sl_mental,
            "Alert-Price" : alert_price,
            "Risk": order['risk']
            }, ignore_index=True)
        str_act = f"BTO {order['Symbol']} {order['price']} {order['expDate']} {order['strike']}, Plan PT:{order['PT1']}, SL:{order['SL']}"
    
        return str_act
    
    
    def make_BTO_option_Avg(self, order, openTrade):
    
        current_Avg = self.portfolio.loc[openTrade, "BTO-avg"]
        if np.isnan(current_Avg):
            current_Avg = 1
            self.portfolio.loc[openTrade, "BTO-avg"] = current_Avg
        else:
            current_Avg = int(current_Avg + 1)
            self.portfolio.loc[openTrade, "BTO-avg"] = current_Avg
    
        str_act =f"BTO {order['Symbol']} {current_Avg}th averging down @ {order['price']}"
    
        self.portfolio.loc[openTrade, "BTO"] = order["avg"]
    
        planned = self.portfolio.loc[openTrade, "Planned_PT"]
    
        PTs = [order["PT1"], order["PT2"], order["PT3"]]
        Qts = order["PTs_Qty"]
        planned = [[PTs[i], Qts[i]] for i in range(order['n_PTs'])]
    
        if len(planned):
            self.portfolio.loc[openTrade, "Planned_PT"] = [planned]
    
        if order["SL"] is not None:
            self.portfolio.loc[openTrade, "Planned_SL"] = order["SL"]
            str_act = str_act + f" update SL: {order['SL']}"
    
        return str_act
    
    
    def make_STC_option(self, order, openTrade):
    
        if np.isnan(self.portfolio.loc[openTrade, "STC1"]):
            STC = "STC1"
        elif np.isnan(self.portfolio.loc[openTrade, "STC2"]):
            STC = "STC2"
        elif np.isnan(self.portfolio.loc[openTrade, "STC3"]):
            STC = "STC3"
        else:
            str_STC = "How many STC already?"
            # print (str_STC)
            return self.portfolio, str_STC
    
        bto_price = self.portfolio.loc[openTrade, "BTO"]
        if order.get("price") is None:
            stc_price = "none"
        else:
            stc_price = float((order.get("price") - bto_price)/bto_price) *100
    
        if order.get("amnt_left"):
            left = order["amnt_left"]
            if left == "few":
                order['xQty'] =   1- .1
            elif left > .99:  # unit left
                order['xQty'] =  1 - (.02 * left)
            elif left < .99:  # percentage left
                order['xQty'] = 1 - left
    
        self.portfolio.loc[openTrade, STC] = order.get("price")
        self.portfolio.loc[openTrade, STC + "-Date"] = order["date"]
        self.portfolio.loc[openTrade, STC + "-xQty"] = order['xQty']
        self.portfolio.loc[openTrade, STC + "-PnL"] = stc_price
    
        if order.get("price") is None:
            str_STC = f"{STC} {order['Symbol']}  ({order['xQty']}), no price provided%"
        else:
            str_STC = f"{STC} {order['Symbol']}  ({order['xQty']}), {stc_price:.2f}%"
    
        Qty_sold = self.portfolio.loc[openTrade,[f"STC{i}-xQty" for i in range(1,4)]].sum()
        if order['xQty'] == 1 or Qty_sold > .99:
            self.portfolio.loc[openTrade, "Open"] = 0
            str_STC = str_STC + " Closed"
            self.portfolio.loc[openTrade, "isOpen"] = 0
    
        return str_STC
    
    
    def check_repeat_STC(order, self.portfolio, openTrade, STC):
    
        STC_prev = [self.portfolio.loc[openTrade, f"STC{i}"] for i in range(1, 4)]
    
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
trades_log = pd.DataFrame(columns = ["BTO-Date", "Symbol", "isOpen", "BTO", "Trader",
                                     "Strike", "ExpDate", "BTO-avg",
                                     "Planned_PT", "Planned_SL", "Asset",
                                     "STC1", "STC1-xQty", "STC1-PnL","STC1-Date",
                                     "STC2", "STC2-xQty", "STC2-PnL","STC2-Date",
                                     "STC3", "STC3-xQty", "STC3-PnL","STC3-Date",
                                     "Total PnL", "Portfolio_inx"])
    # self.portfolio.to_csv(trade_log_file, index=False)




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
    symbol, prev_msg_inx = None, None

    author = alerts_author["Author"].iloc[i]#.split("#")[0]
    order, pars = combine_new_old_orders(msg, order, pars, author)
    if order is not None and order.get("Symbol") is None:
        if author == 'Xtrades Option Guru#8905':
            msg_ix, = alerts_author[alerts_author['Content'] == msg].index.values
            sym, inxf = get_symb_prev_msg(alerts_author, i, author)
            if sym is not None:
                order["Symbol"] = sym
                print(f"Got {sym} symbol from previous msg {inxf}, author: {author}")
            else:
                pars = None
    new_order = auhtor_parser(msg, author)

    if order is None:
        continue

    print(new_order)

    # if new_order.get("Symbol") ==  None:
    #     symbol, prev_msg_inx = get_symb_prev_msg(alerts_author, i, author)
    #     order["Symbol"] = symbol
    # else:


    if symbol is not None:
        print("NEW: ", new_order)
        print(f"Symb {symbol} from: ", alerts_author.loc[prev_msg_inx, "Content"])
        # resp = input("press o to stop")
        # if resp == "o":
        #     print(f"stopped at {i}")
        #     break

    if order  is None:
        not_msg = not_msg.append({"MSG":msg}, ignore_index=True)
        continue

    # order["uQty"] = 3
    alerts_author.loc[i, "parsed"] = pars
    order['Trader'] = alerts_author["Author"].iloc[i]
    order['asset'] = "option"

    # order['Trader'] = alerts_author["Author"].iloc[i]
    # if order['Symbol'] == "DPW":
    #     crh

    # if order['price'] is None:
    #     bad_msg.append((msg, trade_date))
    #     continue

    order["date"] = trade_date
    if order['action'] == 'STC' and  order.get('xQty') is None:
        continue
    trades_log, str_act, trade_ix = option_trader(order, trades_log)

    alerts_author.loc[i,"trade_act"] = str_act
    alerts_author.loc[i, "Portfolio_inx"] = trade_ix

alerts_author.to_csv(f"data/option_alerts_parsed_{author}.csv")
trades_log.to_csv(trade_log_file)

not_msg.to_csv(f"data/not_understood_{author}.csv")



Exits = not_msg[not_msg["MSG"].str.contains("target|stop")]

not_msg_exit = not_msg[~not_msg["MSG"].str.contains("target|stop")]
not_msg_exit.to_csv(f"data/not_understood_notexit_{author}.csv")


