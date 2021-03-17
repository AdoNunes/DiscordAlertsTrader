#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 17 16:38:15 2021

@author: adonay
"""


import threading
import time
from datetime import datetime, timedelta
import asyncio

class first():
    def __init__(self):
        
        self.UPDATE_PERIOD = 5
               

        self.msg = None
        self.listening = False
        self.secnd = second()
 
        # self.thread =  threading.Thread(target=self.listent_trade_alerts)
        # self.thread.start()
    
    def start(self):
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.listent_trade_alerts())
        loop.close()
        
    async def listent_trade_alerts(self):
        
        self.listening = True 
        
        
        while self.listening:
            
            tic = datetime.now()
            
            self.msg = self.secnd.user_in(self.msg)
            print(self.msg)
            toc = datetime.now() 
            tictoc = (toc-tic).total_seconds()
        
            # wait UPDATE_PERIOD
            if tictoc < self.UPDATE_PERIOD:
                await asyncio.sleep(min(self.UPDATE_PERIOD-tictoc, self.UPDATE_PERIOD))
                


class second():
    def __init__(self):
        self.msg = "Second"
        
        
    def user_in(self, msg):   
        resp = input(f"the message is: {msg}")
        return resp
        
        

f = first()
