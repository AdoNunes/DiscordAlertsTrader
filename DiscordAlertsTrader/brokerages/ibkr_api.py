from ib_insync import *
from . import BaseBroker
from ..configurator import cfg
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
            self.ib.connect(cfg['IBKR']['host'], cfg['IBKR']['port'], clientId=cfg['IBKR']['clientId'], account=cfg['IBKR']['accountId'])
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
    
    def get_quotes(self, symbol:list):
        pass
    def send_order(self, side:str, order_type:str, quantity:int, contract: dict, price=None, stop_price=None):
        
        order = Order()
        order.action = side
        order.totalQuantity = quantity
        order.orderType = order_type
        order.tif = 'GTC'
        order.transmit = True

        if(order_type == 'LMT'):
            order.lmtPrice = price
        
        if(order_type == 'STP'):
            order.auxPrice = stop_price
        
        #refer to https://ib-insync.readthedocs.io/api.html#module-ib_insync.contract

        contract = Contract()
        contract.symbol = contract['symbol']
        contract.secType = contract['secType'] # refer to https://ib-insync.readthedocs.io/api.html#module-ib_insync.contract
        contract.exchange = contract['exchange']
        contract.currency = contract['currency']
        contract.primaryExchange = contract['primaryExchange']

        if(contract['secType'] == 'OPT'):
            contract.lastTradeDateOrContractMonth = contract['lastTradeDateOrContractMonth'] # should be in format 'YYYYMMDD'
            contract.strike = contract['strike']
            contract.right = contract['right']
            contract.multiplier = contract['multiplier']
            contract.localSymbol = contract['localSymbol']
        
        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0.1)

        return trade.order.orderId
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
