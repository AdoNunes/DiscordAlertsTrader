#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun  9 09:36:51 2021

@author: adonay
"""
from DiscordAlertsTrader.message_parser import parse_trade_alert

import unittest
import os

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestMessageParser(unittest.TestCase):

    def test_messages(self):
        msgs = [
        "BTO DPW @3.7 PT1: 3.72 PT2: 4.39 PT3:5.96 SL: 3.01",
        'BTO 1 AAPL 190C 07/21 @ 3 PT: 85%TS10% SL: 50%',
        'BTO 1 TSLA 190C 07/21 @ 3 PT: 85%TS10% SL: 50%',
        'BTO 1 TSLA 190C 07/21 @ 3 PT: 3.9TS10% SL: 50%',
        "BTO 200 CHSN @ 2.57 <@&1050033416185335808> (playing the momentum to upside off VWAP, High Risk low float) ",
        "BTO 1 COIN 73c 04/06 @ 1.03 @here (Swing) @Cblast Alert",
        "BTO 1 DPW @3.7 PT1 3.72 SL: 3.01",
        "BTO 10 TSLA 282.5C 07/14 @ 0.96 PT: 125%TS30% SL: 75%",
        "STC  2 QQQ 297c 3/8 @ .7 @here",
        "BTO 2 SPY 393c 3/20 @1.3 @here",
        "STC 2 SPY 393c 3/20 @ 1.0 @here @EM Alert"
        "STC 300 POLA @ 1.7",
        "STC PNC 140c 07/21/2023 @ 1.4 <@&1037722002145935360> ( 79%)"
        ]

        expect = [
            ('BTO DPW 3.7 , PT1:3.72, PT2:4.39, PT3:5.96, SL:3.01',
            {'action': 'BTO', 'Symbol': 'DPW', 'Qty': None, 'price': 3.7, 'asset': 'stock', 'risk': None,
            'avg': None, 'PT1': '3.72', 'PT2': '4.39', 'PT3': '5.96', 'SL': '3.01', 'n_PTs': 3, 'PTs_Qty': [0.33, 0.33, 0.34]}),
            ('BTO 1 AAPL 190C 07/21 3 , PT1:85%TS10%, PT2:None, PT3:None, SL:50%',
            {'action': 'BTO', 'Symbol': 'AAPL_072123C190', 'Qty': 1, 'price': 3.0, 'asset': 'option',
            'strike': '190C', 'expDate': '07/21', 'risk': None, 'avg': None, 'PT1': '85%TS10%', 'PT2': None,
            'PT3': None, 'SL': '50%', 'n_PTs': 1, 'PTs_Qty': [1]}),
            ('BTO 1 TSLA 190C 07/21 3 , PT1:85%TS10%, PT2:None, PT3:None, SL:50%',
            {'action': 'BTO', 'Symbol': 'TSLA_072123C190', 'Qty': 1, 'price': 3.0, 'asset': 'option',
            'strike': '190C', 'expDate': '07/21', 'risk': None, 'avg': None, 'PT1': '85%TS10%', 'PT2': None,
            'PT3': None, 'SL': '50%', 'n_PTs': 1, 'PTs_Qty': [1]}),
            ('BTO 1 TSLA 190C 07/21 3 , PT1:3.9TS10%, PT2:None, PT3:None, SL:50%',
            {'action': 'BTO', 'Symbol': 'TSLA_072123C190', 'Qty': 1, 'price': 3.0, 'asset': 'option',
            'strike': '190C', 'expDate': '07/21', 'risk': None, 'avg': None, 'PT1': '3.9TS10%', 'PT2': None,
            'PT3': None, 'SL': '50%', 'n_PTs': 1, 'PTs_Qty': [1]}),
            ('BTO 200 CHSN 2.57 high ',
            {'action': 'BTO', 'Symbol': 'CHSN', 'Qty': 200, 'price': 2.57, 'asset': 'stock', 'risk': 'high',
            'avg': None, 'PT1': None, 'PT2': None, 'PT3': None, 'SL': None, 'n_PTs': 0, 'PTs_Qty': [1]}),
            ('BTO 1 COIN 73c 04/06 1.03 ',
            {'action': 'BTO', 'Symbol': 'COIN_040623C73', 'Qty': 1, 'price': 1.03, 'asset': 'option',
            'strike': '73C', 'expDate': '04/06', 'risk': None, 'avg': None, 'PT1': None, 'PT2': None,
            'PT3': None, 'SL': None, 'n_PTs': 0, 'PTs_Qty': [1]}),
            ('BTO 1 DPW 3.7 , PT1:3.72, PT2:None, PT3:None, SL:3.01',
            {'action': 'BTO', 'Symbol': 'DPW', 'Qty': 1, 'price': 3.7, 'asset': 'stock', 'risk': None,
            'avg': None, 'PT1': '3.72', 'PT2': None, 'PT3': None, 'SL': '3.01', 'n_PTs': 1, 'PTs_Qty': [1]}),
            ('BTO 10 TSLA 282.5C 07/14 0.96 , PT1:125%TS30%, PT2:None, PT3:None, SL:75%',
            {'action': 'BTO', 'Symbol': 'TSLA_071423C282.5', 'Qty': 10, 'price': 0.96, 'asset': 'option',
            'strike': '282.5C', 'expDate': '07/14', 'risk': None, 'avg': None, 'PT1': '125%TS30%', 'PT2': None,
            'PT3': None, 'SL': '75%', 'n_PTs': 1, 'PTs_Qty': [1]}),
            ('STC 2 QQQ 297c 3/8 .7 ',
            {'action': 'STC', 'Symbol': 'QQQ_030823C297', 'Qty': 2, 'price': 0.7, 'asset': 'option',
            'strike': '297C', 'expDate': '3/8', 'risk': None, 'xQty': 1}),
            ('BTO 2 SPY 393c 3/20 1.3 ',
            {'action': 'BTO', 'Symbol': 'SPY_032023C393', 'Qty': 2, 'price': 1.3, 'asset': 'option',
            'strike': '393C', 'expDate': '3/20', 'risk': None, 'avg': None, 'PT1': None, 'PT2': None,
            'PT3': None, 'SL': None, 'n_PTs': 0, 'PTs_Qty': [1]}),
            ('STC 2 SPY 393c 3/20 1.0 ',
            {'action': 'STC', 'Symbol': 'SPY_032023C393', 'Qty': 2, 'price': 1.0, 'asset': 'option',
            'strike': '393C', 'expDate': '3/20', 'risk': None, 'xQty': 1}),
            ('STC PNC 140c 07/21 1.4  xamount: 1',
            {'action': 'STC', 'Symbol': 'PNC_072123C140', 'Qty': None, 'price': 1.4, 'asset': 'option',
            'strike': '140C', 'expDate': '07/21', 'risk': None, 'xQty': 1})
            ]

        for msg, exp in zip(msgs,expect):
            self.assertEqual(parse_trade_alert(msg), exp)
        
    
if __name__ == '__main__':
    unittest.main()