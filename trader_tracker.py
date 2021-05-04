import pandas as pd
import re
import numpy as np
import os.path as op
from message_parser import parser_alerts, auhtor_parser, get_symb_prev_msg, combine_new_old_orders, parse_exit_plan
from place_order import make_optionID
from disc_trader import  find_last_trade
from config import (data_dir, CHN_NAMES, chn_IDS, UPDATE_PERIOD)
from datetime import datetime
from td.exceptions import NotFndError


def get_author_alerts():
    file = 'data/option_alerts_message_history.csv'

    alerts = pd.read_csv(file)
    alerts.drop(labels=['Attachments', 'Reactions'], axis=1, inplace=True)

    authors = alerts["Author"].unique()
    author = 'Xtrades Option Guru'

    # author = "Kevin Wan#0083"

    # alerts_author = alerts[alerts["Author"].str.contains(author)]


    alerts_author = alerts#_author.dropna(subset=["Content"])
    alerts_author.reset_index(drop=True, inplace=True)

    return alerts_author, author

def get_date():
    time_strf = "%Y-%m-%d %H:%M:%S.%f"
    date = datetime.now().strftime(time_strf)


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
                "Date", "Symbol", "Trader", "isOpen","Total PnL", "Asset", "Type", "Price", "Alert-Price",
                "Avged", "exit_plan", "Risk", "SL_mental"] + [
                    "STC%d-%s"% (i, v) for v in
                    ["Alerted", "xQty", "Price", "PnL","Date"]
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
                print (Back.RED + f"tracker price_now ERROR: {e}.\n Trying again later")
                quote = self.TDsession.get_quotes(
                instruments=[Symbol])[Symbol][ptype]

        return quote


    def trade_alert(self, order, live_alert=True):

        openTrade, isOpen = find_last_trade(order, self.portfolio, open_only=True)

        if order["action"] in ["BTO", "STC"] and live_alert:
            try:
                order["price_current"] = self.price_now(order["Symbol"], order["action"])
            except:
                print(f"{order['Symbol']} quote not available for trade tracker")
                order["price_current"] = None

        if openTrade is None and order["action"] == "BTO":
            str_act = self.make_BTO(order)
            openTrade, isOpen = find_last_trade(order, self.portfolio)

        elif order["action"] == "BTO" and order['avg'] is not None:
            str_act = self.make_BTO_Avg(order, openTrade)

        elif order["action"] == "BTO":
            str_act = "Repeated BTO"

        elif order["action"] == "STC" and openTrade is None:
            str_act = "STC without BTO"

        elif order["action"] == "STC":
            str_act = self.make_STC(order, openTrade)

        elif order['action'] == "ExitUpdate" and isOpen:
            old_plan = self.portfolio.loc[openTrade, "exit_plan"]
            new_plan = parse_exit_plan(order)

            # Update PT if alraedy STCn
            istc = None
            for i in range(1,4):
                if self.portfolio.loc[openTrade, f"STC{i}-Alerted"] is not None:
                    istc = i
            if istc is not None and any(["PT" in k for k in new_plan.keys()]):
                new_plan_c = new_plan.copy()
                for i in range(1,4):
                    if new_plan.get(f"PT{i}"):
                        del new_plan_c[f"PT{i}"]
                        new_plan_c[f"PT{istc}"] = new_plan[f"PT{i}"]
                new_plan = new_plan

            renew_plan = eval(old_plan)
            if renew_plan is not None or renew_plan != {}:
                for k in new_plan.keys():
                    renew_plan[k] = new_plan[k]
            else:
                renew_plan = new_plan

            self.portfolio.loc[openTrade, "exit_plan"] = str(renew_plan)
            symbol =  self.portfolio.loc[openTrade, "Symbol"]
            str_act = f"Updated {symbol} exit plan from :{old_plan} to {renew_plan}"

        else:
            str_act = "Nothing"

        return  str_act


    def make_BTO(self, order):

        PTs = [order["PT1"], order["PT2"], order["PT3"]]
        Qts = order["PTs_Qty"]

        exit_plan = parse_exit_plan(order)
        date = order.get("Date", get_date())

        new_trade = {"Date": date,
             "Symbol": order['Symbol'],
             'isOpen': 1,
             "Asset" : order["asset"],
             "Type" : "BTO",
             "Price" : order["price"],
             "Alert-Price" : order.get("price_current"),
             "exit_plan" : str(exit_plan),
             "Trader" : order['Trader'],
             "Risk" : order['risk'],
             "SL_mental" : order["SL_mental"]
             }
        self.portfolio = self.portfolio.append(new_trade, ignore_index=True)

        str_act = f"BTO {order['Symbol']} {order['price']}, Plan PT:{order['PT1']}, SL:{order['SL']}"

        return str_act


    def make_BTO_Avg(self, order, openTrade):

        current_Avg = self.portfolio.loc[openTrade, "Avged"]
        if np.isnan(current_Avg):
            current_Avg = 1
            self.portfolio.loc[openTrade, "Avged"] = current_Avg
        else:
            current_Avg = int(current_Avg + 1)
            self.portfolio.loc[openTrade, "Avged"] = current_Avg

        str_act =f"BTO {order['Symbol']} {current_Avg}th averging down @ {order['price']}"
        old_price = self.portfolio.loc[openTrade, "Price"]
        self.portfolio.loc[openTrade, "Price"] = f"{old_price}/{order['avg']}"

        price_old = self.portfolio.loc[openTrade, "Alert-Price"]
        alert_price = order.get("price_current")
        self.portfolio.loc[openTrade, "Alert-Price"]= f"{price_old}/{alert_price}"

        planned = eval(self.portfolio.loc[openTrade, "exit_plan"])

        exit_plan = parse_exit_plan(order)
        for k in exit_plan.keys():
            if exit_plan[k] is not None:
                planned[k] = exit_plan[k]

        if len(planned):
            self.portfolio.loc[openTrade, "exit_plan"] = str(planned)

        return str_act


    def make_STC(self, order, openTrade):

        if np.isnan(self.portfolio.loc[openTrade, "STC1-Alerted"]):
            STC = "STC1"
        elif np.isnan(self.portfolio.loc[openTrade, "STC1-Alerted"]):
            STC = "STC2"
        elif np.isnan(self.portfolio.loc[openTrade, "STC1-Alerted"]):
            STC = "STC3"
        else:
            str_STC = "How many STC already?"
            print (str_STC)
            return self.portfolio, str_STC

        bto_price = self.portfolio.loc[openTrade, "Price"]
        if isinstance(bto_price, str):
            bto_price = float(bto_price.split("/")[-1])
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

        self.portfolio.loc[openTrade, f"{STC}-Price"] = order.get("price")
        self.portfolio.loc[openTrade, f"{STC}-Alerted"] = order.get("price_current")
        self.portfolio.loc[openTrade, f"{STC}-Date"] = order["Date"]
        self.portfolio.loc[openTrade, f"{STC}-xQty"] = order['xQty']
        self.portfolio.loc[openTrade, f"{STC}-PnL"] = stc_price

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


    def check_repeat_STC(self, order, openTrade, STC):

        STC_prev = [self.portfolio.loc[openTrade, f"STC{i}"] for i in range(1, 4)]

        if order["price"] in STC_prev:
            rep_ix = [i for i, v in enumerate(STC_prev) if v == order["price"]]
            str_STC = f"Repeated STC{rep_ix} order"
            return True, str_STC
        else:
            return False, None


if 0:
    tt = Trades_Tracker()
    alerts_author, author = get_author_alerts()
    asset = "option"# order.get("asset")
    bad_msg = []
    not_msg = pd.DataFrame(columns=["MSG"])

    for i in range(len(alerts_author)):

        msg = alerts_author["Content"].iloc[i]
        date = alerts_author["Date"].iloc[i]
        author = alerts_author["Author"].iloc[i]#.split("#")[0]

        pars, order =  parser_alerts(msg, asset)

        symbol, prev_msg_inx = None, None

        order, pars = combine_new_old_orders(msg, order, pars, author, asset)
        if order is not None and order.get("Symbol") is None:
            msg_ix, = alerts_author[alerts_author['Content'] == msg].index.values
            sym, inxf = get_symb_prev_msg(alerts_author, i, author)
            if sym is not None:
                order["Symbol"] = sym
                print(f"Got {sym} symbol from previous msg {inxf}, author: {author}")
            else:
                pars = None

        if order is None:
            continue

        order["Date"] = date
        order["Trader"] = author
        if order.get("asset"):
            assert order.get("asset") == asset
        order['asset'] = asset
        tt.trade_alert(order, live_alert=False)
        # if new_order.get("Symbol") ==  None:
#     #     symbol, prev_msg_inx = get_symb_prev_msg(alerts_author, i, author)
#     #     order["Symbol"] = symbol
#     # else:


#     if symbol is not None:
#         print("NEW: ", new_order)
#         print(f"Symb {symbol} from: ", alerts_author.loc[prev_msg_inx, "Content"])
#         # resp = input("press o to stop")
#         # if resp == "o":
#         #     print(f"stopped at {i}")
#         #     break

#     if order  is None:
#         not_msg = not_msg.append({"MSG":msg}, ignore_index=True)
#         continue

#     # order["uQty"] = 3
#     alerts_author.loc[i, "parsed"] = pars
#     order['Trader'] = alerts_author["Author"].iloc[i]
#     order['asset'] = "option"

#     # order['Trader'] = alerts_author["Author"].iloc[i]
#     # if order['Symbol'] == "DPW":
#     #     crh

#     # if order['price'] is None:
#     #     bad_msg.append((msg, trade_date))
#     #     continue

#     order["date"] = trade_date
#     if order['action'] == 'STC' and  order.get('xQty') is None:
#         continue
#     trades_log, str_act, trade_ix = option_trader(order, trades_log)

#     alerts_author.loc[i,"trade_act"] = str_act
#     alerts_author.loc[i, "Portfolio_inx"] = trade_ix

# alerts_author.to_csv(f"data/option_alerts_parsed_{author}.csv")
# trades_log.to_csv(trade_log_file)

# not_msg.to_csv(f"data/not_understood_{author}.csv")



# Exits = not_msg[not_msg["MSG"].str.contains("target|stop")]

# not_msg_exit = not_msg[~not_msg["MSG"].str.contains("target|stop")]
# not_msg_exit.to_csv(f"data/not_understood_notexit_{author}.csv")


