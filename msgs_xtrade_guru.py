#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr  5 10:44:20 2021

@author: adonay
"""




target = ["217s initial target", '23 target', 'TSLA first target, 840', 
          'first target on BBBY is 28.6', 'target is a break of 11.60',
          'target is the break of 30.5', 'target 3320', 'target is 391.54',
          '557 first target', '68.49 first', 'target is break of 66.7 then 71',
          'looking for 554 on NVDA', 'target for MRVL is high 43s',
          'DAL target is the break of 49', 'LAZR first target, mid 28s',
          'target on ORCL. My bad. 68.07', 'next DAL target is in the 55s',
          '221 target', 'next target on LYFT is 66.3sh', 
          'target for DG is in the 203s', 'RUN target is 64',
          'first WGO target is 76, then 80', "targets for NVDA 575 then 588",
          'first target on NFLX 523', 'target is 149.45 on SPLK',
          'targets are 309 break then 320',
          '50.22 target for DAL', 'ATH test at 78.04', 'Target remains 545']


stop = ['FB 268.71 ish is my stop', 'mental stop 43.6', '202 mental stop', 'AMZN stop under 3307',
        'stop is 390.04 on SPY', '91.8 soft mental stop', 'Stop just under 55', 'stop is 522', 
        'Stop under 73'
        ]


risk = ['very high risk', 'very risky', 'risky', 'yolo']

amnt = ['leaving one in', 'scaling out', 'only got a few', 'selling more',
        'leaving just a few', 'leaving only one', 'trimming more off',
        'leaving about 20%', 'leave one on', 'small position', 'very small position', 'eaving only a few', 'small position']





units_left = '(?:leaving|leave)[ ]*(?:only )?[ ]*(one|two|three)'
left_few = '(?:leaving|leave)[ ]*(?:only|just)?[ ]*[a]? (few)'
left_perc = 'leaving about \d{1,2}%'

partial_3 = ['scaling out', 'selling more', 'trimming more off']


STC = ['selling the ORCL lotto 69p at 2.20 from 0.73',
       "out of my last SPY put",
       'STC CRWD 210c all',
       'took my last RH runner off. Sold',
       'sold last PEP runners here', 
       'NFLX all out 520c',
       'selling my last remain ROKU position', ]


pt1 = ['(target[a-zA-Z\s\,\.]*(\d+[\.]*[\d]*)|(\d+[\.]*[\d]*)[a-zA-Z\s\,\.]*target|looking for (\d+[\.]*[\d]*))']
pt2 = ["target[a-zA-Z0-9\.\s\,]*then (\d+[\.]*[\d]*)"]

stc = "(selling|sold|all out|(:?(out|took)[a-zA-Z\s]*last))"
