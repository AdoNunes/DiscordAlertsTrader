import re
import time
from datetime import datetime
from webull import webull, paper_webull
from DiscordAlertsTrader.configurator import cfg


class weBull:
    def __init__(self, paper_trading: bool = False) -> None:
        self._webull = paper_webull() if (paper_trading) else webull()
        self._loggedin = False

    def get_session(self, use_workaround: bool = True) -> bool:
        wb = self._webull
        if (use_workaround):
            wb._set_did(cfg["webull"]['SECURITY_DID'])

        wb.login(username=cfg["webull"]['LOGIN_EMAIL'],
                password=cfg["webull"]['LOGIN_PWD'],
                device_name=cfg["webull"]['DEVICE_ID']
                )

        self.success = wb.get_trade_token(cfg["webull"]['TRADING_PIN'])
        self.session = wb
        if self.success: 
            print(f"Logging into webull: Success!")
        else:
            print(f"Logging into webull: Failed!")
        return self.success

    def get_account_info(self):
        """
        Call portfolio API to retrieve a list of positions held in the specified account
        """
        data = wbsession.session.get_account()       

        acc_inf ={
            'securitiesAccount':{   
                'positions':[],
                'accountId' : data['secAccountId'],
                'currentBalances':{
                    'liquidationValue': data.get('netLiquidation'),
                    'cashBalance': data['accountMembers'][1]['value'],
                    'availableFunds': data['accountMembers'][2]['value'],
                    },
        }}
        positions = data['positions']
        for position in positions["Position"]:
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
        orders = self.session.get_current_orders()
        orders_inf =[]        
        for order in orders:
            order_status = order['OrderDetail'][0]['status'].upper().replace('EXECUTED','FILLED').replace('OPEN','WORKING')
            if order_status in ['CANCELLED', 'REJECTED', 'EXPIRED']:
                continue
            orders_inf.append(self.format_order(order))
        acc_inf['securitiesAccount']['orderStrategies'] = orders_inf
        return acc_inf

    def get_order_info(self, order_id): 
        """ Get order info from order_id, mimicks the order_info from TDA API"""
        orders = self.session.get_current_orders()      
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
      yer, mnt, day = opt_info['date']
      otype = "C" if opt_info['direction'][0].upper() =="CALL" else "P"
      return f"{opt_info['ticker']}_{mnt}{day}{yer[2:]}{otype}{opt_info['strike']}"

    def get_quotes(self, symbol:list) -> dict:  
      resp = {}
      for symb in symbol:        
        if "_" in symb:
          opt_info = self.format_option(symb)
          if opt_info:
            options_data = self.session.get_options(stock=opt_info['ticker'],
                                                    direction=opt_info['direction'], 
                                                    expireDate=opt_info['date'])
            filtered_options_data = [option for option in options_data if option['strikePrice'] == opt_info['strike'] and \
                option[opt_info['direction']]['expireDate'] == opt_info['date']]

          ask = filtered_options_data[0][direction]['askList'][0]['price']
          bid = filtered_options_data[0][direction]['bidList'][0]['price']
          ticker = self.reformat_option(opt_info)
          option_id = filtered_options_data[0][direction]['tickerId']
          resp[ticker] = {
                          'symbol' : ticker,
                          'description': str(option_id),
                          'askPrice': ask,  
                          'bidPrice': bid,    
                          'quoteTimeInLong': round(time.time()*1000),
                          }
        else:
            quote = self.session.get_quote(symb)
            if quote:
               resp[symb] = {
                          'symbol' : quote['symbol'],
                          'description': quote['disSymbol'],
                          'askPrice': quote['askList'][0]['price'],
                          'bidPrice': quote['bidList'][0]['price'],
                          'quoteTimeInLong': round(time.time()*1000),
                        }
      return resp

    def send_order(self, new_order:dict):
      if new_order['asset'] == 'option': 
        order_response = self.session.place_order_option(**new_order)#optionId=str(option_id) , lmtPrice=3.01, action="BUY", orderType='LMT', enforce='GTC', quant=1)     
      else:
        order_response = self.session.place_order(**new_order) # stock=None, tId=None, price=0, action='BUY', orderType='LMT', enforce='GTC', quant=0, outsideRegularTradingHour=True, stpPrice=None, trial_value=0, trial_type='DOLLAR')
        
        # find order id by matching symbol and order type
        order_id = int(order_response['PlaceOrderResponse']['OrderIds']['orderId'])
        _, ord_inf = self.get_order_info(order_id)
        
        order_response['quantity'] =  int(order_response['PlaceOrderResponse']['Order']['Instrument']['quantity']),
        order_response.update(ord_inf) 
        return order_response, order_id
    
    def cancel_order(self, order_id:int):
        resp = self.session.cancel_order(order_id)
        return resp

    def get_orders(self):
        orders = self.session.get_current_orders()
        orders = orders['OrdersResponse']['Order']
        return orders

# def main():
wbsession = weBull(False)
wbsession.get_session(True)

# my_bot._webull.get_account_id()

orders = wbsession.session.get_current_orders()
for order in orders :
    print(order)


option_chain  = wbsession.session.get_options(stock='AAPL')

strike = 175
direction= 'call'
date = '2023-06-09'
ticker = 'AAPL'
# get a list of all available option contracts for AAPL
options_data = wbsession.session.get_options(stock=ticker,direction=direction, expireDate=date)
# filter the options data to find the option contract with a strike price of $175 and an expiration date of May 12, 2023
filtered_options_data = [option for option in options_data if option['strikePrice'] == str(strike) and option[direction]['expireDate'] == date]

# extract the option ID from the filtered options data
option_id = filtered_options_data[0][direction]['tickerId']


print(f"The option ID for AAPL $175 Call option expiring on 05/12/2023 is {option_id}")

option_quote = wbsession.session.get_option_quote(stock='AAPL', optionId=option_id)

wbsession.session.place_order_option(optionId=str(option_id) , lmtPrice=3.01, action="BUY", orderType='LMT', enforce='GTC', quant=1)
