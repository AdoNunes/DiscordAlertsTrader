from ib_insync import *
from DiscordAlertsTrader.brokerages import BaseBroker
from DiscordAlertsTrader.configurator import cfg
from datetime import datetime
import time

class IBKR(BaseBroker):
    def __init__(self,accountId=None):
        self.name = 'ibkr'
        self.accountId = accountId
        self.ib = IB()
    
    def get_session(self):
        if self.ib.isConnected():
            return True
        else:
            self.ib.connect(cfg['IBKR']['host'], cfg['IBKR']['port'], clientId=cfg['IBKR']['clientId'])
            self.ib.sleep(0.1)
            return self.ib.isConnected()
    
    def get_account_info(self):
        data = self.ib.accountValues()
        # print(data)
        for item in data:
            if item.tag == 'NetLiquidation':
                liquidationValue = item.value
            if item.tag == 'CashBalance':
                cashBalance = item.value
            if item.tag == 'AvailableFunds':
                availableFunds = item.value

        acc_inf ={
            'securitiesAccount':{   
                'positions':[],
                'accountId' : str(self.accountId),
                'currentBalances':{
                    'liquidationValue': liquidationValue,    
                    'cashBalance': cashBalance,
                    'availableFunds': availableFunds,  
                    },
        }}

        self.ib.sleep(0.1)
        positions = self.ib.portfolio()
        self.ib.sleep(0.1)

        for position in positions:
            
            # print(position)
            marketValue = position.marketValue
            unrealizedPnL = position.unrealizedPNL
            unrealizedPnLPercentage = unrealizedPnL / marketValue if marketValue != 0 else 0

            pos_d = {
                "longQuantity" : position.position,
                "symbol": position.contract.symbol,
                "marketValue": marketValue,
                "assetType": position.contract.secType,
                "averagePrice": position.averageCost,
                "currentDayProfitLoss": unrealizedPnL,
                "currentDayProfitLossPercentage": unrealizedPnLPercentage,
                'instrument': {'symbol': position.contract.symbol,
                                'assetType': position.contract.secType,
                                }
                }
            acc_inf['securitiesAccount']['positions'].append(pos_d)
        
        if not len(positions):
            acc_inf['securitiesAccount']['positions'] = []
            print("No portfolio")
        
        self.ib.sleep(0.1)
        trades = self.ib.trades()
        orders_inf =[]

        for trade in trades:

            order = trade.order
            status = trade.orderStatus.status
            order_info = {
                'status': status,
                'quantity': order.totalQuantity,
                'filledQuantity': order.filledQuantity,
                'price':trade.orderStatus.avgFillPrice,
                'orderStrategyType': 'SINGLE',
                "order_id" : order.orderId,
                "orderId": order.orderId,
                "stopPrice": order.auxPrice if order.orderType == 'STP' else None,
                'orderType':  order.orderType,
                'placedTime': trade.log[0].time.timestamp() if trade.log else None,
                'enteredTime': trade.fills[0].time if trade.fills else None,
                "closeTime": trade.fills[-1].time if trade.fills else None,
                'orderLegCollection':[{
                    'instrument':{'symbol':trade.contract.symbol},
                    'instruction': order.action,
                    'quantity': order.filledQuantity,
                }]             

            }
            formatted_order = self.format_order(order_info)
            orders_inf.append(formatted_order)

        acc_inf['securitiesAccount']['orderStrategies'] = orders_inf
        # print(acc_inf)
        return acc_inf

    def format_order(self, order:dict):
        """ output format for order_response.Order, mimicks the order_info from TDA API"""
        stopPrice= order['stopPrice']
        timestamp = order['placedTime']/1000 if order['placedTime'] else None
        enteredTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S+00") if timestamp else None
        if 'closeTime' in order:
            timestamp = order['closeTime']/1000 if order['closeTime'] else None
            closeTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%dT%H:%M:%S+00") if timestamp else None
        else:
            closeTime = enteredTime
        status = order['status'].upper().replace('FILLED','FILLED').replace('SUBMITTED','WORKING').replace('CANCELLED','CANCELED')
        order_info = {
            'status': status,
            'quantity': order['quantity'],
            'filledQuantity': order['filledQuantity'],
            'price':order['price'],
            'orderStrategyType': 'SINGLE',
            "order_id" : order['orderId'],
            "orderId": order['orderId'],
            "stopPrice": stopPrice if stopPrice else None,
            'orderType':  order['orderType'],
            'enteredTime': enteredTime,
            "closeTime": closeTime,
            'orderLegCollection':[{
                'instrument':{'symbol':order['orderLegCollection'][0]['instrument']['symbol']},
                'instruction': order['orderLegCollection'][0]['instruction'],
                'quantity': order['orderLegCollection'][0]['quantity'],
            }]             
        }
        return order_info

    def cancel_order(self, order_id):
        
        open_orders = self.ib.openOrders()
        for order in open_orders:
            if order.orderId == order_id:
                self.ib.cancelOrder(order)
                self.ib.sleep(0.1)
                return True
        return False
    def get_orders(self):
        
        trades = self.ib.trades()
        orders_inf =[]
        for trade in trades:
            order = trade.order
            status = trade.orderStatus.status
            order_info = {
                'status': status,
                'quantity': order.totalQuantity,
                'filledQuantity': order.filledQuantity,
                'price':trade.orderStatus.avgFillPrice,
                'orderStrategyType': 'SINGLE',
                "order_id" : order.orderId,
                "orderId": order.orderId,
                "stopPrice": order.auxPrice if order.orderType == 'STP' else None,
                'orderType':  order.orderType,
                'placedTime': trade.log[0].time if trade.log else int(time.time()*1000),
                'enteredTime': trade.fills[0].time if trade.fills else int(time.time()*1000),
                "closeTime": trade.fills[-1].time if trade.fills else int(time.time()*1000),
                'orderLegCollection':[{
                    'instrument':{'symbol':trade.contract.symbol},
                    'instruction': order.action,
                    'quantity': order.filledQuantity,
                }]             

            }
            formatted_order = self.format_order(order_info)
            orders_inf.append(formatted_order)
        return orders_inf
    def get_order_info(self, order_id):
        
        self.ib.sleep(0.1)
        trades = self.ib.trades()

        for trade in trades:
            order = trade.order
            if order.orderId == order_id:
                status = trade.orderStatus.status
                order_info = {
                    'status': status,
                    'quantity': order.totalQuantity,
                    'filledQuantity': order.filledQuantity,
                    'price':trade.orderStatus.avgFillPrice,
                    'orderStrategyType': 'SINGLE',
                    "order_id" : order.orderId,
                    "orderId": order.orderId,
                    "stopPrice": order.auxPrice if order.orderType == 'STP' else None,
                    'orderType':  order.orderType,
                    'placedTime': trade.log[0].time if trade.log else int(time.time()*1000),
                    'enteredTime': trade.fills[0].time if trade.fills else int(time.time()*1000),
                    "closeTime": trade.fills[-1].time if trade.fills else int(time.time()*1000),
                    'orderLegCollection':[{
                        'instrument':{'symbol':trade.contract.symbol},
                        'instruction': order.action,
                        'quantity': order.filledQuantity,
                    }]             

                }
                formatted_order = self.format_order(order_info)
                return formatted_order
    
    def fix_symbol(self, symbol:str, direction:str):
        "Fix symbol for options, direction in or out of webull format"
        if direction == 'in':
            return symbol.replace("SPXW", "SPX").replace("NDXP", "NDX")
        elif direction == 'out':
            return symbol.replace("SPX", "SPXW").replace("NDX", "NDXP")
    
    def send_order(self, order_dict:dict):
        
        order = Order()
        order.action = order_dict['action']
        order.totalQuantity = order_dict['quant']
        order.orderType = order_dict['orderType']
        order.tif = order_dict['enforce']
        order.transmit = True
        order.outsideRth = order_dict['outsideRegularTradingHour'] if 'outsideRegularTradingHour' in order_dict else False

        if(order.orderType == 'LMT'):
            order.lmtPrice = order_dict['lmtPrice']
        
        if(order.orderType == 'STP'):
            order.auxPrice = order_dict['lmtPrice']
        
        if(order.orderType == 'TRAIL'):
            if(order_dict['trial_type'] == 'DOLLAR'):
                order.trailStopPrice = order_dict['trial_value']
            elif(order_dict['trial_type'] == 'PERCENT'):
                order.trailStopPrice = order_dict['trial_value']
        
        if(order.orderType == 'STP LMT'):
            order.lmtPrice = order_dict['lmtPrice']
            order.auxPrice = order_dict['stpPrice']
        #refer to https://ib-insync.readthedocs.io/api.html#module-ib_insync.contract

        contract = Contract(conId=order_dict['conId'])
        contract = self.ib.qualifyContracts(contract)[0] 
        self.ib.sleep(0.1)
        
        trade = self.ib.placeOrder(contract, order)
        print(contract)
        print(order)
        print(trade)
        self.ib.sleep(0.1)

        return trade.order.orderId
    
    def get_con_id(self, symbol:str):
        "Get contract id for a given symbol"
        if "_" in symbol:
            symbol_kwargs = self._convert_option_tots(symbol)
            contract = Option(symbol=symbol_kwargs['symbol'], lastTradeDateOrContractMonth=symbol_kwargs['lastTradeDateOrContractMonth'], \
                              strike=symbol_kwargs['strike'], right=symbol_kwargs['right'], \
                                exchange='SMART', currency='USD')
            contracts = self.ib.qualifyContracts(contract)
            contract = contracts[0] if contracts else None
            conId = contract.conId if contract else None
            return conId
        elif " " in symbol:
            symbol_kwargs = self._convert_option_fromts(symbol)
            contract = Option(symbol=symbol_kwargs['symbol'], lastTradeDateOrContractMonth=symbol_kwargs['lastTradeDateOrContractMonth'], \
                              strike=symbol_kwargs['strike'], right=symbol_kwargs['right'], \
                                exchange='SMART', currency='USD')
            contracts = self.ib.qualifyContracts(contract)
            contract = contracts[0] if contracts else None
            conId = contract.conId if contract else None
            return conId
        else:
            contracts = self.ib.qualifyContracts(Stock(symbol, 'SMART', 'USD'))
            contract = contracts[0] if contracts else None
            conId = contract.conId if contract else None
            return conId
    
    def make_BTO_lim_order(self, Symbol:str, Qty:int, price:float, action="BTO", **kwarg):
        "Buy with a limit order"

        kwargs = {}
        if action == "BTO":
            kwargs['action'] = "BUY"
        elif action == "STO":
            kwargs['action'] = "SELL"
        Symbol = self.fix_symbol(Symbol, "in")

        if (("_" in Symbol) or (" " in Symbol)):
            kwargs['asset'] = 'OPT'

        else:
            kwargs['asset'] ='STK'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol
            
        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty  
        kwargs['orderType'] = 'LMT' 
        kwargs['lmtPrice'] = price
        kwargs['conId'] = self.get_con_id(Symbol)

        return kwargs if kwargs['conId'] is not None else None

    def make_Lim_SL_order(self, Symbol:str, Qty:int,  PT:float, SL:None, action="STC", **kwarg):
        """Sell with a limit order and a stop loss order"""        
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            kwargs['action'] = "BUY"

        Symbol = self.fix_symbol(Symbol, "in")
        if (("_" in Symbol) or (" " in Symbol)):
            kwargs['asset'] = 'OPT'

        else:
            kwargs['asset'] ='STK'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol

        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty 
        kwargs['conId'] = self.get_con_id(Symbol)
        if SL is not None:
            print("WARNING: webull api does not support OCO, setting a SL only, do not provide SL to send PT")
            kwargs['orderType'] = 'STP' 
            kwargs['lmtPrice'] = SL
        else:
            print("WARNING: webull api does not support OCO, sending PT without SL")
            kwargs['orderType'] = 'LMT' 
            kwargs['lmtPrice'] = PT
        return kwargs if kwargs['conId'] is not None else None

    def make_STC_lim(self, Symbol:str, Qty:int, price:float, strike=None, action="STC", **kwarg):
        """Sell with a limit order and a stop loss order"""        
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            kwargs['action'] = "BUY"

        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'OPT'
            
        else:
            kwargs['asset'] ='STK'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol

        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty  
        kwargs['orderType'] = 'LMT' 
        kwargs['lmtPrice'] = price
        kwargs['conId'] = self.get_con_id(Symbol)

        return kwargs if kwargs['conId'] is not None else None

    def make_STC_SL(self, Symbol:str, Qty:int, SL:float, action="STC", **kwarg):
        """Sell with a stop loss order"""
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            kwargs['action'] = "BUY"

        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'OPT'
        else:
            kwargs['asset'] ='STK'
            kwargs['outsideRegularTradingHour'] = False
            kwargs['stock'] = Symbol

        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty 
        kwargs['orderType'] = 'STP LMT' 
        kwargs['stpPrice'] = SL
        kwargs['lmtPrice'] = SL
        kwargs['conId'] = self.get_con_id(Symbol)

        return kwargs if kwargs['conId'] is not None else None

    def make_STC_SL_trailstop(self, Symbol:str, Qty:int,  trail_stop_const:float, action="STC", **kwarg):
        "trail_stop_const"
        kwargs = {}
        if action == "STC":
            kwargs['action'] = "SELL"
        elif action == "BTC":
            kwargs['action'] = "BUY"

        Symbol = self.fix_symbol(Symbol, "in")
        if "_" in Symbol:
            kwargs['asset'] = 'OPT'
        else:
            kwargs['asset'] ='STK'
            kwargs['outsideRegularTradingHour'] = True
            kwargs['stock'] = Symbol    

        kwargs['enforce'] ='GTC'
        kwargs['quant'] = Qty 
        kwargs['orderType'] = 'TRAIL'
        kwargs['trial_value'] = trail_stop_const
        kwargs['trial_type'] = 'DOLLAR'
        kwargs['outsideRegularTradingHour'] = True
        kwargs['conId'] = self.get_con_id(Symbol)

        return kwargs if kwargs['conId'] is not None else None
    
    def get_quotes(self, symbol:list):
        
        quotes = {}
        for symbol in symbols:
            con_id = self.get_con_id(symbol)
            print(con_id)
            contract = Contract(conId=con_id)
            contract = self.ib.qualifyContracts(contract)[0]
            self.ib.sleep(0.1)
            quote = self.ib.reqTickers(contract)
            self.ib.sleep(0.1)
            quotes[symbol] = {
                'symbol': symbol,
                'mid': ((quote[-1].ask + quote[-1].bid) / 2) if quote[-1].ask and quote[-1].bid else float('nan'),
                'bid': quote[-1].bid,
                'ask': quote[-1].ask,
                'quoteTimeInLong': int(round(quote[-1].time.timestamp())) if quote[-1].time else None,
            }
        
        return quotes
    
    def _convert_option_fromts(self, ticker):
        """
        Convert ticker from 'NFLX 051724C450' to 

        {
            'symbol':'NFLX',
            'lastTradeDateOrContractMonth':'20240517',
            'strike': 450,
            'right':'C',
        }
        
        Parameters:
        ticker (str): Ticker in the original format.
        
        Returns:
        dict: kwargs in desired format.
        """
        if "_" not in ticker:
            return ticker
        symb, option_part = ticker.split(" ")  # Split the ticker by spaces
        date = option_part[2:4]
        month = option_part[:2]
        year = '20' + option_part[4:6]

        date = year + month + date
        right = (option_part[6])
        strike = int(option_part[7:])

        return {
            'symbol': symb,
            'lastTradeDateOrContractMonth': date,
            'strike': strike,
            'right': right
        }

    def _convert_option_tots(self, ticker):
        """
        Convert ticker from 'NFLX_051724C450' to 

        {
            'symbol':'NFLX',
            'lastTradeDateOrContractMonth':'20240517',
            'strike': 450,
            'right':'C',
        }
        
        Parameters:
        ticker (str): Ticker in the original format.
        
        Returns:
        dict: kwargs in desired format.
        """
        if "_" not in ticker:
            return ticker
        symb, option_part = ticker.split("_")  # Split the ticker by spaces
        date = option_part[2:4]
        month = option_part[:2]
        year = '20' + option_part[4:6]

        date = year + month + date
        right = (option_part[6])
        strike = int(option_part[7:])

        return {
            'symbol': symb,
            'lastTradeDateOrContractMonth': date,
            'strike': strike,
            'right': right
        }
            

##### Uncomment for testing

# if __name__ == '__main__':

#     ibkr = IBKR()
#     ibkr.get_session()
#     print(ibkr.get_account_info())

#     symbols = ["NFLX_051724C450", "AMD_051724C100"]

#     quotes = ibkr.get_quotes(symbols)

#     print(quotes)
    # order = ibkr.make_BTO_lim_order("NFLX_051724C450", 1, 605)
    # print(order)

    # order_id = ibkr.send_order(order)
    # print(order_id)

    # order = ibkr.cancel_order(order_id)
    # print(order)
