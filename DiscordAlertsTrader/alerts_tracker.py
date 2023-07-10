import pandas as pd
import numpy as np
import os.path as op
from datetime import datetime, date

from .alerts_trader import find_last_trade, option_date
from .configurator import cfg

def get_date():
    time_strf = "%Y-%m-%d %H:%M:%S.%f"
    date = datetime.now().strftime(time_strf)
    return date


class AlertsTracker():

    def __init__(self, brokerage=None,
                 portfolio_fname=cfg['portfolio_names']["tracker_portfolio_name"],
                 dir_quotes = cfg['general']['data_dir'] + '/live_quotes',
                 cfg=cfg):

        self.portfolio_fname = portfolio_fname  
        self.dir_quotes = dir_quotes
        self.bksession = brokerage
        self.cfg = cfg

        if op.exists(self.portfolio_fname):
            self.portfolio = pd.read_csv(self.portfolio_fname)
        else:
            self.portfolio = pd.DataFrame(columns=self.cfg["col_names"]['tracker_portfolio'].split(",") )
            self.portfolio.to_csv(self.portfolio_fname, index=False)

    def price_now(self, symbol:str, price_type="BTO"):
        if self.bksession is None:
            return None

        if price_type in ["BTO", "BTC"]:
            ptype = 'askPrice'
        else:
            ptype = 'bidPrice'

        quote = self.bksession.get_quotes([symbol])
        if quote is None:
            # Try it again in case of TDA
            quote = self.bksession.get_quotes([symbol])
            
        if quote is not None and len(quote) and quote.get(symbol) is not None and quote.get(symbol).get('description' ) != 'Symbol not found':
            quote = quote.get(symbol).get(ptype)
            if quote != 0:
                return quote
            else:
                print("quote 0 for", symbol, price_type)

    def trade_alert(self, order, live_alert=True, channel=None):
        open_trade, _ = find_last_trade(order, self.portfolio, open_only=True)
        if order.get('Qty') is None:
            order['Qty'] = 1
        
        if order["action"] in ["BTO", "STC",'STO', 'BTC'] and live_alert:
            if order.get('Actual Cost', 'None') == 'None':
                order["Actual Cost"] = self.price_now(order["Symbol"], order["action"])

        if open_trade is None and order["action"] in ["BTO", 'STO']:
            str_act = self.make_BTO(order, channel)
        elif order["action"] in ["BTO", 'STO']:
            # str_act = "BTO averaging disabled as it is mostly wrong alert messages"
            str_act = self.make_BTO_Avg(order, open_trade)
        elif order["action"] in ["STC", "BTC"] and open_trade is None:
            str_act = order["action"] + "without BTO"
        elif order["action"] in ["STC", "BTC"]:
            str_act = self.make_STC(order, open_trade)
        elif order["action"] == "ExitUpdate":
            if open_trade is not None:
                self.portfolio.loc[open_trade, "SL"] = order.get('SL')
            return 

        #save to csv
        self.portfolio.to_csv(self.portfolio_fname, index=False)      
        return str_act

    def make_BTO(self, order, chan=None):
        if order["price"] is None:
            return
        date = order.get("Date", get_date())
        if order['Qty'] is None:
            order['Qty'] = 1
        new_trade = {
            "Date": date,
            "Symbol": order['Symbol'],
            'isOpen': 1,
            "Asset": order["asset"],
            "Type": order["action"],
            "Price": order["price"],
            "Qty": order['Qty'],
            "Price-actual": order.get("Actual Cost"),
            "Trader": order['Trader'],
            "SL": order.get("SL"),
            "Channel" : chan
            }        
        self.portfolio =pd.concat([self.portfolio, pd.DataFrame.from_records(new_trade, index=[0])], ignore_index=True)

        str_act = f"{order['action']} {order['Symbol']} {order['price']}"
        if order['SL'] is not None:
            str_act += f", SL:{order['SL']}"
        return str_act

    def make_BTO_Avg(self, order, open_trade):
        actual_Avg = self.portfolio.loc[open_trade, "Avged"]
        if np.isnan(actual_Avg):
            actual_Avg = 1
        else:
            actual_Avg = int(actual_Avg + 1)
        
        old_price = self.portfolio.loc[open_trade, "Price"]
        old_price = eval(old_price) if isinstance(old_price, str) else old_price
        old_qty = self.portfolio.loc[open_trade, "Qty"]
        alert_price_old = self.portfolio.loc[open_trade, "Price-actual"]
        alert_price_old = eval(alert_price_old) if isinstance(alert_price_old, str) else alert_price_old
        alert_price_old = None if pd.isnull(alert_price_old) else alert_price_old
        alert_price = order.get("Actual Cost", "None")
        avgs_prices_al = f"{alert_price_old}/{alert_price}".replace("None/", "").replace("/None", "").replace("None", "")
        if not len(avgs_prices_al):
            avgs_prices_al = None
    
        self.portfolio.loc[open_trade, "Avged"] = actual_Avg
        self.portfolio.loc[open_trade, "Qty"] += order['Qty']
        self.portfolio.loc[open_trade, "Price"] = round(((old_price*old_qty) + (order['price']*order['Qty']))/(old_qty+order['Qty']),2)
        self.portfolio.loc[open_trade, "Prices"] = f"{old_price}/{order['price']}"
        if alert_price == 'None' or alert_price is None or alert_price_old is None:
            self.portfolio.loc[open_trade, "Price-actual"] = alert_price_old
        else:
            self.portfolio.loc[open_trade, "Price-actual"] = round(((alert_price_old*old_qty) + (alert_price*order['Qty']))/(old_qty+order['Qty']),2)
        self.portfolio.loc[open_trade, "Prices-actual"] = avgs_prices_al
        if order.get("SL"):
            self.portfolio.loc[open_trade, "SL"] =  order.get("SL")
        
        str_act = f"{order['action']} {order['Symbol']} {actual_Avg}th averging down @ {order['price']}"
        return str_act

    def make_STC(self, order, open_trade, check_trail=False):
        trade = self.portfolio.loc[open_trade]
        stc_info = calc_stc_prices(trade, order)
        #Log portfolio
        for k, v in stc_info.items():
            self.portfolio.loc[open_trade, k] = v
        
        trailstat = self.compute_trail(open_trade)
        self.portfolio.loc[open_trade, "TrailStats"] = trailstat
        self.portfolio.loc[open_trade, "STC-Date"] = order["Date"]
        stc_price =  self.portfolio.loc[open_trade,"STC-Price"]
        stc_utotal = self.portfolio.loc[open_trade,"STC-Qty"]
        suffx = ''
        if stc_utotal >= trade['Qty']:
            suffx = " Closed"
            self.portfolio.loc[open_trade, "isOpen"] = 0
            
        if stc_price == "none" or stc_price is None:
            str_STC = f"{order['action']} {order['Symbol']}  ({order['Qty']}), no price provided" + suffx
        else:
            # str_STC = f"STC {order['Symbol']} ({order['Qty']}),{suffx} @{stc_price:.2f}"
            str_STC = ""
            if stc_info['STC-Price-actual'] is not None:           
                str_STC += f"\t@{stc_price:.2f}, actual: {stc_info['STC-Price-actual']:.2f} " 
            if stc_info["PnL"] is not None:
                str_STC += f'\tPnL:{round(stc_info["PnL"])}% ${round(stc_info["PnL$"])}' 
            if stc_info["PnL-actual"] is not None:
                str_STC += f' Actual:{round(stc_info["PnL-actual"])}% ${round(stc_info["PnL$-actual"])}\n\t\t'

        if eval(order.get('# Closed', "0"))==1 :
            self.portfolio.loc[open_trade, "isOpen"]=0
        str_STC = str_STC + " " + trailstat.replace('| ', '\n\t')
        return str_STC

    def compute_trail(self, open_trade):
        trade = self.portfolio.loc[open_trade]
        fname = self.dir_quotes + f"/{trade['Symbol']}.csv"
        if not op.exists(fname):
            return ""
        
        quotes = pd.read_csv(fname, on_bad_lines='skip')
        # start after BTO date
        quotes = quotes.dropna()
        dates = quotes['timestamp'].apply(lambda x: datetime.fromtimestamp(x))
        msk = dates >= pd.to_datetime(trade['Date'])
        quotes = quotes[msk].reset_index(drop=True)
        
        # first price will be the actual
        if not pd.isnull(trade["Price-actual"]):
            price0 = trade["Price-actual"]
        else:
            price0 = trade["Price"]
        quotes.loc[0, ' quote'] = price0

        # Calculate trailingStops
        res_str = "TS:{},{}%,${},in {}"
        trailing_Stop = [.2, .3, .4, .5] 
        max_trails = []      
        quotes['highest'] = quotes[' quote'].cummax() #take the cumulative max
        quotes['perc'] = round((quotes[' quote'] - quotes[' quote'].loc[0])/ quotes[' quote'].loc[0] *100,2)
        for trl in trailing_Stop:
            # Calculate trailing stop based on constant value
            trailing_stop = quotes['highest'] - quotes[' quote'].loc[0]* trl
            trl_ix = (quotes[' quote'] <= trailing_stop).idxmax()
            if trl_ix:
                tdiff_str, trl_r = self.trailing_get_time(trade['Date'], quotes, trl_ix)
                max_trails.extend([res_str.format(trl,trl_r['perc'],trl_r[' quote'],tdiff_str)])
        max_trails = "| ".join(max_trails)
        # get min max and their time
        quotes_stats = "| "
        for st, ix in  zip(['min', 'max'],[ quotes['perc'].idxmin(),  quotes['perc'].idxmax()]):
            tdiff_str, trl_r = self.trailing_get_time(trade['Date'], quotes, ix)
            quotes_stats += f"{st},{trl_r['perc']}%,${trl_r[' quote']},in {tdiff_str}| "
        quotes_stats +=  "| " + max_trails
        return quotes_stats

    def trailing_get_time(self, trade_date, quotes, inx):
        trl_r = quotes.loc[inx]
        if pd.isna(trl_r['timestamp']):
            return "", trl_r
        tdiff =  datetime.fromtimestamp(trl_r['timestamp']) - pd.to_datetime(trade_date)
        tdiff_str = str(tdiff.round('s')).replace('0 days ','')
        return tdiff_str, trl_r

    def close_expired(self):
        for i, trade in  self.portfolio.iterrows():
            if trade["Asset"] != "option" or trade["isOpen"] == 0:
                continue
            optdate = option_date(trade['Symbol'])
            if optdate.date() < date.today():
                expdate = date.today().strftime("%Y-%m-%dT%H:%M:%S+0000")
                
                stc_info = calc_stc_prices(trade)
                #Log portfolio
                self.portfolio.loc[i, "STC-Date"] = expdate
                self.portfolio.loc[i, "STC-xQty"] = 1
                for k, v in stc_info.items():
                    self.portfolio.loc[i, k] = v
                
                self.portfolio.loc[i, "isOpen"] = 0
                str_prt = f"{trade['Symbol']} option expired -100%"
                print(str_prt)
        self.portfolio.to_csv(self.portfolio_fname, index=False)

