#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 17:47:06 2021

@author: adonay
"""

import os
import numpy as np
import subprocess
import time
import re
import pandas as pd
from datetime import datetime, timedelta
from message_parser import parser_alerts, get_symb_prev_msg, combine_new_old_orders
from config import (path_dll, data_dir, CHN_NAMES, channel_IDS, discord_token, UPDATE_PERIOD, path_dotnet)
import config as cfg
from disc_trader import AlertTrader
import threading
from colorama import Fore, Back, Style, init
import itertools
import json
from trader_tracker_bot_alerts import Bot_bulltrades_Tracker

if not os.path.exists(data_dir):
    os.mkdir(data_dir)

init(autoreset=True)

def updt_chan_hist(df_hist, path_update):
    last_date = df_hist['Date'].max()

    new_msg = pd.read_csv(path_update)
    if not pd.isna(last_date):
        new_msg = new_msg.loc[new_msg['Date']>last_date]
    return  new_msg


def update_edited_msg(df_hist, json_msg):
    msg_old = []
    for jmsg in json_msg:
        inx, = np.where(df_hist['Date']== jmsg['timestamp'])
        if df_hist.loc[inx, 'Content'].values == jmsg['content']:
            continue

        msg_old.append((inx, df_hist.loc[inx, 'Content'].values[0]))
        df_hist.loc[inx, 'Content']  = jmsg['content']

    return df_hist, msg_old


def msg_update_alert(df_hist, json_msg, asset):
    df_hist, msg_old = update_edited_msg(df_hist, json_msg)

    if msg_old == []:
        return [], []

    new_alerts=[]
    for msg in msg_old:

        _, order_old =  parser_alerts(msg[1], asset)
        msg_content = df_hist.loc[msg[0], "Content"].values[0]
        pars, order_upd = parser_alerts(msg_content, asset)

        if order_old == order_upd:
            continue

        order_upd['Trader'] = df_hist.loc[msg[0], 'Author'].values[0]
        # Previous non edited msg not understood
        if order_old is None and order_upd is not None:
            new_alerts.append([pars,order_upd, msg_content])
            continue

        ex_old = [order_old[f"PT{i}"] for i in range(1,4)] + [order_old['SL']]
        ex_upd = [order_upd[f"PT{i}"] for i in range(1,4)] + [order_upd['SL']]
        if ex_old != ex_upd:
            order_upd['action'] = "ExitUpdate"
            pars.replace("BTO", "ExitUpdate")
            new_alerts.append([pars,order_upd, msg_content])

    return new_alerts, msg_old


def closest_fullname_match(name, names_all):
    """Match first substring in a list from a list of strings,
    eg, name = ["Name"]
    """
    if name is None:
        return name
    candidate = [n for n in names_all if name[0].lower() in n.lower()]
    if candidate == []:
        print ("name not matched")
        return None
    # df unique returned in order of appearence
    # if candidate > 1, return last most recent
    return candidate[-1]


def send_sh_cmd(cmd):
    "takes command string, returns true if no error"
    env = os.environ
    if path_dotnet not in env["PATH"] :
        env["PATH"] =  env["PATH"]+ f"{path_dotnet};."
    try:
        spro = subprocess.Popen(cmd, shell=True, cwd=os.getcwd(), env=env, 
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE
                            )
        spro.wait()
    except OSError as e:
        print(e)
        return False
    # Capture if read new messages
    spro_err = str(spro.communicate()[1])
    if len(spro_err)>3:
        if spro_err == "b'Export failed.\\r\\n'":
            return False
        if "'dotnet' is not recognized" in spro_err:
            return False
        print(spro_err)
    return False if "ERROR" in spro_err else True


def read_json(file_path):
    with open(file_path, "r", errors='ignore') as f:
        data = json.load(f)
    return data


def disc_json_time_corr(time_json):
    """ Mesages from json are 4hs forward

        Original format: '2021-03-19T18:31:01.609+00:00'
        output: dateime object - 4hs !"""

    date = datetime.strptime(time_json.split("+")[0], "%Y-%m-%dT%H:%M:%S.%f")

    return  date + timedelta(hours=-4)


class my_queue():
    def __init__(self, maxsize=10):
        self.maxsize = maxsize
        self.queue = []

    def put(self, item):
        if len(self.queue) >= self.maxsize:
            self.queue.pop(0)
        self.queue.append(item)


class AlertsListner():

    def __init__(self, queue_prints=my_queue(maxsize=10), threaded=True):

        self.UPDATE_PERIOD = cfg.UPDATE_PERIOD
        self.UPDATE_PERIOD_offtradeing = cfg.UPDATE_PERIOD_nontrade_hs
        self.CHN_NAMES = cfg.CHN_NAMES
        self.cmd = f'dotnet {path_dll} export' + ' -c {} -t ' + discord_token  + \
                ' -f Csv --after "{}" --dateformat "yyyy-MM-dd HH:mm:ss.ffffff" -o {}'
        self.time_strf = "%Y-%m-%d %H:%M:%S.%f"
        self.queue_prints = queue_prints

        self.Altrader = AlertTrader(queue_prints=self.queue_prints)       
        self.tracker = Bot_bulltrades_Tracker(TDSession=self.Altrader.TDsession, portfolio_fname=data_dir + "/trade_tracker_portfolio.csv")
        self.listening = False
        self.load_data()
        
        if threaded:
            self.thread =  threading.Thread(target=self.listent_trade_alerts)
            self.thread.start()
        
        self.thread_liveq =  threading.Thread(target=self.track_live_quotes)
        self.thread_liveq.start()


    def load_data(self):
        self.chn_hist= {}
        self.chn_hist_fname = {}
        for ch in cfg.CHN_NAMES:
            dt_fname = f"{data_dir}/{ch}_message_history.csv"
            if not os.path.exists(dt_fname):
                ch_dt = pd.DataFrame(columns=['AuthorID', 'Author', 'Date', 'Content', 'Attachments', 'Reactions', 'Parsed'])
                ch_dt.to_csv(dt_fname, index=False)
                ch_dt.to_csv(f"{data_dir}/{ch}_message_history_temp.csv", index=False)
            else:
                ch_dt = pd.read_csv(dt_fname)
                if "Parsed" not in ch_dt.columns:
                    ch_dt['Parsed'] = pd.Series(dtype='str')

            self.chn_hist_fname[ch] = dt_fname
            self.chn_hist[ch]= ch_dt


    def close(self):
        self.Altrader.update_portfolio = False
        self.listening = False


    def get_edited_msgs(self, chn_id, time_after_last, out_file, hours=1):
        out_json = out_file.replace("csv", "json")

        date_obj = datetime.strptime(time_after_last, self.time_strf)
        date_obj -= timedelta(hours=hours)
        date = date_obj.strftime(self.time_strf)

        cmd = self.cmd.format( chn_id, date, out_json)
        cmd = cmd.replace("Csv", "Json")

        if not send_sh_cmd(cmd):
            return False

        data = read_json(out_json)["messages"]
        msg_edit = []
        for msg in data:
            if msg['timestampEdited']:
                aux = disc_json_time_corr(msg['timestamp'])
                msg['timestamp'] = aux.strftime(self.time_strf)
                msg_edit.append(msg)
        return msg_edit


    def track_live_quotes(self):
        dir_quotes = cfg.data_dir + '/live_quotes'
        os.makedirs(dir_quotes, exist_ok=True)

        while self.listening:
            # Skip closed market
            now = datetime.now()
            weekday, hour = now.weekday(), now.hour
            if  weekday >= 5 or (hour < 9 and hour >= 17):  
                time.sleep(60)
                continue

            # get unique symbols  from portfolios
            track_symb = set(self.tracker.portfolio.loc[self.tracker.portfolio['isOpen']==1, 'Symbol'].to_list() + \
                self.Altrader.portfolio.loc[self.Altrader.portfolio['isOpen']==1, 'Symbol'].to_list())
            # save quotes to file
            try:
                quote = self.Altrader.TDsession.get_quotes(instruments=track_symb)
            except ConnectionError as e:
                print('error during live quote:', e)
                
            for q in quote: 
                if quote[q]['description'] == 'Symbol not found':
                    continue
                timestamp = quote[q]['quoteTimeInLong']//1000  # in ms
                # quote_date = datetime.fromtimestamp(timestamp)
                # if (datetime.now() - quote_date).total_seconds() > 10:
                #     continue                
                if os.path.exists(f"{dir_quotes}/{quote[q]['symbol']}.csv"):
                    do_header = False
                else:
                    do_header = True
                with open(f"{dir_quotes}/{quote[q]['symbol']}.csv", "a+") as f:
                    if do_header:
                        f.write(f"timestamp, quote\n")
                    f.write(f"{timestamp}, {quote[q]['bidPrice']}\n")
            
            # Sleep for up to 5 secs    
            toc = (datetime.now() - now).total_seconds()
            if toc < 5:
                time.sleep(5-toc)


    def listent_trade_alerts(self):
        self.listening = True
        while self.listening:
            tic = datetime.now()
            for chn_i in range(len(self.CHN_NAMES)):
                if chn_i >0: 
                    if datetime.now()-tic < timedelta(seconds=3)* (1+chn_i): 
                        time.sleep(3)  #sleep so doesn't hog
                
                chn = self.CHN_NAMES[chn_i]
                tic0 =  datetime.now()
                out_file = self.chn_hist_fname[chn].replace('.csv', "_temp.csv")
                
                # Decide from when to read alerts 
                time_after = self.chn_hist[chn]['Date'].max()
                if pd.isna(time_after):
                    time_after = (datetime.now() - timedelta(weeks=2)).strftime(self.time_strf)
                else:
                    new_t = min(59.99, float(time_after[-9:]) + .1)
                    time_after = time_after[:-9] + f"{new_t:.6f}"
                tic1 = datetime.now()
                cmd_sh = self.cmd.format(channel_IDS[chn], time_after, out_file)
                new_msgs = send_sh_cmd(cmd_sh)
                tic2 = datetime.now()
                if  tic2-tic1 >timedelta(seconds=3):
                    print(chn, 'before cmd', tic1-tic0, "after", tic2-tic1)
                if not new_msgs:
                    continue

                new_msg = updt_chan_hist(self.chn_hist[chn], out_file )

                nmsg = len(new_msg)
                if nmsg:
                    dnow = short_date(datetime.now())
                    self.queue_prints.put([f"{dnow} | {chn}: got {nmsg} new msgs:", "gray"])
                    print(Style.DIM + f"{dnow} | {chn}: got {nmsg} new msgs:")

                    self.new_msg_acts(new_msg, chn, self.chn_hist_fname[chn])
                
            toc = datetime.now()
            tictoc = (toc-tic).total_seconds()

            # wait UPDATE_PERIOD
            if toc.hour < 9 or toc.hour > 16:
                update_time = self.UPDATE_PERIOD_offtradeing
                self.tracker.close_expired()
            else:
                update_time = self.UPDATE_PERIOD
            if tictoc < update_time:
                time.sleep(min(update_time-tictoc, update_time))


    def new_msg_acts(self, new_msg, chn, out_file):
        # Loop over new msg and take action
        for ix, msg in new_msg.iterrows():

            if msg['Author'] == "Xcapture#0190":
                continue
            
            if pd.isnull(msg['Content']) and self.chn_hist.get(chn) is not None:
                self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
                continue

            if chn.split("_")[0] == "stock":
                asset = "stock"
            elif chn.split("_")[0] == "option":
                asset = "option"
            else:
                asset = None

            shrt_date = datetime.strptime(msg["Date"], self.time_strf).strftime('%Y-%m-%d %H:%M:%S')
            self.queue_prints.put([f"{shrt_date} \t {msg['Author']}: {msg['Content']} ", "blue"])
            print(Fore.BLUE + f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")

            pars, order =  parser_alerts(msg['Content'], asset)
            author = msg['Author']
            order, pars = combine_new_old_orders(msg['Content'], order, pars, author, asset)
            if order is not None and order.get("Symbol") is None:
                # legacy compat, add last message
                df_hist_lastmsg = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                msg_ix = df_hist_lastmsg[df_hist_lastmsg['Content'] == msg['Content']].index.values[-1]
                sym, inxf = get_symb_prev_msg(df_hist_lastmsg, msg_ix, author)
                if sym is not None:
                    order["Symbol"] = sym
                    self.queue_prints.put([f"Got {sym} symbol from previous msg {inxf}, author: {author}", "green"])
                    print(Fore.GREEN + f"Got {sym} symbol from previous msg {inxf}, author: {author}")
                else:
                    pars = None

            if pars is None:
                str_msg = "\t \t MSG NOT UNDERSTOOD"
                self.queue_prints.put([str_msg, "grey"])
                print(Style.DIM + str_msg)
                msg['Parsed'] = ""
                self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
                continue

            else:
                order['Trader'], order["Date"] = msg['Author'], msg["Date"]
                order_date = datetime.strptime(order["Date"], "%Y-%m-%d %H:%M:%S.%f")
                date_diff = datetime.now() - order_date
                print(f"time difference is {date_diff.total_seconds()}")

                live_alert = True if date_diff.seconds < 90 else False
                str_msg = pars
                if live_alert:
                    str_msg += " " + self.Altrader.price_now(order['Symbol'], order["action"], pflag=0)
                self.queue_prints.put([f"\t \t {str_msg}", "green"])
                print(Fore.GREEN + f"\t \t {str_msg}")
                
                self.tracker.trade_alert(order, live_alert, chn)
                if msg['Author'] in cfg.authors_subscribed:
                    order["Trader"] = msg['Author']
                    if cfg.default_stop_lim is not None:
                        order['SL'] = cfg.default_stop_lim
                    self.Altrader.new_trade_alert(order, pars, msg['Content'])
            if self.chn_hist.get(chn) is not None:
                msg['Parsed'] = pars
                self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)


def short_date(dateobj, frm="%Y/%m/%d %H:%M:%S"):
    return dateobj.strftime(frm)


if __name__ == '__main__':
    alistner = AlertsListner(threaded=False)
    alistner.listent_trade_alerts()



