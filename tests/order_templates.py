#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order templates to test functionality Alerts_Trader

Created on Wed Mar 10 21:54:37 2021

@author: adonay
"""

import json


# # Save dic obtained from TDsession.get_orders
# with open("order_info_template.json", "w") as js:
#     json.dump(order_info, js)


order_BTO_PT_LT = {
    'action': 'BTO',
    'Symbol': 'DPW',
    'price': 3.1,
    'avg': None,
    'PT1': 5.84,
    'PT2': 6.39,
    'PT3': 6.95,
    'SL': 3.01,
    'n_PTs': 3,
    'PTs_Qty': [1],
    'Trader': 'ScaredShirtless#0001',
    'PTs': [5.84],
    'uQty': 20
    }


# Save json dic with order BTO + OCO{Pt, Sl}, equivalent to TDSession.get_orders()
order_response_BTO_PT_LT = {
    'order_id': '2259360954',
     'headers': {'Date': 'Thu, 11 Mar 2021 03:04:55 GMT', 
                 'Content-Length': '0', 
                 'Connection': 'keep-alive',
                 'Location': 'https://api.tdameritrade.com/v1/accounts/123456789/orders/2259360954',
                 'X-API-Version': '1.11.5',
                 'Cache-Control': 'no-cache, no-store, max-age=0, must-revalidate',
                 'Pragma': 'no-cache',
                 'Expires': '0',
                 'X-XSS-Protection': '1; mode=block',
                 'X-Frame-Options': 'DENY, SAMEORIGIN',
                 'X-Content-Type-Options': 'nosniff',
                 'Access-Control-Allow-Headers': 'origin, x-requested-with, accept, authorization, content-type, correlationid, apikey, application-name',
                 'Access-Control-Max-Age': '3628800',
                 'Access-Control-Allow-Methods': 'GET, PUT, POST, DELETE, OPTIONS, HEAD, PATCH',
                 'Content-Security-Policy': "frame-ancestors 'self'",
                 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains, max-age=31536000'},
    'content': "",
    'status_code': 201,
    'request_body': {
       "orderStrategyType": "TRIGGER",
       "orderType": "LIMIT", 
       "session": "NORMAL",
       "duration": "GOOD_TILL_CANCEL",
       "price": 3.1, 
       "orderLegCollection": [
           {
               "instruction": "BUY",
               "quantity": 20,
               "instrument": { 
                   "assetType": "EQUITY",
                   "symbol": "DPW"}
                   }
               ],
       "childOrderStrategies": [
           {
               "orderStrategyType": "OCO",
               "childOrderStrategies": [
                   {
                       "orderStrategyType": "SINGLE",
                        "orderType": "LIMIT",
                        "session": "NORMAL",
                        "duration": "GOOD_TILL_CANCEL",
                        "price": 5.84,
                        "orderLegCollection": [
                            {
                                "instruction": "SELL",
                                "quantity": 20,
                                "instrument": {
                                    "assetType": "EQUITY",
                                    "symbol": "DPW"}
                                    }
                                ]
                            }, 
                       {
                            "orderStrategyType": "SINGLE",
                            "session": "NORMAL",
                            "duration": "GOOD_TILL_CANCEL",
                            "orderType": "STOP",
                            "stopPrice": 3.01,
                            "orderLegCollection": [
                                {
                                    "instruction": "SELL",
                                    "quantity": 20,
                                    "instrument": {
                                        "assetType": "EQUITY",
                                        "symbol": "DPW"
                                        }
                                    }
                                ]
                            }
                           ]
                   }
               ]
           },
    'request_method': 'POST'}

order_response_BTO_PT_LT['request_body'] = str(order_response_BTO_PT_LT['request_body'])


order_info_BTO_PT_LT = {
    'session': 'NORMAL',
    'duration': 'GOOD_TILL_CANCEL',
    'orderType': 'LIMIT',
    'cancelTime': '2021-09-03',
    'complexOrderStrategyType': 'NONE',
    'quantity': 20,
    'filledQuantity': 0.0,
    'remainingQuantity': 20,
    'requestedDestination': 'AUTO',
    'destinationLinkName': 'AutoRoute',
    'price': 3.1,
    'orderLegCollection': [
        {
            'orderLegType': 'EQUITY',
            'legId': 1,
            'instrument': {
                'assetType': 'EQUITY',
                'cusip': '05150X104',
                'symbol': 'DPW'
                },
          'instruction': 'BUY',
          'positionEffect': 'OPENING',
          'quantity': 20
          }
        ],
    'orderStrategyType': 'TRIGGER',
    'orderId': 2259360954,
    'cancelable': True,
    'editable': False,
    'status': 'WORKING',
    'enteredTime': '2021-03-11T03:04:55+0000',
    'tag': 'AA_adonaynunes1',
    'accountId': 123456789,
    'childOrderStrategies': [
        {
            'orderStrategyType': 'OCO',
            'orderId': 2259360956,
            'cancelable': True,
            'editable': False,
            'accountId': 123456789,
            'childOrderStrategies': [
                {
                    'session': 'NORMAL',
                    'duration': 'GOOD_TILL_CANCEL',
                    'orderType': 'STOP',
                    'cancelTime': '2021-09-03',
                    'complexOrderStrategyType': 'NONE',
                    'quantity': 20,
                    'filledQuantity': 0.0,
                    'remainingQuantity': 20,
                    'requestedDestination': 'AUTO',
                    'destinationLinkName': 'AutoRoute',
                    'stopPrice': 3.01,
                    'orderLegCollection': [
                        {
                            'orderLegType': 'EQUITY',
                            'legId': 1,
                            'instrument': {
                                'assetType': 'EQUITY',
                                'cusip': '05150X104',
                                'symbol': 'DPW'
                                },
                            'instruction': 'SELL',
                            'positionEffect': 'CLOSING',
                            'quantity': 20
                            }
                        ],
                    'orderStrategyType': 'SINGLE',
                    'orderId': 2259360957,
                    'cancelable': True,
                    'editable': False,
                    'status': 'ACCEPTED',
                    'enteredTime': '2021-03-11T03:04:55+0000',
                    'tag': 'AA_aaaaaaaaa',
                    'accountId': 123456789
                    },
       {
        'session': 'NORMAL',
        'duration': 'GOOD_TILL_CANCEL',
        'orderType': 'LIMIT',
        'cancelTime': '2021-09-03',
        'complexOrderStrategyType': 'NONE',
        'quantity': 20,
        'filledQuantity': 0.0,
        'remainingQuantity': 20,
        'requestedDestination': 'AUTO',
        'destinationLinkName': 'AutoRoute',
        'price': 5.84,
        'orderLegCollection': [
            {
                'orderLegType': 'EQUITY',
                'legId': 1,
                'instrument': {
                    'assetType': 'EQUITY',
                    'cusip': '05150X104',
                    'symbol': 'DPW'
                    },
                'instruction': 'SELL',
                'positionEffect': 'CLOSING',
                'quantity': 20
                }
            ],
        'orderStrategyType': 'SINGLE',
        'orderId': 2259360956,
        'cancelable': True,
        'editable': False,
        'status': 'ACCEPTED',
        'enteredTime': '2021-03-11T03:04:55+0000',
        'tag': 'AA_adonaynunes1',
        'accountId': 123456789
        }
       ]
        }
        ]
    }


with open("order_response_BTO_PT_LT_template.json", "w") as js:
    json.dump(order_response_BTO_PT_LT, js)

