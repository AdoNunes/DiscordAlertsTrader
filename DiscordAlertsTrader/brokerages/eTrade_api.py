
import webbrowser
import pandas as pd
import pyetrade
import re
import random
from datetime import datetime
import time
import json
import os
import functools

from ..configurator import cfg
from . import BaseBroker

def retry_on_exception(retries=3, do_raise=False, fallback_method=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, retries+1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Exception occurred: {e}. Retrying... (Attempt {attempt}/{retries})")
            
            # if fallback_method:
            #     try:
            #         fallback_method()
            #         return func(*args, **kwargs)
            #     except Exception as e:
            #         print("Could not execute renew access method.", e)
            if do_raise:
                raise Exception(f"Method {func.__name__} failed after {retries} retries.")
            else:
                print(f"Method {func.__name__} failed after {retries} retries. Returning...")
        return wrapper
    return decorator

class eTrade(BaseBroker):
    def __init__(self, account_n=0, accountId=None):
        self.name = 'etrade'
        self.base_url = cfg["etrade"]["PROD_BASE_URL"]
        self.accountId = accountId
        self.account_n = account_n
        self.consumer_key = cfg["etrade"]["CONSUMER_KEY"]
        self.consumer_secret = cfg["etrade"]["CONSUMER_SECRET"]
        self.token_fname = os.path.join(cfg['root']['dir'], "tokens.json")
        
    def get_session(self):
        """get token and sessions, will try several times and sleep for a second between each try"""
        for ix in range(5):
            try:
                return self._get_session()
            except:
                print(ix,"Could not get session, trying again")
                time.sleep(1)
        raise Exception("Could not get session")

    def _get_access_token(self, oauth,verifier_code):
        """Gets access token and tries 3 times before giving up"""        
        for ix in range(3):
            try:
                request_token = oauth.get_access_token(verifier_code)
                return request_token                
            except:
                print(f"Could not get token, trying again {ix}/3")
                time.sleep(1)
        raise Exception("Could not get token")

    def _get_session(self):
        """Allows user authorization for the sample application with OAuth 1"""
        def sessions():
            # get sessions
            kwargs = {
                'client_key': self.consumer_key,
                'client_secret': self.consumer_secret,
                'resource_owner_key': self.tokens['oauth_token'],
                'resource_owner_secret': self.tokens['oauth_token_secret'],
                'dev': False
                }
            self.account_session = pyetrade.ETradeAccounts(**kwargs)
            self.market_session = pyetrade.ETradeMarket(**kwargs)     
            self.order_session = pyetrade.ETradeOrder(**kwargs)
            kwargs.pop('dev')
            self.accessmanager = pyetrade.ETradeAccessManager(**kwargs)
            self._get_account()
            return True
        
        # if tokens saved try getting session
        if os.path.exists(self.token_fname):
            with open(self.token_fname, "r") as f:
                self.tokens = json.load(f)   
            try:
                return sessions()  
            except:
                print("Loaded tokens expired, requesting new tokens")
                os.remove(self.token_fname)  
        
        # if tokens not valid, get new ones
        oauth = pyetrade.ETradeOAuth(self.consumer_key, self.consumer_secret)
        if cfg['etrade'].getboolean('WITH_BROWSER'):
            webbrowser.open(oauth.get_request_token())
        else:
            print("Please open the following URL in your browser:")
            print(oauth.get_request_token())
        verifier_code = input("Please accept agreement and enter verification code from browser: ")
        self.tokens = self._get_access_token(oauth, verifier_code)
        with open(self.token_fname, "w") as f:
            json.dump(self.tokens, f)
        return sessions() 

    def renew_access(self):
        """Renews access token"""
        self.accessmanager.renew_access_token()
        
    @retry_on_exception()
    def _get_account(self):
        """
        Calls account list API to retrieve a list of the user's E*TRADE accounts
        """
        data = self.account_session.list_accounts(resp_format='json')
        self.accounts_list = data["AccountListResponse"]["Accounts"]["Account"]        
        
        if self.accountId is not None:
            self.accountIdKey = [self.accounts_list[i]['accountIdKey'] for i in range(len(self.accounts_list)) 
                                 if self.accounts_list[i]['accountId'] == self.accountId][0]
        else:
            self.accountIdKey = self.accounts_list[self.account_n]['accountIdKey']
            self.accountId = self.accounts_list[self.account_n]['accountId']
        self.account = self.accounts_list[self.account_n]

    @retry_on_exception()
    def get_account_info(self):
        """
        Call portfolio API to retrieve a list of positions held in the specified account
        """
        data = self.account_session.get_account_balance(self.accountIdKey, resp_format='json')        

        balance= {
            'liquidationValue': data['BalanceResponse'].get("Computed").get("RealTimeValues").get("totalAccountValue"),
            'cashBalance': data['BalanceResponse'].get("Computed").get('cashBalance'),
            'availableFunds': data['BalanceResponse'].get("Computed").get('cashAvailableForInvestment'),
            }

        data = self.account_session.get_account_portfolio(self.accountIdKey, resp_format='json')
                
        acc_inf ={
            'securitiesAccount':{   
                'positions':[],
                'accountId' : self.accountId,
                'currentBalances':{
                    'liquidationValue': balance.get('liquidationValue'),
                    'cashBalance': balance.get('cashBalance'),
                    'availableFunds': balance.get('availableFunds'),
                    },
        }}
        # Handle and parse response
        if data is not None and "PortfolioResponse" in data and "AccountPortfolio" in data["PortfolioResponse"]:
            for acctPortfolio in data["PortfolioResponse"]["AccountPortfolio"]:
                if acctPortfolio is not None and "Position" in acctPortfolio:
                    for position in acctPortfolio["Position"]:
                        assetType = position['Product']["securityType"].replace('EQ', 'stock').replace('OPTN', 'OPTION')
                        pos = {
                            "longQuantity" : position['quantity'] if position['positionType'] == 'LONG' else 0,
                            "symbol": position['Product']["symbol"],
                            "marketValue": position['marketValue'],
                            "assetType": assetType,
                            "averagePrice": position['costPerShare'],
                            "currentDayProfitLoss": position['totalGainPct'],
                            "currentDayProfitLossPercentage": position['totalGainPct'],
                            'instrument': {'symbol': position['Product']["symbol"],
                                           'assetType': assetType,
                                           }
                        }
                        acc_inf['securitiesAccount']['positions'].append(pos)
        else:
            print("No portfolio")
            
        # get orders and add them to acc_inf
        orders = self.get_orders()
        orders_inf =[]        
        for order in orders:
            order_status = order['OrderDetail'][0]['status'].upper().replace('EXECUTED','FILLED').replace('OPEN','WORKING')
            if order_status in ['CANCELLED', 'REJECTED', 'EXPIRED']:
                continue
            orders_inf.append(self.format_order(order))
        acc_inf['securitiesAccount']['orderStrategies'] = orders_inf
        return acc_inf

    def get_positions_orders(self):
        try:
            acc_inf = self.get_account_info()
        except:
            print("Could not get account info")
            return [], []
        df_pos = pd.DataFrame(columns=["symbol", "asset", "type", "Qty", "Avg Price", "PnL", "PnL %"])

        for pos in acc_inf['securitiesAccount']['positions']:
            long = True if pos["longQuantity"]>0 else False

            pos_inf = {
                "symbol":pos["instrument"]["symbol"],
                "asset":pos["instrument"]["assetType"],
                "type": "long" if  long else "short",
                "Avg Price": pos['averagePrice'],
                "PnL": pos["currentDayProfitLoss"],
                }
            pos_inf["Qty"] = int(pos[f"{pos_inf['type']}Quantity"])
            pos_inf["PnL %"] = pos_inf["PnL"]/(pos_inf["Avg Price"]*pos_inf["Qty"])
            df_pos =pd.concat([df_pos, pd.DataFrame.from_records(pos_inf, index=[0])], ignore_index=True)

        df_ordr = pd.DataFrame(columns=["symbol", "asset", "type", "Qty",
                                        "Price", "action"])
        return df_pos, df_ordr

    def format_option(self, opt_ticker:str)->str:
        """From ticker_monthdayyear[callput]strike to ticker:year:month:day:optionType:strikePrice"""

        exp = r"(\w+)_(\d{2})(\d{2})(\d{2})([CP])([\d.]+)"        
        match = re.search(exp, opt_ticker, re.IGNORECASE)
        if match:
            symbol, mnt, day, yer, type, strike = match.groups()
            if type.lower() == 'c':
                type = 'Call'
            else:
                type = 'Put'
            converted_code = f"{symbol}:20{yer}:{mnt}:{day}:{type}:{strike}"
            return converted_code
        else:
            print('No format_option match for', opt_ticker)

    @retry_on_exception()
    def get_quotes(self, symbol:list):
        """
        Calls quotes API to provide quote details for equities, options, and mutual funds
        """
        # reformat option tickers

        symbol = [self.format_option(i) if "_" in i else i for i in symbol ]
        
        resp = {}
        for ix in range(0,len(symbol),25):  # lim is 25, loop over 25 symbols at a time
            symbol_l = symbol[ix:ix+25]
            data = self.market_session.get_quote(symbol_l,resp_format='json')

            if data is not None and "QuoteResponse" in data:
                if data["QuoteResponse"].get("Messages"):
                    for message in data["QuoteResponse"]["Messages"]['Message']:
                        ticker = message["description"].split(" ")[0]
                        if ":" in ticker:
                            parts = ticker.split(":")
                            ticker = f"{parts[0]}_{parts[2]}{parts[3]}{parts[1][2:]}{parts[4]}{parts[5].replace('.0','')}"
                        resp[ticker] = {'description': 'Symbol not found'}
                if "QuoteData" in data["QuoteResponse"]:
                    for quote in data["QuoteResponse"]["QuoteData"]:
                        if quote is None:
                            resp[ticker] = {'description': 'Symbol not found'}
                            continue 
                        if  quote.get("Product").get('securityType') == "OPTN":
                            # to common format ticker_monthdayyearstrike[callput]
                            prod = quote['Product']
                            opty = prod['callPut'][0].upper().replace('CALL','C').replace('PUT','P')
                            ticker = f"{prod['symbol']}_{prod['expiryMonth']:02d}{prod['expiryDay']:02d}{str(prod['expiryYear'])[2:]}{opty}{str(prod['strikePrice']).replace('.0','')}"
                        else:
                            ticker =  quote.get("Product").get('symbol')        
                        resp[ticker] = {
                            'symbol' : ticker,
                            'description': quote.get("All").get("symbolDescription"),
                            'askPrice': quote.get("All").get("ask"),  
                            'bidPrice': quote.get("All").get("bid"),    
                            'quoteTimeInLong': quote.get("dateTimeUTC")*1000,
                            "status": quote['quoteStatus']
                            }
                        if resp[ticker]['status'].upper() == 'DELAYED':
                            print("\033[91mWARNING: QUOTES ARE DELAYED by 15 min, setup realtime quotes in etrade.com. Info in github README.md \033[0m")
        return resp

    @retry_on_exception()
    def get_order_info(self, order_id): 
        """ Get order info from order_id, mimicks the order_info from TDA API"""
        orders = self.order_session.list_orders(self.accountIdKey, resp_format='json')        
        for order in orders['OrdersResponse']['Order']:
            if order['orderId'] == order_id:
                order_status = order['OrderDetail'][0]['status'].upper().replace('EXECUTED','FILLED').replace('OPEN','WORKING')
                order_info = self.format_order(order)         
                return order_status, order_info
        return None, None

    def format_order(self, order:dict):
        """ output format for order_response.Order, mimicks the order_info from TDA API"""
        stopPrice= order['OrderDetail'][0]['Instrument'][0].get('stopPrice')
        timestamp = int(order['OrderDetail'][0]['placedTime'])/1000
        enteredTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S+00")
        if 'executedTime' in order['OrderDetail'][0]:
            timestamp = int(order['OrderDetail'][0]['executedTime'])/1000
            closeTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S+00")
        else:
            closeTime = enteredTime
        status = order['OrderDetail'][0]['status'].upper().replace('EXECUTED','FILLED').replace('OPEN','WORKING')
        order_info = {
            'status': status,
            'quantity': order['OrderDetail'][0]['Instrument'][0]['orderedQuantity'],
            'filledQuantity': order['OrderDetail'][0]['Instrument'][0]['filledQuantity'],
            'price':order['OrderDetail'][0]['Instrument'][0].get('averageExecutionPrice'),
            'orderStrategyType': 'SINGLE',
            "order_id" : order['orderId'],
            "orderId": order['orderId'],
            "stopPrice": stopPrice if stopPrice else None,
            'orderType':  order['OrderDetail'][0]['priceType'],
            'enteredTime': enteredTime,
            "closeTime": closeTime,
            'orderLegCollection':[{
                'instrument':{'symbol':order['OrderDetail'][0]['Instrument'][0]['Product']['symbol']},
                'instruction': order['OrderDetail'][0]['Instrument'][0]['orderAction'],
                'quantity': order['OrderDetail'][0]['Instrument'][0]['filledQuantity'],
            }]             
        }    
        return order_info

    @retry_on_exception()
    def send_order(self, new_order:dict):        
        order_response =  self.order_session.place_equity_order(
            resp_format="xml",
            accountId = self.accountId,
            accountIdKey = self.accountIdKey,
            **new_order)
        
        order_id = int(order_response['PlaceOrderResponse']['OrderIds']['orderId'])
        _, ord_inf = self.get_order_info(order_id)
        
        order_response['quantity'] =  int(order_response['PlaceOrderResponse']['Order']['Instrument']['quantity']),
        order_response.update(ord_inf) 
        return order_response, order_id
    
    @retry_on_exception()
    def cancel_order(self, order_id:int):
        time.sleep(.5)  # sleep as order status change is not instant
        resp = self.order_session.cancel_order(self.accountIdKey,order_id, resp_format='xml')
        time.sleep(.5)
        return resp

    def make_BTO_lim_order(self, Symbol:str, uQty:int, price:float, **kwarg):
        "Buy with a limit order"
        kwargs = {}
        kwargs['symbol'] = Symbol
        kwargs['orderAction'] = "BUY"
        if len(Symbol.split("_"))>1:
            Symbol = self.format_option(Symbol)            
            symbol, year, month, day, optype, strike = Symbol.split(":")
            kwargs['symbol'] = symbol
            kwargs['expiryDate'] = f"{year}-{month}-{day}"
            kwargs['strikePrice'] = float(strike)
            kwargs['callPut'] = optype
            kwargs["securityType"] = "OPTN"
            kwargs['orderAction'] = 'BUY_OPEN'        
        kwargs['clientOrderId'] = str(random.randint(1000000000, 9999999999))
        kwargs['priceType'] = 'LIMIT'
        kwargs['limitPrice'] = price    
        kwargs['allOrNone'] = False
        kwargs['quantity'] = uQty       
        kwargs['orderTerm'] = "GOOD_FOR_DAY"
        kwargs['marketSession'] = 'REGULAR'
        return kwargs

    def make_Lim_SL_order(self, Symbol:str, uQty:int,  PT:float, SL:float,  **kwarg):
        """Sell with a limit order and a stop loss order"""
        kwargs = {}
        kwargs['symbol'] = Symbol
        kwargs['orderAction'] = "SELL"
        if len(Symbol.split("_"))>1:
            Symbol = self.format_option(Symbol)            
            symbol, year, month, day, optype, strike = Symbol.split(":")
            kwargs['symbol'] = symbol
            kwargs['expiryDate'] = f"{year}-{month}-{day}"
            kwargs['strikePrice'] = float(strike)
            kwargs['callPut'] = optype
            kwargs["securityType"] = "OPTN"
            kwargs['orderAction'] = 'SELL_CLOSE'
        kwargs['clientOrderId'] = str(random.randint(1000000000, 9999999999))
        kwargs['priceType'] = 'STOP_LIMIT'
        kwargs['limitPrice'] = PT
        kwargs['stopPrice'] = SL
        kwargs['allOrNone'] = False
        kwargs['quantity'] = uQty       
        kwargs['orderTerm'] = "GOOD_UNTIL_CANCEL"
        kwargs['marketSession'] = 'REGULAR'
        return kwargs

    def make_STC_lim(self, Symbol:str, uQty:int, price:float, strike=None, **kwarg):
        """Sell with a limit order and a stop loss order"""
        kwargs = {}
        kwargs['symbol'] = Symbol
        kwargs['orderAction'] = "SELL"
        if len(Symbol.split("_"))>1:
            Symbol = self.format_option(Symbol)            
            symbol, year, month, day, optype, strike = Symbol.split(":")
            kwargs['symbol'] = symbol
            kwargs['expiryDate'] = f"{year}-{month}-{day}"
            kwargs['strikePrice'] = float(strike)
            kwargs['callPut'] = optype
            kwargs["securityType"] = "OPTN"
            kwargs['orderAction'] = 'SELL_CLOSE'
        kwargs['clientOrderId'] = str(random.randint(1000000000, 9999999999))
        kwargs['priceType'] = 'LIMIT'
        kwargs['limitPrice'] = price
        kwargs['allOrNone'] = False
        kwargs['quantity'] = uQty       
        kwargs['orderTerm'] = "GOOD_UNTIL_CANCEL"
        kwargs['marketSession'] = 'REGULAR'
        return kwargs

    def make_STC_SL(self, Symbol:str, uQty:int, SL:float, **kwarg):
        """Sell with a stop loss order"""
        kwargs = {}
        kwargs['symbol'] = Symbol
        kwargs['orderAction'] = "SELL"
        if len(Symbol.split("_"))>1:
            Symbol = self.format_option(Symbol)            
            symbol, year, month, day, optype, strike = Symbol.split(":")
            kwargs['symbol'] = symbol
            kwargs['expiryDate'] = f"{year}-{month}-{day}"
            kwargs['strikePrice'] = float(strike)
            kwargs['callPut'] = optype
            kwargs["securityType"] = "OPTN"
            kwargs['orderAction'] = 'SELL_CLOSE'
        kwargs['clientOrderId'] = str(random.randint(1000000000, 9999999999))
        kwargs['priceType'] = 'STOP'
        kwargs['stopPrice'] = int(SL)
        kwargs['allOrNone'] = False
        kwargs['quantity'] = uQty       
        kwargs['orderTerm'] = "GOOD_UNTIL_CANCEL"
        kwargs['marketSession'] = 'REGULAR'

    def make_STC_SL_trailstop(self, Symbol:str, uQty:int,  trail_stop_const:float, **kwarg):
        "trail_stop_const"
        kwargs = {}
        kwargs['symbol'] = Symbol
        kwargs['orderAction'] = "SELL"
        if len(Symbol.split("_"))>1:
            Symbol = self.format_option(Symbol)            
            symbol, year, month, day, optype, strike = Symbol.split(":")
            kwargs['symbol'] = symbol
            kwargs['expiryDate'] = f"{year}-{month}-{day}"
            kwargs['strikePrice'] = float(strike)
            kwargs['callPut'] = optype
            kwargs["securityType"] = "OPTN"
            kwargs['orderAction'] = 'SELL_CLOSE'       
        kwargs['clientOrderId'] = str(random.randint(1000000000, 9999999999))
        kwargs['priceType'] = 'TRAILING_STOP_CNST'
        kwargs['stopPrice'] = trail_stop_const
        kwargs['allOrNone'] = False
        kwargs['quantity'] = uQty       
        kwargs['orderTerm'] = "GOOD_UNTIL_CANCEL"
        kwargs['marketSession'] = 'REGULAR'
        return kwargs

    @retry_on_exception()
    def get_orders(self):
        orders = self.order_session.list_orders(self.accountIdKey, resp_format='json')
        orders = orders['OrdersResponse']['Order']
        return orders



if 0:
    rt = eTrade()
    rt.get_session()
    rt.get_account_info()
    rt.get_quotes(["AAPL", 'NIO:2023:08:18:P:4'])

    order = rt.make_STC_lim('NIO_081823P4', 1, 0.07)
    order_response, order_id = rt.send_order(order)

    order = rt.make_BTO_lim_order('VERB', 1, 1.7)
    order_response, order_id = rt.send_order(order)
    res = rt.cancel_order(order_id)

    order = rt.make_Lim_SL_order('VERB', 1,  1.8, 1.5)
    order_response, order_id = rt.send_order(order)
    res = rt.cancel_order(order_id)
    
    order = rt.make_STC_SL_trailstop('VERB', 1, 40)
    order_response, order_id = rt.send_order(order)
    res = rt.cancel_order(order_id)