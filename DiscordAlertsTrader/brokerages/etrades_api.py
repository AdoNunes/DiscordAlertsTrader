
import webbrowser
import pandas as pd
import pyetrade
import re
import random
from DiscordAlertsTrader.configurator import cfg


# price: number
# round_down: bool
# return string
def to_decimal_str(price: float, round_down: bool) -> str:
    spstr = "%.2f" % price  # round to 2-place decimal
    spstrf = float(spstr)  # convert back to float again
    diff = price - spstrf

    if diff != 0:  # have to work hard to round to decimal
        HALF_CENT = 0.005  # e.g. BUY  stop: round   up to decimal

        if round_down:
            HALF_CENT *= -1  # e.g. SELL stop: round down to decimal
        price += HALF_CENT

        if price > 0:
            spstr = "%.2f" % price  # now round to 2-place decimal

    return spstr

class etreade():
    def __init__(self, account_n=0, accountId=None):
        self.base_url = cfg["etrade"]["PROD_BASE_URL"]
        self.accountId = accountId
        self.account_n = account_n
        self.consumer_key = cfg["etrade"]["CONSUMER_KEY"]
        self.consumer_secret = cfg["etrade"]["CONSUMER_SECRET"]
        
    def get_session(self):
        """Allows user authorization for the sample application with OAuth 1"""
        oauth = pyetrade.ETradeOAuth(self.consumer_key, self.consumer_secret)
        print(oauth.get_request_token())  # Use the printed URL

        if cfg['etrade'].getboolean('WITH_BROWSER'):
            webbrowser.open(oauth.get_request_token())
        else:
            print("Please open the following URL in your browser:")
            print(oauth.get_request_token())
        verifier_code = input("Please accept agreement and enter verification code from browser: ")

        self.tokens = oauth.get_access_token(verifier_code)
        
        # get sessions
        kwargs = {'client_key': self.consumer_key,
                  'client_secret': self.consumer_secret,
                  'resource_owner_key': self.tokens['oauth_token'],
                  'resource_owner_secret': self.tokens['oauth_token_secret'],
                  'dev': False}
        
        self.account_session = pyetrade.ETradeAccounts(**kwargs)
        self.market_session = pyetrade.ETradeMarket(**kwargs)     
        self.order_session = pyetrade.ETradeOrder(**kwargs)
        self._get_account()
        return True

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
                        pos = {
                            "longQuantity" : position['quantity'] if position['positionType'] == 'LONG' else 0,
                            "symbol": position['Product']["symbol"],
                            "assetType": 'stock' if position['Product']["securityType"] == 'EQ' else 'option',
                            "averagePrice": position['costPerShare'],
                            "currentDayProfitLoss": position['totalGainPct'],
                        }
                        acc_inf['securitiesAccount']['positions'].append(pos)
        else:
            print("No portfolio")

        return acc_inf

    def get_positions_orders(self):
        acc_inf = self.get_account_info()

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
        """From ticker_monthdayyearstrike[callput] to ticker:year:month:day:optionType:strikePrice"""

        exp = r"(\w+)_(\d{2})(\d{2})(\d{2})([CP])([\d.]+)"        
        match = re.search(exp, opt_ticker, re.IGNORECASE)
        if match:
            symbol, mnt, day, yer, type, strike = match.groups()
        converted_code = f"{symbol}:20{yer}:{mnt}:{day}:{type}:{strike}"
        return converted_code

    def get_quotes(self, symbol:list):
        """
        Calls quotes API to provide quote details for equities, options, and mutual funds
        """
        # reformat option tickers
        symbol = [self.format_option(i) if "_" in i else i for i in symbol ]
        
        resp = {}
        for ix in range(0,len(symbol),25):  # lim is 25, loop over 25 symbols at a time
            symbol_l = symbol[ix:25]
            data = self.market_session.get_quote(symbol_l,resp_format='json')

            if data is not None and "QuoteResponse" in data:
                if data["QuoteResponse"].get("Messages"):
                    for message in data["QuoteResponse"]["Messages"]['Message']:
                        ticker = message["description"].split(" ")[0]
                        resp[ticker] = {'description': 'Symbol not found'}
                if "QuoteData" in data["QuoteResponse"]:
                    for quote in data["QuoteResponse"]["QuoteData"]:
                        if quote is None:
                            resp[ticker] = {'description': 'Symbol not found'}
                            continue 
                        if  quote.get("Product").get('securityType') == "OPTN":
                            # to common format ticker_monthdayyearstrike[callput]
                            prod = quote['Product']
                            ticker = f"{prod['symbol']}_{prod['expiryMonth']:02d}{prod['expiryDay']:02d}{str(prod['expiryYear'])[2:]}{prod['callPut'][0]}{str(prod['strikePrice']).replace('.0','')}"
                        else:
                            ticker =  quote.get("Product").get('symbol')        
                        resp[ticker] = {
                            'description': quote.get("All").get("symbolDescription"),
                            'askPrice': quote.get("All").get("ask"),  
                            'bidPrice': quote.get("All").get("bid"),    
                            'quoteTimeInLong': quote.get("dateTimeUTC")*1000,
                            "status": quote['quoteStatus']
                            }
        return resp

    def get_order_info(self, order_id): 
        """ Get order info from order_id"""
        orders = self.order_session.list_orders(self.accountIdKey, resp_format='json')
        
        for order in orders['OrdersResponse']['Order']:
            if order['orderId'] == order_id:
                order_status = order['OrderDetail'][0]['status']
                order_info = {
                    'status': order_status,
                    'quantity': order['OrderDetail'][0]['Instrument'][0]['orderedQuantity'],
                    'filledQuantity': order['OrderDetail'][0]['Instrument'][0]['filledQuantity'],
                    'price':order['OrderDetail'][0]['Instrument'][0].get('averageExecutionPrice'),
                    'orderStrategyType': 'SINGLE',
                    "order_id" : order['orderId']
                }                
                return order_status, order_info
        return None, None

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
    
    def cancel_order(self, order_id:int):        
        return self.order_session.cancel_order(self.accountIdKey,order_id, resp_format='xml')
        
    
    
    # def make_BTO_lim_order(self, Symbol:str, uQty:int, price:float, strike=None, **kwarg):
    #     new_order=Order()
    #     new_order.order_strategy_type("TRIGGER")
    #     new_order.order_type("LIMIT")
    #     new_order.order_session('NORMAL')
    #     new_order.order_duration('GOOD_TILL_CANCEL')
    #     new_order.order_price(float(price))

    #     order_leg = OrderLeg()

    #     if strike is not None:
    #         order_leg.order_leg_instruction(instruction="BUY_TO_OPEN")
    #         order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    #     else:
    #         order_leg.order_leg_instruction(instruction="BUY")
    #         order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)

    #     order_leg.order_leg_quantity(quantity=int(uQty))
    #     new_order.add_order_leg(order_leg=order_leg)
    #     return new_order



    # def make_Lim_SL_order(self, Symbol:str, uQty:int,  PT:float, SL:float, SL_stop:float=None, new_order=None, strike=None, **kwarg):
    #     if new_order is None:
    #         new_order = Order()
    #     new_order.order_strategy_type("OCO")

    #     child_order1 = new_order.create_child_order_strategy()
    #     child_order1.order_strategy_type("SINGLE")
    #     child_order1.order_type("LIMIT")
    #     child_order1.order_session('NORMAL')
    #     child_order1.order_duration('GOOD_TILL_CANCEL')
    #     child_order1.order_price(float(PT))

    #     child_order_leg = OrderLeg()

    #     child_order_leg.order_leg_quantity(quantity=uQty)
    #     if strike is not None:
    #         child_order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
    #         child_order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    #     else:
    #         child_order_leg.order_leg_instruction(instruction="SELL")
    #         child_order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)

    #     child_order1.add_order_leg(order_leg=child_order_leg)
    #     new_order.add_child_order_strategy(child_order_strategy=child_order1)

    #     child_order2 = new_order.create_child_order_strategy()
    #     child_order2.order_strategy_type("SINGLE")
    #     child_order2.order_session('NORMAL')
    #     child_order2.order_duration('GOOD_TILL_CANCEL')

    #     if SL_stop is not None:
    #         child_order2.order_type("STOP_LIMIT")
    #         child_order2.order_price(float(SL))
    #         child_order2.stop_price(float(SL_stop))
    #     else:
    #         child_order2.order_type("STOP")
    #         child_order2.stop_price(float(SL))

    #     child_order2.add_order_leg(order_leg=child_order_leg)
    #     new_order.add_child_order_strategy(child_order_strategy=child_order2)
    #     return new_order


    # def make_STC_lim(self, Symbol:str, uQty:int, price:float, strike=None, **kwarg):
    #     new_order=Order()
    #     new_order.order_strategy_type("SINGLE")
    #     new_order.order_type("LIMIT")
    #     new_order.order_duration('GOOD_TILL_CANCEL')
    #     new_order.order_price(float(price))

    #     order_leg = OrderLeg()
    #     order_leg.order_leg_quantity(quantity=int(uQty))

    #     if strike is not None:
    #         new_order.order_session('NORMAL')
    #         order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
    #         order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    #     else:
    #         new_order.order_session('SEAMLESS')
    #         order_leg.order_leg_instruction(instruction="SELL")
    #         order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
    #     new_order.add_order_leg(order_leg=order_leg)
    #     return new_order

    # def make_STC_SL(self, Symbol:str, uQty:int, SL:float, strike=None,
    #                 SL_stop:float=None, new_order=Order(), **kwarg):
    #     new_order=Order()
    #     new_order.order_strategy_type("SINGLE")

    #     if SL_stop is not None:
    #         new_order.order_type("STOP_LIMIT")
    #         new_order.stop_price(float(SL_stop))
    #         new_order.order_price(float(SL))
    #     else:
    #         new_order.order_type("STOP")
    #         new_order.stop_price(float(SL))

    #     new_order.order_session('NORMAL')
    #     new_order.order_duration('GOOD_TILL_CANCEL')

    #     order_leg = OrderLeg()
    #     order_leg.order_leg_quantity(quantity=int(uQty))
    #     if strike is not None:
    #         order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
    #         order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
    #     else:
    #         order_leg.order_leg_instruction(instruction="SELL")
    #         order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
    #     new_order.add_order_leg(order_leg=order_leg)
    #     return new_order

    def make_STC_SL_trailstop(self, Symbol:str, uQty:int,  trail_stop_percent:float, **kwarg):
        kwargs = {}
        kwargs['symbol'] = Symbol
        if len(Symbol.split("_"))>1:
            Symbol = self.format_option(Symbol)            
            symbol, year, month, day, optype, strike = Symbol.split(":")
            kwargs['symbol'] = symbol
            kwargs['expiryDate'] = f"{year}-{month}-{day}"
            kwargs['strikePrice'] = float(strike)
            kwargs['callPut'] = optype
            kwargs["securityType"] = "OPTN"

        kwargs['orderAction'] = "SELL"
        kwargs['clientOrderId'] = str(random.randint(1000000000, 9999999999))
        kwargs['priceType'] = 'TRAILING_STOP_PRCT'
        # kwargs['trailPrice'] = trail_stop_percent
        kwargs['stopPrice'] = trail_stop_percent
        # kwargs['offsetType'] = 'TRAILING_STOP_PRCT'
        kwargs['allOrNone'] = False
        kwargs['quantity'] = uQty       
        kwargs['orderTerm'] = "GOOD_UNTIL_CANCEL"
        kwargs['marketSession'] = 'REGULAR'
        return kwargs





rt = etreade()
rt.get_session()
rt.get_account_info()
rt.get_quotes(["AAPL", 'NIO:2023:08:18:P:4'])
# rt.order_session.list_orders(rt.accountIdKey, resp_format='json')

order = rt.make_STC_SL_trailstop('VERB', 1, 40)

order_response, order_id = rt.send_order(order)

res = rt.cancel_order(order_id)