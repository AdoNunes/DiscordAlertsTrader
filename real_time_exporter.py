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
import pandas as pd
from datetime import datetime, timedelta
from message_parser import parser_alerts
from option_message_parser import option_alerts_parser

from config import (path_dll, data_dir, CHN_NAMES, channel_IDS, discord_token, UPDATE_PERIOD)


def updt_chan_hist(df_hist, path_update, path_hist):
    
    last_date = df_hist['Date'].max()
    
    new_msg = pd.read_csv(path_update)
    new_msg = new_msg.loc[new_msg['Date']>last_date]
    
    df_hist = df_hist.append(new_msg, ignore_index=True)    
    df_hist.to_csv(path_hist, index=False)    
    return df_hist, new_msg


chn_hist_f = {c:f"{data_dir}/{c}_message_history.csv" for c in CHN_NAMES}
chn_hist = {c: pd.read_csv(chn_hist_f[c]) for c in CHN_NAMES}


cmd = 'dotnet {} export -c {}   -t {} -f Csv --after "{}" --dateformat "yyyy-MM-dd HH:mm:ss.ffffff" -o {}'
time_strf = "%Y-%m-%d %H:%M:%S.%f"


last_time = [d['Date'].max() for d in chn_hist.values()]
last_time = [datetime.strptime(d, time_strf) for d in last_time]

time_after = [None]*len(CHN_NAMES)

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
            print(f"{last_time[chn_i]} | {chn_name}: got {nmsg} new msgs:")
            
            for ix, msg in new_msg.iterrows():
                if msg['Author'] == "Xcapture#0190":
                    print("\t XcaptureD")
                elif isinstance(msg['Content'], float) and np.isnan(msg['Content']):
                    "NaN msg"
                else:
                    shrt_date = datetime.strptime(msg["Date"], time_strf
                                                  ).strftime('%H:%M:%S')
                    print(f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")
                    
                    if chn_name.split("_")[0] == "stock":
                        pars, order =  parser_alerts(msg['Content'])
                    else:
                        pars, order =  option_alerts_parser(msg['Content'])
                        
                    if pars is None:
                        print(f"\t \t MSG NOT UNDERSTOOD")
                    else:
                        print(f"\t \t {pars}")
            
    toc = datetime.now() 
    tictoc = (toc-tic).total_seconds()

    # wait UPDATE_PERIOD
    if tictoc < UPDATE_PERIOD:
        time.sleep(min(UPDATE_PERIOD-tictoc, UPDATE_PERIOD))


