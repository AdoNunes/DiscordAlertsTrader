#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  9 09:36:51 2021

@author: adonay
"""
from DiscordAlertsTrader.message_parser import parser_alerts

import re

exp = r'\b(BTO|STC)\b\s*(\d+)?\s*([A-Z]+)\s*(\d+[cp])?\s*(\d{1,2}\/\d{1,2})?\s*@\s*[$]*[ ]*(\d+(?:\.\d+)?|\.\d+)'

'\b(BTO|STC)\b\s*(\d+)?\s*([A-Z,a-z]+)\s*(\d+[cp])?\s*((\d{1,2}\/\d{1,2}(\/(20\d{2}))?))?\s*@\s*[$]*[ ]*(\d+(?:\.\d+)?|\.\d+)'

exit_examples = [("BTO AEHL @ 7 (risky scalp. PT 8.39, SL below 6.45) @everyone", (8.39, None, None, 6.45)),
                 ("BTO CPB @ 45.95 (SL $43, PT 49, posted this in watchlist on monday", (49.0, None, None, 43.0)),
                 ("Price Target: 185 Stop: 200", (185, None,None, 200)),
                 ("SL around 388.5 PT 380"),
                 ("BTO 1 COIN 73c 04/06 @ 1.03 @here (Swing) @Cblast Alert"),
                 "AVI#9896: STC PNC 140c 07/21/2023 @ 1.4 <@&1037722002145935360> ( 79%)"
                 
]

alert = exit_examples[0][0]
option = re.search(exp, alert, re.IGNORECASE)
print(option.groups())

alerts_exampes  = [("BTO 1 TSLA 195p 03/31 @ 4.75 @here (Day Trade/Swing) @Cblast Alert", ("BTO TSLA 03/31 195P  @4.75")),
                    "BTO 5 QQQ 301p @ .63",
                    "STC 4 QQQ 301p @ .88 @here @EM Alert",
                    "STC  2 QQQ 297c 3/8 @ .7 @here",
                    "BTO 2 SPY 393c 3/20 @c1.3 @here",
                    "STC 2 SPY 393c 3/20 @ 1.0 @here @EM Alert",
                    "BTO 5 QQQ 314c 4/25 @ .1.01 5% sz HIGH RISK  @Cedar Alert  voice",
                    "BTO 4 SPY 415c 5/3 @ 1,61" ,
                    "BTO 200 CHSN @ 2.57 <@&1050033416185335808> (playing the momentum to upside off VWAP, High Risk low float) "
                    "STC 300 POLA @ 1.7"
                    
    
]

'BTO 5 AI 25c 5/19 @ 1 <@&940418825235619910> swinging'
"BTO TSLA 180p 3/17 @ .59 @here @EM Alert", "BTO 3 TSLA 180p 3/17 @ .54"


order = {'action': 'BTO',
    'Symbol': 'DPW',
    'price': 3.7,
    'avg': None,
    'PT1': 3.72,
    'PT2': 4.39,
    'PT3': 5.95,
    'SL': 3.65,
    'n_PTs': 3,
    'PTs_Qty': [.33, .33, .34],
    'Trader': 'ScaredShirtless#0001',
    'PTs': [5.84],
    'uQty': 3}

pars = "BTO DPW @3.7 PT1: 3.72 PT2: 4.39 PT3:5.96 SL: 3.01"
msg = "BTO DPW @3.7 PT1 3.72 SL: 3.01"