def calc_stc_prices(trade, order=None):
    # if order is None = expired option
    if order is None:
        order = {
            "price":0,
            "Actual Cost":0,
            "expired": True
            }
    bto_price = trade["Price"]
    bto_price_al = trade["Price-actual"]
    
    if not order.get('expired', False):
        if order['Qty'] is None:
            Qty = 1
        else:
            Qty = order['Qty']
    else: 
        if pd.isnull(trade["STC-Qty"]):
            Qty = trade['Qty'] 
        else:
            Qty = trade['Qty'] - trade["STC-Qty"]
    
    if isinstance(bto_price, str):
        bto_price =  np.mean(eval(bto_price.replace("/", ",")))
    if isinstance(bto_price_al, str):
        if bto_price_al[0] == '/':
            bto_price_al = bto_price_al[1:]
        bto_price_al =  np.mean(eval(bto_price_al.replace("/", ",")))
    
    if not pd.isnull(trade["STC-Price"]):  # previous stcs            
        stc_wprice = trade["STC-Price"] * trade["STC-Qty"]
        stc_utotal = trade["STC-Qty"] + Qty
        stc_price = (order.get("price") * Qty +  stc_wprice)/stc_utotal      
        prices = "/".join([str(trade["STC-Prices"]), str(order.get("price"))])
        
        if pd.isnull(trade["STC-Price-actual"]) or pd.isnull(order.get("Actual Cost")):
            prices_curr = 0 if order.get('expired', False) else ""
            stc_price_al = 0 if order.get('expired', False) else None
        else:
            stc_wprice = trade["STC-Price-actual"] * trade["STC-Qty"]
            stc_price_al = (order.get("Actual Cost") * Qty +  stc_wprice)/stc_utotal
            prices_curr = "/".join([str(trade["STC-Prices-actual"]), str(order.get("Actual Cost"))])
    else:  # non-previous stcs   
        stc_price = order.get("price")
        stc_price_al = order.get("Actual Cost")
        stc_utotal = Qty
        prices = order.get("price")
        prices_curr = order.get("Actual Cost")
    
    mutipl = 1 if trade['Asset'] == "option" else .01  # pnl already in %
    if stc_price is not None and stc_price != 0: 
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
                "STC-Prices-actual": prices_curr,
                "STC-Price": stc_price,
                "STC-Price-actual": stc_price_al,
                "STC-Qty": stc_utotal,
                "PnL": stc_pnl,
                "PnL-actual": stc_pnl_al,
                "PnL$": stc_pnl_u,
                "PnL$-actual": stc_pnl_al_u,
                }
    return stc_info
