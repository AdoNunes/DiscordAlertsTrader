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
from message_parser import parser_alerts
from option_message_parser import option_alerts_parser
from config import (path_dll, data_dir, CHN_NAMES, channel_IDS, discord_token, UPDATE_PERIOD)
from disc_trader import AlertTrader
from colorama import Fore, Back, Style, init


init(autoreset=True)

def updt_chan_hist(df_hist, path_update, path_hist):
    
    last_date = df_hist['Date'].max()
    
    new_msg = pd.read_csv(path_update)
    new_msg = new_msg.loc[new_msg['Date']>last_date]
    
    df_hist = df_hist.append(new_msg, ignore_index=True)    
    df_hist.to_csv(path_hist, index=False)    
    return df_hist, new_msg


def prev_msg_exitUpdate(df_hist, path_update, path_hist):
    
    parser_alerts(msg)
    
    
def update_Edited_msg(df_hist_old, df_hist_upd):
    
    df_hist_upd = df_hist_upd[["Author", 'Content', 'Date']]
    df_hist_old = df_hist_old[["Author", 'Content', 'Date']]
    
    df_hist_upd = df_hist_upd.loc[~(df_hist_upd["Author"] == "Xcapture#0190")]
    df_hist_old = df_hist_old.loc[~(df_hist_old["Author"] == "Xcapture#0190")]
   
        
    since_date = df_hist_upd['Date'].min()
    msg_inxs = df_hist_old['Date'] >= since_date
    
    df_hist_upd.reset_index( inplace=True)
    hist_last = df_hist_old.loc[msg_inxs]
    hist_last.reset_index( inplace=True)
    
    if df_hist_upd.equals(hist_last):
        return None
            
    diff_msg_inx = df_hist_upd['Content'] == hist_last['Content']    
    edited_msg = df_hist_upd.loc[~diff_msg_inx,:]
        
    return edited_msg 
       



    
    
chn_hist_f = {c:f"{data_dir}/{c}_message_history.csv" for c in CHN_NAMES}
chn_hist = {c: pd.read_csv(chn_hist_f[c]) for c in CHN_NAMES}


cmd = 'dotnet {} export -c {}   -t {} -f Csv --after "{}" --dateformat "yyyy-MM-dd HH:mm:ss.ffffff" -o {}'
time_strf = "%Y-%m-%d %H:%M:%S.%f"


last_time = [d['Date'].max() for d in chn_hist.values()]
last_time = [datetime.strptime(d, time_strf) for d in last_time]

time_after = [None]*len(CHN_NAMES)

Alerts_trader = AlertTrader()


while True:
    
    tic = datetime.now()
    for chn_i in range(len(CHN_NAMES)):  
        chn_name = CHN_NAMES[chn_i]
        
        out_file = f"{data_dir}/{chn_name}_temp.csv"
                
        time_diff = (datetime.now() - last_time[chn_i])
        time_after[chn_i] = (datetime.now() - time_diff).strftime(time_strf)  
        
        cmd_sh = cmd.format(path_dll, 
                            channel_IDS[chn_name], 
                            discord_token, 
                            time_after[chn_i], 
                            out_file
                            )
        spro = subprocess.Popen(cmd_sh, shell=True, 
                                stderr=subprocess.PIPE, 
                                stdout=subprocess.PIPE
                                )        
        # Capture if read new messages 
        spro_err = str(spro.communicate()[1])
        new_msgs = False if "ERROR" in spro_err else True
        if new_msgs:
            
            last_time[chn_i] = datetime.now()           

            df_update, new_msg = updt_chan_hist(df_hist=chn_hist[chn_name], 
                                       path_update=f"{data_dir}/{chn_name}_temp.csv",
                                       path_hist=chn_hist_f[chn_name]
                                       )
            
            chn_hist[chn_name] = df_update
            nmsg = len(new_msg)
            print(Style.DIM + f"{last_time[chn_i]} | {chn_name}: got {nmsg} new msgs:")
            
            for ix, msg in new_msg.iterrows():
                   
                if msg['Author'] != "Xcapture#0190":  
                    
                    shrt_date = datetime.strptime(msg["Date"], time_strf
                                                  ).strftime('%H:%M:%S')
                    print(f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")
                    
                    
                    if chn_name.split("_")[0] == "stock":
                        pars, order =  parser_alerts(msg['Content'])
                        msg_type = "stock"
                    elif chn_name.split("_")[0] == "option":
                        pars, order =  option_alerts_parser(msg['Content'])
                        msg_type = "option"
                    else:
                        raise TypeError ("Type of equity not known")
                    
                    
                    if pars is None:                        
                        re_upd = re.compile("trade plan (?:.*?)\*\*([A-Z]*?)\*\*(?:.*?) updated")
                        mark_inf = re_upd.search(msg['Content'])
                        if mark_inf is None:
                            print(Style.DIM + "\t \t MSG NOT UNDERSTOOD")
                            continue
                        
                        symb = mark_inf.groups()[0]
                            
                        time_since = (datetime.now() - timedelta(hours=23)).strftime(time_strf)
                        out_file = f"{data_dir}/{chn_name}_temp_2.csv"
                        
                        cmd_sh = cmd.format(path_dll, 
                            channel_IDS[chn_name], 
                            discord_token, 
                            time_since, 
                            out_file
                            )                        
                        
                        spro = subprocess.Popen(cmd_sh, shell=True, 
                                stderr=subprocess.PIPE, 
                                stdout=subprocess.PIPE
                                )        
                        
                        hist_upd = pd.read_csv(out_file)
                        
                        edited =  update_Edited_msg(chn_hist[chn_name], hist_upd)
                        
                        if edited is not None:
                            df = chn_hist[chn_name]
                            for ix, edit in edited.iterrows():
                                df.loc[df["Date"] == edit["Date"], "Content"] = edit["Content"]
                                print(f"Updated exit plan: \n \t {edit['Content']}")
                                
                                if msg_type == "stock":
                                    pars, order =  parser_alerts(edit['Content'])                                    
                                else:
                                    pars, order =  option_alerts_parser(edit.loc[0, 'Content'])   
                                if order is None:
                                    continue
                                order['action'] = "ExitUpdate"
                                pars.replace("BTO", "ExitUpdate")
                                
                                eval(f"Alerts_trader.new_{msg_type}_alert(order, pars,\
                                 edit['Content'])")
                                
                    elif pars == 'not an alert':
                        print(Style.DIM + "\t \tnot for @everyone")
                    else:
                        print(Fore.RED +f"\t \t {pars}")
                                            
                        if msg['Author'] in [ "ScaredShirtless#0001", "Kevin (Momentum)#4441"]:
                            order["Trader"] = msg['Author']
                            eval(f"Alerts_trader.new_{msg_type}_alert(order, pars,\
                                 msg['Content'])")
    
    toc = datetime.now() 
    tictoc = (toc-tic).total_seconds()

    # wait UPDATE_PERIOD
    if tictoc < UPDATE_PERIOD:
        time.sleep(min(UPDATE_PERIOD-tictoc, UPDATE_PERIOD))


