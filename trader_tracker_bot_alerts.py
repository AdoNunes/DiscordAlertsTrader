import pandas as pd
import numpy as np
import os.path as op
import json
from datetime import datetime, timedelta, date

from disc_trader import find_last_trade, option_date
from message_parser import parser_alerts
from config import (path_dll, data_dir,  discord_token,  analyst_logs)


def get_date():
    time_strf = "%Y-%m-%d %H:%M:%S.%f"
    date = datetime.now().strftime(time_strf)
    return date


def disc_json_time_corr(time_json):
    """ Mesages from json are 4hs forward

        Original format: '2021-03-19T18:31:01.609+00:00'
        output: dateime object - 4hs !"""
    try:
        date = datetime.strptime(time_json.split("+")[0], "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        date = datetime.strptime(time_json.split("+")[0], "%Y-%m-%dT%H:%M:%S")

    time_strf = "%Y-%m-%d %H:%M:%S.%f"
    date +=  timedelta(hours=-4)
    date = date.strftime(time_strf)
    return date


class Bot_bulltrades_Tracker():

    def __init__(self, TDSession=None,
                 portfolio_fname=data_dir + "/analyst_bot_log_portfolio.csv"):

        self.portfolio_fname = portfolio_fname        

        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=[
                "Date", "Symbol", "Trader", "isOpen", "Asset", "Type", "Price", "Amount", "Price-current", "Prices", "Prices-current", "Avged"
                ] + [ f"STC-{v}" for v in
                    ["Amount", "Price", "Price-current", "Prices", "Prices-current", "PnL", "PnL-current","PnL$", "PnL$-current", "Date"]
                    for i in range(1,2)] )
            self.portfolio.to_csv(self.portfolio_fname, index=False)
        self.TDSession = TDSession
        self.cmd = f'dotnet {path_dll} export' + ' -c {} -t ' + discord_token  + \
            ' -f Json --after "{}" --dateformat "yyyy-MM-dd HH:mm:ss.ffffff" -o {}'
        self.time_strf = "%Y-%m-%d %H:%M:%S.%f"


    def price_now(self, symbol, price_type="BTO"):
        if self.TDSession is None:
            return None

        if price_type in ["BTO", "BTC"]:
            ptype = 'askPrice'
        else:
            ptype = 'bidPrice'

        quote = self.TDSession.get_quotes(instruments=[symbol])
        if quote is None:
            quote = self.TDSession.get_quotes(instruments=[symbol])
            
        if quote is not None and len(quote):
            quote = quote.get(symbol)[ptype]
            if quote != 0:
                return quote
            else:
                print("quote 0 for", symbol, price_type)


    def update_msgs(self): 
        from real_time_exporter import send_sh_cmd       
        for author, chan_ID in analyst_logs.items():
            out_file = op.join(data_dir, f"alert_chan_logs_{author}.json")
            
            # Decide from when to read alerts 
            if (self.portfolio["Trader"]==author).sum():
                trader_trades = self.portfolio.loc[self.portfolio["Trader"] == author]
                time_after_1 = trader_trades["Date"].max()
                time_after_2 = trader_trades.loc[~trader_trades["STC-Date"].isnull(), "STC-Date"].max()
                time_after = max(time_after_1,time_after_2)
                new_t = min(59.99, float(time_after[-9:]) + .1)
                time_after = time_after[:-9] + f"{new_t:.6f}"
            else:
                time_after = (datetime.now() - timedelta(weeks=2)).strftime(self.time_strf)

            cmd_sh = self.cmd.format(chan_ID, time_after, out_file)
            new_msgs = send_sh_cmd(cmd_sh)
            
            if not new_msgs:
                continue

            with open(out_file, "r", errors='ignore') as f:
                data = json.load(f)

            for msg_n in range(data['messageCount']):
                msg = data['messages'][msg_n]
                msg_str = msg['content']
                if not len(msg_str):
                    continue
                field = {m['name']:m['value'] for m in msg['embeds'][0]['fields']}
                if msg_str ==  'Expired contract.':
                    msg_str = f"STC {field['# Closed'].split('/')[0]} {field['Ticker']} {field['Strike']} {field['Date']} @{field['Sell']}"
                    print(msg_str)
                ord_str, order = parser_alerts(msg_str)
                if order is None:
                    continue
                if field['Actual Cost'] == 'None':
                    order['Actual Cost'] = None
                else:
                    order['Actual Cost'] = float(field['Actual Cost'])
                order['# Closed'] = field['# Closed']
                order['Trader'] = author
                order["Date"] = disc_json_time_corr(msg['timestamp'])
                
                # find if live alert and process trade
                order_date = datetime.strptime(order["Date"], "%Y-%m-%d %H:%M:%S.%f")
                date_diff = datetime.now() - order_date
                live_alert = True if date_diff.seconds < 90 else False
                msg_track = self.trade_alert(order, live_alert, author)
                print(msg_track)
            self.close_expired()
        self.portfolio = self.portfolio.sort_values("Date")
        self.portfolio.to_csv(self.portfolio_fname, index=False) 


    def trade_alert(self, order, live_alert=True, channel=None):
        open_trade, _ = find_last_trade(order, self.portfolio, open_only=True)
        if order.get('uQty') is None:
            order['uQty'] = 1
        
        if order["action"] in ["BTO", "STC"] and live_alert:
            if order.get('Actual Cost', 'None') == 'None':
                order["Actual Cost"] = self.price_now(order["Symbol"], order["action"])

        if open_trade is None and order["action"] == "BTO":
            str_act = self.make_BTO(order, channel)
        elif order["action"] == "BTO":
            str_act = self.make_BTO_Avg(order, open_trade)
        elif order["action"] == "STC" and open_trade is None:
            str_act = "STC without BTO"
        elif order["action"] == "STC":
            str_act = self.make_STC(order, open_trade)
        elif order["action"] == "ExitUpdate":
            if open_trade is not None:
                self.portfolio.loc[open_trade, "SL"] = order.get('SL')
            return 

        #save to csv
        self.portfolio.to_csv(self.portfolio_fname, index=False)      
        return  str_act


    def make_BTO(self, order, chan=None):
        if order["price"] is None:
            return
        date = order.get("Date", get_date())
        if order['uQty'] is None:
            order['uQty'] = 1
        new_trade = {
            "Date": date,
            "Symbol": order['Symbol'],
            'isOpen': 1,
            "Asset": order["asset"],
            "Type": "BTO",
            "Price": order["price"],
            "Amount": order['uQty'],
            "Price-current": order.get("Actual Cost"),
            "Trader": order['Trader'],
            "SL": order.get("SL"),
            "Channel" : chan
            }        
        self.portfolio =pd.concat([self.portfolio, pd.DataFrame.from_records(new_trade, index=[0])], ignore_index=True)

        str_act = f"BTO {order['Symbol']} {order['price']}"
        if order['SL'] is not None:
            str_act += f", SL:{order['SL']}"
        return str_act


    def make_BTO_Avg(self, order, open_trade):
        current_Avg = self.portfolio.loc[open_trade, "Avged"]
        if np.isnan(current_Avg):
            current_Avg = 1
        else:
            current_Avg = int(current_Avg + 1)
        
        old_price = self.portfolio.loc[open_trade, "Price"]
        old_price = eval(old_price) if isinstance(old_price, str) else old_price
        old_qty = self.portfolio.loc[open_trade, "Amount"]
        alert_price_old = self.portfolio.loc[open_trade, "Price-current"]
        alert_price_old = eval(alert_price_old) if isinstance(alert_price_old, str) else alert_price_old
        alert_price_old = None if pd.isnull(alert_price_old) else alert_price_old
        alert_price = order.get("Actual Cost", "None")
        avgs_prices_al = f"{alert_price_old}/{alert_price}".replace("None/", "").replace("/None", "").replace("None", "")
        if not len(avgs_prices_al):
            avgs_prices_al = None
    
        self.portfolio.loc[open_trade, "Avged"] = current_Avg
        self.portfolio.loc[open_trade, "Amount"] += order['uQty']
        self.portfolio.loc[open_trade, "Price"] = ((old_price*old_qty) + (order['price']*order['uQty']))/(old_qty+order['uQty'])
        self.portfolio.loc[open_trade, "Prices"] = f"{old_price}/{order['price']}"
        if alert_price == 'None' or alert_price is None or alert_price_old is None:
            self.portfolio.loc[open_trade, "Price-current"] = alert_price_old
        else:
            self.portfolio.loc[open_trade, "Price-current"] = ((alert_price_old*old_qty) + (alert_price*order['uQty']))/(old_qty+order['uQty'])
        self.portfolio.loc[open_trade, "Prices-current"] = avgs_prices_al
        if order.get("SL"):
            self.portfolio.loc[open_trade, "SL"] =  order.get("SL")
        
        str_act = f"BTO {order['Symbol']} {current_Avg}th averging down @ {order['price']}"
        return str_act


    def make_STC(self, order, open_trade):
        trade = self.portfolio.loc[open_trade]
        stc_info = self.calc_stc_prices(trade, order)
        #Log portfolio
        for k, v in stc_info.items():
            self.portfolio.loc[open_trade, k] = v
        self.portfolio.loc[open_trade, "STC-Date"] = order["Date"]
        stc_price =  self.portfolio.loc[open_trade,"STC-Price"]
        stc_utotal = self.portfolio.loc[open_trade,"STC-Amount"]
        
        if stc_price == "none" or stc_price is None:
            str_STC = f"STC {order['Symbol']}  ({order['uQty']}), no price provided"
        else:
            str_STC = f"STC {order['Symbol']}  ({order['uQty']}), {stc_price:.2f}%"

        if stc_utotal >= trade['Amount']:
            str_STC = str_STC +" Closed"
            self.portfolio.loc[open_trade, "isOpen"] = 0
        if eval(order.get('# Closed', "0"))==1 :
            self.portfolio.loc[open_trade, "isOpen"]=0
        return str_STC


    def calc_stc_prices(self, trade, order=None ):
        # if order is None = expired option
        if order is None:
            order = {
                "price":0,
                "Actual Cost":0,
                "expired": True
                }
        bto_price = trade["Price"]
        bto_price_al = trade["Price-current"]
        
        if not order.get('expired', False):
            if order['uQty'] is None:
                uQty = 1
            else:
                uQty = order['uQty']
        else: 
            if pd.isnull(trade["STC-Amount"]):
                uQty = trade['Amount'] 
            else:
                uQty = trade['Amount'] - trade["STC-Amount"]
        
        if isinstance(bto_price, str):
            bto_price =  np.mean(eval(bto_price.replace("/", ",")))
        if isinstance(bto_price_al, str):
            if bto_price_al[0] == '/':
                bto_price_al = bto_price_al[1:]
            bto_price_al =  np.mean(eval(bto_price_al.replace("/", ",")))
        
        if not pd.isnull(trade["STC-Price"]):  # previous stcs            
            stc_wprice = trade["STC-Price"] * trade["STC-Amount"]
            stc_utotal = trade["STC-Amount"] + uQty
            stc_price = (order.get("price") * uQty +  stc_wprice)/stc_utotal      
            prices = "/".join([str(trade["STC-Prices"]), str(order.get("price"))])
            
            if pd.isnull(trade["STC-Price-current"]) or pd.isnull(order.get("Actual Cost")):
                prices_curr = 0 if order.get('expired', False) else ""
                stc_price_al = 0 if order.get('expired', False) else None
            else:
                stc_wprice = trade["STC-Price-current"] * trade["STC-Amount"]
                stc_price_al = (order.get("Actual Cost") * uQty +  stc_wprice)/stc_utotal
                prices_curr = "/".join([str(trade["STC-Prices-current"]), str(order.get("Actual Cost"))])
        else:  # non-previous stcs   
            stc_price = order.get("price")
            stc_price_al = order.get("Actual Cost")
            stc_utotal = uQty
            prices = order.get("price")
            prices_curr = order.get("Actual Cost")
        
        mutipl = 1 if trade['Asset'] == "option" else .01  # pnl already in %
        if stc_price is not None: 
            stc_pnl = float((stc_price - bto_price)/bto_price) *100
            stc_pnl_u = stc_pnl* bto_price *mutipl*stc_utotal 
        else:
            stc_pnl = None
            stc_pnl_u = None
        
        if stc_price_al is None or pd.isnull(bto_price_al) or bto_price_al == 0:
            stc_pnl_al = None
            stc_pnl_al_u = None
        else:
            stc_pnl_al = float((stc_price_al - bto_price_al)/bto_price_al) *100
            stc_pnl_al_u = stc_pnl_al* bto_price_al *mutipl*stc_utotal 

        stc_info = {"STC-Prices":prices,
                    "STC-Prices-current": prices_curr,
                    "STC-Price": stc_price,
                    "STC-Price-current": stc_price_al,
                    "STC-Amount": stc_utotal,
                    "STC-PnL": stc_pnl,
                    "STC-PnL-current": stc_pnl_al,
                    "STC-PnL$": stc_pnl_u,
                    "STC-PnL$-current": stc_pnl_al_u,
                    }
        return stc_info

    def close_expired(self):
        for i, trade in  self.portfolio.iterrows():
            if trade["Asset"] != "option" or trade["isOpen"] == 0:
                continue
            optdate = option_date(trade['Symbol'])
            if optdate.date() < date.today():
                expdate = date.today().strftime("%Y-%m-%dT%H:%M:%S+0000")
                
                stc_info = self.calc_stc_prices(trade)
                #Log portfolio
                self.portfolio.loc[i, "STC-Date"] = expdate
                self.portfolio.loc[i, "STC-xQty"] = 1
                for k, v in stc_info.items():
                    self.portfolio.loc[i, k] = v
                
                self.portfolio.loc[i, "isOpen"] = 0
                str_prt = f"{trade['Symbol']} option expired -100%"
                print(str_prt)


if __name__ == "__main__":
    tracker = Bot_bulltrades_Tracker()
    tracker.update_msgs()