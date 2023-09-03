import re
import time
from ib_insync import IB, Stock, MarketOrder, util, Option
from datetime import datetime
from DiscordAlertsTrader.configurator import cfg
import ib_insync

class Ibkr:
    def __init__(self, paper_trading: bool = False) -> None:
        self._ibkr = IB()
        self._loggedin = False
        self.name = 'ibkr'
        self.option_ids = {}

    def connect(self, port: int = 7496) -> bool:
        try:
            self._ibkr.connect('127.0.0.1', port, clientId=random.randint(1, 50))
            self.success = True
            self._port = port
        except:
            self.success = False
            self._port = None
         
    def get_session(self) -> bool:
        # todo : can use singleton pattern
        self.success = self.connect(port=7496)
        if not self.success:
            self.session = None
        else:
            self.session = self._ibkr

        if self.success: 
            print(f"Logging into IBKR: Success!")
        else:
            print(f"Logging into IBKR: Failed!")
        return self.success

    def get_account_info(self,account:str =""):
        """
        Call portfolio API to retrieve a list of positions held in the specified account
        """
        account_summary = self.session.accountSummary(account=account)
        res = None
        for summary in account_summary:
            if summary.tag == ftag:
                res = float(summary.value)
                break
        
        # get account metadata information
        netLiquidation = [v for v in self.session.accountValues() if 
                          v.tag == 'NetLiquidationByCurrency' and v.currency == 'BASE'] # ib example        
        cashBalance = self.session.accountValues()['TotalCashValue'] # ib example
        availableFunds = self.session.accountValues()['SettledCash'] # ib example
        acc_inf ={
            'securitiesAccount':{   
                'positions':[],
                'accountId' : str(data['secAccountId']),
                'currentBalances':{
                    'liquidationValue': netLiquidation, # ib example    
                    'cashBalance': cashBalance, # ib example   
                    'availableFunds': availableFunds, # ib example   
                    },
        }}

        # get positions of the account
        positions = self.session.positions() # ib example
        
        for position in positions:
            pos = {
                "longQuantity" : eval(position['position']), # ib example        
                "symbol": position["symbol"],  # ib example        
                "marketValue": eval(position['position']),
                "assetType": position['tradingClass'], # ib example    
                "averagePrice": eval(position['avgCost']), # ib example    
                "currentDayProfitLoss": eval(position['unrealizedProfitLoss']),
                "currentDayProfitLossPercentage": float(eval(position['unrealizedProfitLoss']))/100,
                'instrument': {'symbol': position["symbol"], # ib example    
                                'assetType': position['tradingClass'], # ib example    
                                }
            }
            acc_inf['securitiesAccount']['positions'].append(pos)

        # checks if account has no open pos   
        if not len(positions):
            acc_inf['securitiesAccount']['positions'] = []
            print("No portfolio")

        # get orders and add them to acc_inf
        orders = self.session.openOrders() # ib example
        orders_inf =[]  
       
        for order in orders:
            order_status = order['status'].upper()
            if order_status in ['CANCELLED', 'FAILED']:
                continue
            orders_inf.append(self.format_order(order))
        acc_inf['securitiesAccount']['orderStrategies'] = orders_inf
        return acc_inf

    def get_order_info(self, order_id): 
        """ Get order info from order_id"""
        orders = self.session.get_history_orders()      
        for order in orders:
            if order['orders'][0]['orderId'] == order_id:
                order_status = order['status'].upper()
                order_info = self.format_order(order)         
                return order_status, order_info
        return None, None

    def format_order(self, order:dict):
        """ output format for order_response. Order, mimicks the order_info from TDA API"""
        stopPrice= order['orders'][0].get('stpPrice')
        
        price = order['orders'][0].get('avgFilledPrice')
        if price is None:
            price = order['orders'][0].get('lmtPrice')
            
        timestamp = int(order['orders'][0]['createTime0'])/1000
        enteredTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S+00")
        timestamp = int(order['orders'][0]['updateTime0'])/1000
        closeTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S+00")
        asset = order['orders'][0]['tickerType'].lower()
        if asset == 'option':            
            yer, mnt, day = order['orders'][0]['optionExpireDate'].split("-")
            otype = "C" if order['orders'][0]['optionType'][0].upper() =="CALL" else "P"
            symbol = f"{order['orders'][0]['symbol']}_{mnt}{day}{yer[2:]}{otype}{order['orders'][0]['optionExercisePrice']}".replace(".00","")
            symbol = self.fix_symbol(symbol, "out")
            orderStrategyType = order['optionStrategy'].upper()
        else:
            symbol = order['orders'][0]['symbol']
            orderStrategyType= 'SINGLE'
        status = order['status'].upper()
        order_info = {
            'status': status,
            'quantity': int(order['orders'][0]['totalQuantity']),
            'filledQuantity': int(order['orders'][0]['filledQuantity']),
            'price': float(price) if price else float(order['auxPrice']),
            'orderStrategyType': orderStrategyType,
            "order_id" : order['orders'][0]['orderId'],
            "orderId": order['orders'][0]['orderId'],
            "stopPrice": stopPrice if stopPrice else None,
            'orderType':  order['orders'][0]['orderType'],
            'enteredTime': enteredTime,
            "closeTime": closeTime,
            'orderLegCollection':[{
                'instrument':{'symbol': symbol},
                'instruction': order['orders'][0]['action'],
                'quantity': int(order['filledQuantity']),
            }]             
        }    
        return order_info

    def format_option(self, opt_ticker:str)->dict:
        """From ticker_monthdayyear[callput]strike to dict {ticker, year-month-day,optionType,strikePrice"""
        exp = r"(\w+)_(\d{2})(\d{2})(\d{2})([CP])([\d.]+)"        
        match = re.search(exp, opt_ticker, re.IGNORECASE)
        if match:
            symbol, mnt, day, yer, type, strike = match.groups()
            type = 'call' if type.lower() == 'c' else 'put'
            opt_info = {
              'ticker': symbol,
              'date': f"20{yer}-{mnt}-{day}",
              'direction': type,
              'strike': strike
              }
            return opt_info
        else:
            print('No format_option match for', opt_ticker)

    def reformat_option(self, opt_info:dict)->str:
        "From dict to standard option format ticker_monthdayyear[callput]strike"      
        yer, mnt, day = opt_info['date'].split("-")
        otype = opt_info['direction'][0].upper()
        return f"{opt_info['ticker']}_{mnt}{day}{yer[2:]}{otype}{opt_info['strike']}"

    def get_option_id(self, symb:str):
        "Get option id from option symb with standard format"
        if self.option_ids.get(symb) is None:
            opt_info = self.format_option(symb)
            if opt_info:
                options_data = self.session.get_options(stock=opt_info['ticker'],
                                                        direction=opt_info['direction'], 
                                                        expireDate=opt_info['date'])
                filtered_options_data = [option for option in options_data if option['strikePrice'] == opt_info['strike'] and \
                    option[opt_info['direction']]['expireDate'] == opt_info['date']]
                option_id = filtered_options_data[0][opt_info['direction']]['tickerId']
                self.option_ids[symb] = str(option_id)
                return option_id
            else:
                return None
        else:
            return self.option_ids[symb]

    def fix_symbol(self, symbol:str, direction:str):
        "Fix symbol for options, direction in or out of webull format"
        if direction == 'in':
            return symbol.replace("SPXW", "SPX")
        elif direction == 'out':
            return symbol.replace("SPX", "SPXW")

    def get_quotes(self, symbol:list) -> dict:  
        resp = {}
        for symb in symbol:        
            if "_" in symb:
                symb = self.fix_symbol(symb, "in")
                opt_info = self.format_option(symb)
                if opt_info:
                    try:
                        option_id = self.get_option_id(symb)
                        quote = self.session.get_option_quote(stock=opt_info['ticker'], optionId=option_id)
                        
                        ts = quote['data'][0]['tradeStamp']
                        ask = eval(quote['data'][0]['askList'][0]['price'])
                        bid = eval(quote['data'][0]['bidList'][0]['price'])
                        ticker = self.fix_symbol(self.reformat_option(opt_info), 'out')
                        
                        resp[ticker] = {
                                        'symbol' : ticker,
                                        'description': option_id,
                                        'askPrice': ask,  
                                        'bidPrice': bid,    
                                        'quoteTimeInLong': ts
                                        }
                    except Exception as e:
                        sym_out = self.fix_symbol(symb, "out")
                        print("Error getting quote for",  sym_out, e)
                        resp[sym_out] = {'symbol': sym_out,
                                        'description':'Symbol not found'
                                        }
            else:
                quote = self.session.get_quote(symb)
                if quote and quote['template']=='stock':                
                    resp[symb] = {
                                'symbol' : quote['symbol'],
                                'description': quote['disSymbol'],
                                'askPrice': eval(quote['askList'][0]['price']),
                                'bidPrice': eval(quote['bidList'][0]['price']),
                                'quoteTimeInLong': round(time.time()*1000),
                            }
                else:
                    print(symb, "not found", quote['template'])
                    resp[symb] = {'symbol' :symb,
                                    'description':'Symbol not found'
                                    }
        return resp

    def send_order(self, new_order:dict):
        if new_order['asset'] == 'option':
            final_order = {}
            for key, val in new_order.items():
                if key  in ['optionId', 'lmtPrice', 'stpPrice', 'action', 'orderType', 'enforce', 'quant']:
                    final_order[key] = val
            order_response = self.session.place_order_option(**final_order)     
        else:
            final_order = {}
            if new_order.get('lmtPrice'):
                new_order['price'] = new_order.pop('lmtPrice')
            for key, val in new_order.items():
                if key in ['stock', 'tId', 'price', 'action', 'orderType', 'enforce', 'quant', 
                           'outsideRegularTradingHour', 'stpPrice', 'trial_value', 'trial_type']:
                    final_order[key] = val
            order_response = self.session.place_order(**final_order)
        
        if order_response.get('success') is False:
            print("Order failed", order_response)
            return None, None
        # find order id by matching symbol and order type
        if order_response.get('data'):  #for stocks
            order_id = order_response['data']['orderId']
        else:
            order_id = order_response['orderId']
        time.sleep(3) # 3 secs to wait for order to show up in history
        _, ord_inf = self.get_order_info(order_id)
        
        order_response.update(ord_inf) 
        return order_response, order_id
    
    def cancel_order(self, order_id:int) -> bool:
        # todo: handle exception
        try:
            self.session.cancelOrder(ib_insync.Order(orderId=order_id))
            return True
        except:
            return False

    def get_orders(self, open_only=True):
        '''
        todo
        1. pass account id to get only that account open orders
        2. is it asking for all orders or just open orders?
        '''

        orders_all  = []
        if open_only is True:
            for order in self.session.openOrders():
                orders_all.append(self.format_order(order))
        else:
            for order in self.session.orders():
                orders_all.append(self.format_order(order))
                
        return orders_all

    def get_account_names(self) -> List[str]: 
        '''Return list of accounts eligible for trading'''
        res = self.session.managedAccounts()
        return ret

    def make_BTO_lim_order(self, Symbol:str, Qty:int, price:float, action="BTO", **kwarg):
        "Buy with a limit order"
        
        kwargs = {}
        if action == "BTO":
            kwargs['action'] = "BUY"
        elif action == "STO":
            print("STO not available for WeBull")
            return
        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'option'
            optionId = self.get_option_id(Symbol)
            if optionId is None:
                print("No optionId found for", Symbol)
                return None        
            kwargs['optionId'] = optionId
        else:
            kwargs['asset'] ='stock'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol
        
        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty  
        kwargs['orderType'] = 'LMT' 
        kwargs['lmtPrice'] = price
        return kwargs

    def make_Lim_SL_order(self, Symbol:str, Qty:int,  PT:float, SL:None, action="STC", **kwarg):
        """Sell with a limit order and a stop loss order"""        
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            print("BTC not available for WeBull")
            return
        
        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'option'
            optionId = self.get_option_id(Symbol)
            if optionId is None:
                print("No optionId found for", Symbol)
                return None        
            kwargs['optionId'] = optionId
        else:
            kwargs['asset'] ='stock'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol
        
        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty 
        if SL is not None:
            print("WARNING: webull api does not support OCO, setting a SL only, do not provide SL to send PT")
            kwargs['orderType'] = 'STP' 
            kwargs['lmtPrice'] = SL
        else:
            print("WARNING: webull api does not support OCO, sending PT without SL")
            kwargs['orderType'] = 'LMT' 
            kwargs['lmtPrice'] = PT
        return kwargs

    def make_STC_lim(self, Symbol:str, Qty:int, price:float, strike=None, action="STC", **kwarg):
        """Sell with a limit order and a stop loss order"""        
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            print("BTC not available for WeBull")
            return
        
        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'option'
            optionId = self.get_option_id(Symbol)
            if optionId is None:
                print("No optionId found for", Symbol)
                return None        
            kwargs['optionId'] = optionId
        else:
            kwargs['asset'] ='stock'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol
        
        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty  
        kwargs['orderType'] = 'LMT' 
        kwargs['lmtPrice'] = price
        return kwargs

    def make_STC_SL(self, Symbol:str, Qty:int, SL:float, action="STC", **kwarg):
        """Sell with a stop loss order"""
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            print("BTC not available for WeBull")
            return
        
        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'option'
            optionId = self.get_option_id(Symbol)
            if optionId is None:
                print("No optionId found for", Symbol)
                return None        
            kwargs['optionId'] = optionId
        else:
            kwargs['asset'] ='stock'
            kwargs['outsideRegularTradingHour'] = False
            kwargs['stock'] = Symbol

        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty 
        kwargs['orderType'] = 'STP' 
        kwargs['stpPrice'] = SL
        kwargs['lmtPrice'] = SL
        return kwargs

    def make_STC_SL_trailstop(self, Symbol:str, Qty:int,  trail_stop_const:float, action="STC", **kwarg):
        "trail_stop_const"
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            print("BTC not available for WeBull")
            return
        
        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            print("WARNING webull does not support trailing stop for options")
            return {}        

        kwargs['asset'] ='stock'
        kwargs['outsideRegularTradingHour'] = True
        kwargs['stock'] = Symbol
        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty 
        kwargs['orderType'] = 'STP TRAIL'
        kwargs['trial_value'] = trail_stop_const
        kwargs['trial_type'] = 'DOLLAR'
        kwargs['outsideRegularTradingHour'] = True
        return kwargs