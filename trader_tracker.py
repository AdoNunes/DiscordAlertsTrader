import pandas as pd
import numpy as np
import os.path as op
from message_parser import parser_alerts, get_symb_prev_msg, combine_new_old_orders, parse_exit_plan
from disc_trader import find_last_trade
from config import data_dir
from datetime import datetime, date
import re


def get_author_alerts(asset='option', author=None):
    file = f'data/{asset}_alerts_message_history.csv'
    alerts = pd.read_csv(file)
    alerts.drop(labels=['Attachments', 'Reactions'], axis=1, inplace=True)

    if author is not None:
        alerts = alerts[alerts["Author"].str.contains(author)]

    alerts = alerts.dropna(subset=["Content"])
    alerts.reset_index(drop=True, inplace=True)
    return alerts


def get_date():
    time_strf = "%Y-%m-%d %H:%M:%S.%f"
    date = datetime.now().strftime(time_strf)
    return date


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
                "Date", "Symbol", "Channel", "Trader", "isOpen", "Total PnL", "Asset", "Type", "Price", "Amount", "Alert-Price",
                "Avged", "exit_plan", "Risk", "SL_mental"] + [
                    "STC%d-%s" % (i, v) for v in
                    ["Alerted", "xQty", "uQty", "Price", "PnL", "Date"]
                    for i in range(1,4)] )
            self.portfolio.to_csv(self.portfolio_fname, index=False)

        if op.exists(self.alerts_log_fname):
            self.alerts_log = pd.read_csv(self.alerts_log_fname)
        else:
            self.alerts_log = pd.DataFrame(columns=["Date","Trader", "Symbol",
                                                    "action", "parsed", "msg", "portfolio_idx"])
        self.TDSession = TDSession


    def price_now(self, symbol, price_type="BTO"):
        if self.TDSession is None:
            return None

        if price_type in ["BTO", "BTC"]:
            ptype = 'askPrice'
        else:
            ptype = 'bidPrice'

        try:
            quote = self.TDSession.get_quotes(instruments=[symbol]).get(symbol)
            if quote is not None:
                quote = quote[ptype]
        except KeyError as e:
            print(e)
            quote = None

        return quote


    def trade_alert(self, order, pars, msg, live_alert=True, channel=None):

        open_trade, isOpen = find_last_trade(order, self.portfolio, open_only=True)

        date = order.get("Date", get_date())
        log_alert = {"Date": date,
                     "Symbol": order['Symbol'],
                     "Trader" : order['Trader'],
                     "parsed" : pars,
                     "msg": msg
                     }

        if order["action"] in ["BTO", "STC"] and live_alert:
            try:
                order["price_current"] = self.price_now(order["Symbol"], order["action"])
            except:
                print(f"{order['Symbol']} quote not available for trade tracker")
                order["price_current"] = None

        if open_trade is None and order["action"] == "BTO":
            str_act = self.make_BTO(order, channel)
            open_trade, isOpen = find_last_trade(order, self.portfolio)

        elif order["action"] == "BTO" and order['avg'] is not None:
            str_act = self.make_BTO_Avg(order, open_trade)

        elif order["action"] == "BTO":
            str_act = "Repeated BTO"

        elif order["action"] == "STC" and open_trade is None:
            str_act = "STC without BTO"

        elif order["action"] == "STC":
            str_act = self.make_STC(order, open_trade)

        elif order['action'] == "ExitUpdate" and isOpen:
            old_plan = self.portfolio.loc[open_trade, "exit_plan"]
            new_plan = parse_exit_plan(order)

            # Update PT if already STCn
            istc = None
            for i in range(1,4):
                if self.portfolio.loc[open_trade, f"STC{i}-Alerted"] is not None:
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

            self.portfolio.loc[open_trade, "exit_plan"] = str(renew_plan)
            symbol = self.portfolio.loc[open_trade, "Symbol"]
            str_act = f"Updated {symbol} exit plan from :{old_plan} to {renew_plan}"

        else:
            return "Nothing"

        self.close_expired(open_trade)
        log_alert["portfolio_idx"] = open_trade
        log_alert["action"] = str_act
        self.alerts_log = pd.concat([self.alerts_log, pd.DataFrame.from_records(log_alert, index=[0])], ignore_index=True)

        #save to csv
        self.portfolio.to_csv(self.portfolio_fname, index=False) # try except PermissionError
        self.alerts_log.to_csv(self.alerts_log_fname, index=False)        
        return  str_act


    def make_BTO(self, order, chan=None):

        PTs = [order["PT1"], order["PT2"], order["PT3"]]
        Qts = order["PTs_Qty"]

        exit_plan = parse_exit_plan(order)
        date = order.get("Date", get_date())

        if order['uQty'] is None:
            order['uQty'] = 1
        new_trade = {"Date": date,
                     "Symbol": order['Symbol'],
                     'isOpen': 1,
                     "Asset": order["asset"],
                     "Type": "BTO",
                     "Price": order["price"],
                     "Amount": order['uQty'],
                     "Alert-Price": order.get("price_current"),
                     "exit_plan": str(exit_plan),
                     "Trader": order['Trader'],
                     "Risk": order['risk'],
                      "SL_mental": order.get("SL_mental"),
                      "Channel" : chan
                     }
        
        self.portfolio =pd.concat([self.portfolio, pd.DataFrame.from_records(new_trade, index=[0])], ignore_index=True)

        str_act = f"BTO {order['Symbol']} {order['price']}"
        if order['PT1'] is not None:
            str_act += f", Plan PT:{order['PT1']}"
        if order['SL'] is not None:
            str_act += f", SL:{order['SL']}"

        return str_act


    def make_BTO_Avg(self, order, open_trade):

        current_Avg = self.portfolio.loc[open_trade, "Avged"]
        if np.isnan(current_Avg):
            current_Avg = 1
        else:
            current_Avg = int(current_Avg + 1)
        self.portfolio.loc[open_trade, "Avged"] = current_Avg

        str_act = f"BTO {order['Symbol']} {current_Avg}th averging down @ {order['price']}"
        old_price = self.portfolio.loc[open_trade, "Price"]
        self.portfolio.loc[open_trade, "Price"] = f"{old_price}/{order['price']}"

        price_old = self.portfolio.loc[open_trade, "Alert-Price"]
        alert_price = order.get("price_current")
        avgs_prices = f"{price_old}/{alert_price}".replace("None/None", "").replace("None", "")
        self.portfolio.loc[open_trade, "Alert-Price"] = avgs_prices

        planned = eval(self.portfolio.loc[open_trade, "exit_plan"])

        exit_plan = parse_exit_plan(order)
        for k in exit_plan.keys():
            if exit_plan[k] is not None:
                planned[k] = exit_plan[k]

        if len(planned):
            self.portfolio.loc[open_trade, "exit_plan"] = str(planned)

        return str_act


    def make_STC(self, order, open_trade):

        if pd.isnull(self.portfolio.loc[open_trade, "STC1-PnL"]):
            STC = "STC1"
        elif pd.isnull(self.portfolio.loc[open_trade, "STC2-PnL"]):
            STC = "STC2"
        elif pd.isnull(self.portfolio.loc[open_trade, "STC3-PnL"]):
            STC = "STC3"
        else:
            str_STC = f"How many STC already?, {order}"
            print (str_STC)
            return str_STC

        bto_price = self.portfolio.loc[open_trade, "Price"]
        if isinstance(bto_price, str):
            bto_price =  np.mean(eval(bto_price.replace("/", ",")))
        if order.get("price") is None or bto_price is None:
            stc_price = "none"
        else:
            stc_price = float((order.get("price") - bto_price)/bto_price) *100

        if order.get("amnt_left"):
            left = order["amnt_left"]
            if left == "few":
                order['xQty'] = 1 - .1
            elif left > .99:  # unit left
                order['xQty'] = 1 - (.02 * left)
            elif left < .99:  # percentage left
                order['xQty'] = 1 - left
        
        if order['uQty'] is None:
            order['uQty'] = 1
        
        self.portfolio.loc[open_trade, f"{STC}-Price"] = order.get("price")
        self.portfolio.loc[open_trade, f"{STC}-Alerted"] = order.get("price_current", "-")
        self.portfolio.loc[open_trade, f"{STC}-Date"] = order["Date"]
        self.portfolio.loc[open_trade, f"{STC}-uQty"] = order['uQty']
        self.portfolio.loc[open_trade, f"{STC}-xQty"] = order['xQty']
        self.portfolio.loc[open_trade, f"{STC}-PnL"] = stc_price

        if stc_price == "none":
            str_STC = f"{STC} {order['Symbol']}  ({order['uQty']}), no price provided"
        else:
            str_STC = f"{STC} {order['Symbol']}  ({order['uQty']}), {stc_price:.2f}%"

        # Qty_sold = self.portfolio.loc[open_trade,[f"STC{i}-xQty" for i in range(1, 4)]].sum()
        # if order['xQty'] == 1 or Qty_sold > .98:
        if self.portfolio.loc[open_trade, 'Amount'] is not None:
            Qty_sold = self.portfolio.loc[open_trade,[f"STC{i}-uQty" for i in range(1, 4)]].sum()
            Qty_bougt = self.portfolio.loc[open_trade, 'Amount']
        else:
            Qty_sold = self.portfolio.loc[open_trade,[f"STC{i}-xQty" for i in range(1, 4)]].sum()
            Qty_bougt = 1
        if Qty_sold >= Qty_bougt:
            str_STC = str_STC + " Closed"
            self.portfolio.loc[open_trade, "isOpen"] = 0

        return str_STC


    def check_repeat_STC(self, order, open_trade, STC):

        STC_prev = [self.portfolio.loc[open_trade, f"STC{i}"] for i in range(1, 4)]

        if order["price"] in STC_prev:
            rep_ix = [i for i, v in enumerate(STC_prev) if v == order["price"]]
            str_STC = f"Repeated STC{rep_ix} order"
            return True, str_STC
        else:
            return False, None


    def close_expired(self, open_trade):
        if open_trade == 0 or pd.isnull(open_trade):
            return

        current_trade = self.portfolio.iloc[open_trade]
        current_date = current_trade["Date"]
        current_date = datetime.strptime(current_date, "%Y-%m-%d %H:%M:%S.%f")

        for trade_inx in range(open_trade):
            trade = self.portfolio.iloc[trade_inx]
            if trade["Asset"] != "option" or trade["isOpen"] == 0:
                continue

            optdate = option_date(trade['Symbol'])
            if optdate.date() < current_date.date():
                for stci in range(1,4):
                    if pd.isnull(trade[f"STC{stci}-xQty"]):
                        STC = f"STC{stci}"
                        break
                else:
                    stci = 4
                    STC = f"STC{stci}"
                uQty = trade["Amount"] - trade[[f"STC{i}-xQty" for i in range(1, stci)]].sum()                
                #Log portfolio
                self.portfolio.loc[trade_inx, STC + "-Status"] = 'EXPIRED'
                self.portfolio.loc[trade_inx, STC + "-Price"] = 0
                self.portfolio.loc[trade_inx, STC + "-Date"] = current_date
                self.portfolio.loc[trade_inx, STC + "-xQty"] = 1
                self.portfolio.loc[trade_inx, STC + "-uQty"] = uQty
                self.portfolio.loc[trade_inx, STC + "-PnL"] = -100
                self.portfolio.loc[trade_inx, "isOpen"] = 0

                str_prt = f"{trade['Symbol']} option expired -100%"
                print(str_prt)




