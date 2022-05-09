#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 17:47:06 2021

@author: adonay
"""

from calendar import month
import os
import ssl
import numpy as np
import subprocess
import time
import re
import queue
import pandas as pd
from datetime import datetime, timedelta
from message_parser import parser_alerts, get_symb_prev_msg, combine_new_old_orders
from config import (path_dll, data_dir, CHN_NAMES, chn_IDS, discord_token, UPDATE_PERIOD, path_dotnet)
import config as cfg
from disc_trader import AlertTrader
import threading
from colorama import Fore, Back, Style, init
import itertools
import json
from trader_tracker import Trades_Tracker



init(autoreset=True)

def updt_chan_hist(df_hist, path_update, path_hist):

    last_date = df_hist['Date'].max()

    new_msg = pd.read_csv(path_update)
    if not pd.isna(last_date):
        new_msg = new_msg.loc[new_msg['Date']>last_date]

    df_hist = pd.concat([df_hist, new_msg],axis=0, ignore_index=True)
    df_hist.to_csv(path_hist, index=False)
    return df_hist, new_msg


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


def dm_message(msg, names_all):

    if "author:" in msg or "A:" in msg:
        re_author = re.compile("(?:author|A):[ ]?(\w+)")
        auth_inf = re_author.search(msg)

        author = closest_fullname_match(auth_inf.groups(), names_all)

        re_author = re.compile("ms:[ ]?(\w+)")

        content = msg[auth_inf.span()[1]+1:]

    else:
        author = "Me"

        content = msg

    if "asset:" in msg or "AS:" in msg:
        re_ass = re.compile("(?:asset|AS):[ ]?(\w+)")
        ass_inf = re_ass.search(msg)
        asset = ass_inf.groups()[0]
    else:
        asset = None

    return author, asset, content


def send_sh_cmd(cmd):
    "takes command string, returns true if no error"
    env = os.environ
    env["PATH"] =  env["PATH"][:-1]+ f"{path_dotnet};."
    spro = subprocess.Popen(cmd, shell=True, cwd=os.getcwd(), env=env, 
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE
                            )
    # Capture if read new messages
    spro_err = str(spro.communicate()[1])
    if len(spro_err)>3:
        if spro_err == "b'Export failed.\\r\\n'":
            return False
        print(spro_err)
    return False if "ERROR" in spro_err else True

def read_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


def disc_json_time_corr(time_json):
    """ Mesages from json are 4hs forward

        Original format: '2021-03-19T18:31:01.609+00:00'
        output: dateime object - 4hs !"""

    date = datetime.strptime(time_json.split("+")[0], "%Y-%m-%dT%H:%M:%S.%f")

    return  date + timedelta(hours=-4)

def null_print(*args, **kwargs):
    pass

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
        self.CHN_NAMES = cfg.CHN_NAMES

        self.cmd = f'dotnet {path_dll} export' + ' -c {} -t ' + discord_token  + \
                ' -f Csv --after "{}" --dateformat "yyyy-MM-dd HH:mm:ss.ffffff" -o {}'

        self.time_strf = "%Y-%m-%d %H:%M:%S.%f"
        self.queue_prints = queue_prints

        self.Altrader = AlertTrader(queue_prints=self.queue_prints)
        self.tracker = Trades_Tracker(TDSession=self.Altrader.TDsession)
        self.listening = False
        self.load_data()
        
        if threaded:
            self.thread =  threading.Thread(target=self.listent_trade_alerts)
            self.thread.start()

    def load_data(self):
        self.chn_hist= {}
        self.chn_hist_fname = {}
        for ch in cfg.CHN_NAMES:
            dt_fname = f"{data_dir}/{ch}_message_history.csv"
            if not os.path.exists(dt_fname):
                ch_dt = pd.DataFrame(columns=['AuthorID', 'Author', 'Date', 'Content', 'Attachments', 'Reactions'])
                ch_dt.to_csv(dt_fname, index=False)
                ch_dt.to_csv(f"{data_dir}/{ch}_message_history_temp.csv", index=False)
            else:
                ch_dt = pd.read_csv(dt_fname)

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


    def listent_trade_alerts(self):

        self.listening = True

        while self.listening:

            tic = datetime.now()
            for chn_i in range(len(self.CHN_NAMES)):
                chn = self.CHN_NAMES[chn_i]

                out_file = self.chn_hist_fname[chn].replace('.cvs', "temp.csv")
                
                # Decide from when read alerts 
                time_after = self.chn_hist[chn]['Date'].max()
                if pd.isna(time_after):
                    time_after = (datetime.now() - timedelta(weeks=2)).strftime(self.time_strf)
                else:
                    new_t = min(59.99, float(time_after[-9:]) + .1)
                    time_after = time_after[:-9] + f"{new_t:.6f}"
                
                cmd_sh = self.cmd.format(chn_IDS[chn], time_after, out_file)
                new_msgs = send_sh_cmd(cmd_sh)

                if not new_msgs:
                    continue

                df_update, new_msg = updt_chan_hist(self.chn_hist[chn], out_file, self.chn_hist_fname[chn])
                self.chn_hist[chn] = df_update

                nmsg = len(new_msg)
                if nmsg:
                    dnow = short_date(datetime.now())
                    self.queue_prints.put([f"{dnow} | {chn}: got {nmsg} new msgs:", "gray"])
                    print(Style.DIM + f"{dnow} | {chn}: got {nmsg} new msgs:")

                    self.new_msg_acts(new_msg, chn, out_file)

            toc = datetime.now()
            tictoc = (toc-tic).total_seconds()

            # wait UPDATE_PERIOD
            if tictoc < self.UPDATE_PERIOD:
                time.sleep(min(self.UPDATE_PERIOD-tictoc, self.UPDATE_PERIOD))


    def new_msg_acts(self, new_msg, chn, out_file):
        # Loop over new msg and take action
        for ix, msg in new_msg.iterrows():

            if msg['Author'] == "Xcapture#0190" or pd.isnull(msg['Content']):
                continue

            if chn.split("_")[0] == "stock":
                asset = "stock"
            elif chn.split("_")[0] == "option":
                asset = "option"
            else:
                asset = None

            # Private DM message
            if chn == 'DM_xcapture':
                # Get authors names from non-DM servers
                names_all = [self.chn_hist[n]['Author'].unique() for n in self.CHN_NAMES if n[:2] != "DM"]
                names_all = list(itertools.chain(*names_all))

                author, asset, content = dm_message(msg["Content"], names_all)
                self.queue_prints.put([f"DM: {author}, {asset}, {content},", "blue"])
                print("DM: ", author, asset, content)
                msg['Author'] = author
                msg["Content"] = content

            shrt_date = datetime.strptime(msg["Date"], self.time_strf).strftime('%Y-%m-%d %H:%M:%S')
            self.queue_prints.put([f"{shrt_date} \t {msg['Author']}: {msg['Content']} ", "blue"])
            print(Fore.BLUE + f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")

            pars, order =  parser_alerts(msg['Content'], asset)
            author = msg['Author']
            order, pars = combine_new_old_orders(msg['Content'], order, pars, author, asset)
            if order is not None and order.get("Symbol") is None:
                df_hist = self.chn_hist[chn]
                msg_ix, = df_hist[df_hist['Content'] == msg['Content']].index.values
                sym, inxf = get_symb_prev_msg(df_hist, msg_ix, author)
                if sym is not None:
                    order["Symbol"] = sym
                    self.queue_prints.put([f"Got {sym} symbol from previous msg {inxf}, author: {author}", "green"])
                    print(Fore.GREEN + f"Got {sym} symbol from previous msg {inxf}, author: {author}")
                else:
                    pars = None

            if pars is None:
                # Check if msg alerting exitUpdate in prev msg
                if msg['Author'] in cfg.authors_subscribed:
                    re_upd = re.compile("(?:T|t)rade plan[a-zA-Z\s\,\.]*\*{2}([A-Z]*?)\*{2}[a-zA-Z\s\,\.]* updated")
                    upd_inf = re_upd.search(msg['Content'])
                    if upd_inf:
                        self.queue_prints.put(["Updating trade plan msg:", "green"])
                        print(Fore.GREEN + "Updating trade plan msg:")

                time_after = self.chn_hist[chn]['Date'].max()
                json_msg = self.get_edited_msgs(chn_IDS[chn], time_after, out_file)

                new_alerts, _ = msg_update_alert(self.chn_hist[chn], json_msg, asset)

                if new_alerts == []:
                    self.queue_prints.put(["\t \t MSG NOT UNDERSTOOD", "grey"])
                    print(Style.DIM + "\t \t MSG NOT UNDERSTOOD")
                    continue

                self.queue_prints.put(["Updating edited msgs", "green"])
                print(Fore.GREEN + "Updating edited msgs")

                for alert in new_alerts:
                    self.queue_prints.put([alert[2], "green"])
                    print(Fore.GREEN + alert[2])
                    pars, order, msg_str = alert

                    self.tracker.trade_alert(order, pars, msg_str, live_alert=True)

                    if order['Trader'] in cfg.authors_subscribed:
                        self.Altrader.new_trade_alert(order, pars, msg_str)

            elif pars == 'not an alert':
                self.queue_prints.put(["\t \tnot for @everyone", "grey"])
                print(Style.DIM + "\t \tnot for @everyone")

            else:
                self.queue_prints.put([f"\t \t {pars}", "green"])
                print(Fore.GREEN + f"\t \t {pars}")
                order['Trader'] = msg['Author']
                order["Date"] = msg["Date"]
                order_date = datetime.strptime(order["Date"], "%Y-%m-%d %H:%M:%S.%f")
                date_diff = order_date - datetime.now()
                live_alert = True if date_diff.seconds < 60 else False
                self.tracker.trade_alert(order, pars, msg['Content'],
                                         live_alert=live_alert)
                if msg['Author'] in cfg.authors_subscribed:
                    order["Trader"] = msg['Author']
                    self.Altrader.new_trade_alert(order, pars,\
                          msg['Content'])



def short_date(dateobj, frm="%Y/%m/%d %H:%M:%S"):
    return dateobj.strftime(frm)




if __name__ == '__main__':
    alistner = AlertsListner(threaded=False)
    alistner.listent_trade_alerts()