def option_date(opt_symbol):
    sym_inf = opt_symbol.split("_")[1]
    opt_date = re.split("C|P", sym_inf)[0]
    return datetime.strptime(opt_date, "%m%d%y")




if 0:
    tt = Trades_Tracker()

    for asset in ["stock"]:# [ "option", "stock"]:#
        alerts_author = get_author_alerts(asset)

        bad_msg = []
        not_msg = pd.DataFrame(columns=["MSG"])

        for i in range(len(alerts_author)):

            msg = alerts_author["Content"].iloc[i]
            if pd.isnull(msg):
                continue

            date = alerts_author["Date"].iloc[i]
            author = alerts_author["Author"].iloc[i]

            pars, order =  parser_alerts(msg, asset)

            order, pars = combine_new_old_orders(msg, order, pars, author, asset)
            if order is not None and order.get("Symbol") is None:
                msg_ix, = alerts_author[alerts_author['Content'] == msg].index.values
                sym, inxf = get_symb_prev_msg(alerts_author, i, author)
                if sym is not None:
                    order["Symbol"] = sym
                    print(f"Got {sym} symbol from previous msg {inxf}, author: {author}")
                else:
                    pars = None

            if order is None or order.get('action') is None:
                continue

            order["Date"] = date
            order["Trader"] = author
            if order.get("asset"):
                assert order.get("asset") == asset
            order['asset'] = asset
            res_out = tt.trade_alert(order, pars, msg, live_alert=False)
            if "How many STC already?" in res_out:
                tt.portfolio.to_csv(tt.portfolio_fname, index=False)
                tt.alerts_log.to_csv(tt.alerts_log_fname, index=False)
                # resp = input("Continue? yes or no")
                # if resp == "no":
                #     break

    tt.portfolio.to_csv(tt.portfolio_fname, index=False)
    tt.alerts_log.to_csv(tt.alerts_log_fname, index=False)
        # if new_order.get("Symbol") ==  None:
#     #     symbol, prev_msg_inx = get_symb_prev_msg(alerts_author, i, author)
#     #     order["Symbol"] = symbol
#     # else:

# tt.portfolio.to_csv(tt.portfolio_fname, index=False)
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


