import pandas as pd

from ..configurator import cfg
from . import BaseBroker

from td.orders import Order, OrderLeg
from td.client import TDClient

class TDA(BaseBroker):
    def __init__(self,account_n=0, accountId=None):
        self.name = 'tda'
        self.account_n = account_n
        self.accountId = accountId

    def get_session(self, ):
        """Provide either:
            - account_n: indicating the orinal position from the accounts list
            (if only one account, it will be 0)
            - accountId: Number of the account

        auth is a dict with login info created with setup.py
        """
        if len(cfg['TDA']['client_id']) < 10:
            raise ValueError( "No TDA authentication file found, get credentials (in setup.py) to continue")
        # Create a new session, credentials path is required.
        self.session = TDClient(
            client_id=cfg['TDA']['client_id'],
            redirect_uri=cfg['TDA']['redirect_url'],
            credentials_path=cfg['TDA']['credentials_path']
        )

        # Login to the session
        success = self.session.login()

        if self.accountId is not None:
            self.session.accountId = self.accountId
        else:
            self.account_n = 0
            accounts_info = self.session.get_accounts(account="all")[self.account_n]
            self.accountId = accounts_info['securitiesAccount']['accountId']
        return success

    def send_order(self, new_order):
        order_response = self.session.place_order(account=self.accountId,
                                        order=new_order)
        order_id = order_response["order_id"]
        return order_response, order_id
    
    def cancel_order(self, order_id):
        return self.session.cancel_order(self.accountId, order_id)

    def get_order_info(self, order_id):  
        """
        order_status = 'REJECTED' | "FILLED" | "WORKING"
        """      
        order_info = self.session.get_orders(account=self.accountId, order_id=int(order_id))
        if order_info['orderStrategyType'] == "OCO":
            order_status = [
                order_info['childOrderStrategies'][0]['status'],
                order_info['childOrderStrategies'][1]['status']]
            if not order_status[0]==order_status[1]:
                print(f"OCO order status are different in ordID {order_id}: ",
                      f"{order_status[0]} vs {order_status[1]}, will try to get the filled")
            # take the first one, if cancelled it will look for the filled later
            order_status = order_status[0] 
        elif order_info['orderStrategyType'] in ['SINGLE', 'TRIGGER']:
            order_status = order_info['status']
        else:
            raise TypeError("Not sure type order. Check")
        return order_status, order_info

    def get_quotes(self, symbol:list):
        return self.session.get_quotes(instruments=symbol)

    def get_orders(self):
        pass

    def get_order_status(self, order_id):
        pass
    
    def get_account_info(self):
        acc_inf = self.session.get_accounts(self.accountId, ['orders','positions'])
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

    def make_BTO_lim_order(self, Symbol:str, uQty:int, price:float, strike=None, action="BTO", **kwarg):
        # iftrailing stop in STO, do a STO with trailstop
        if action == 'STO' and "trail_stop_const" in kwarg:
            print("STO with trail_stop_const")
            return self.make_STC_SL_trailstop(Symbol, uQty, action=action, **kwarg)

        new_order=Order()
        new_order.order_strategy_type("TRIGGER")
        new_order.order_type("LIMIT")
        new_order.order_session('NORMAL')
        new_order.order_duration('GOOD_TILL_CANCEL')
        new_order.order_price(float(price))

        order_leg = OrderLeg()

        if strike is not None:
            if action == "BTO":
                order_leg.order_leg_instruction(instruction="BUY_TO_OPEN")
            elif action == "STO":
                order_leg.order_leg_instruction(instruction="SELL_TO_OPEN")
            order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
        else:
            if action == "BTO":
                order_leg.order_leg_instruction(instruction="BUY")
            elif action == "STO":
                order_leg.order_leg_instruction(instruction="SELL_SHORT")
            order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)

        order_leg.order_leg_quantity(quantity=int(uQty))
        new_order.add_order_leg(order_leg=order_leg)
        return new_order

    def make_Lim_SL_order(self, Symbol:str, uQty:int,  PT:float, SL:float, SL_stop:float=None,
                          new_order=None, strike=None, action="STC",**kwarg):
        if new_order is None:
            new_order = Order()
        new_order.order_strategy_type("OCO")

        child_order1 = new_order.create_child_order_strategy()
        child_order1.order_strategy_type("SINGLE")
        child_order1.order_type("LIMIT")
        child_order1.order_session('NORMAL')
        child_order1.order_duration('GOOD_TILL_CANCEL')
        child_order1.order_price(float(PT))

        child_order_leg = OrderLeg()

        child_order_leg.order_leg_quantity(quantity=uQty)
        if strike is not None:
            if action == "STC":
                child_order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
            elif action == "BTC":
                child_order_leg.order_leg_instruction(instruction="BUY_TO_CLOSE")
            child_order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
        else:
            if action == "STC":
                child_order_leg.order_leg_instruction(instruction="SELL")
            elif action == "BTC":
                child_order_leg.order_leg_instruction(instruction="BUY_TO_COVER")
            child_order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)

        child_order1.add_order_leg(order_leg=child_order_leg)
        new_order.add_child_order_strategy(child_order_strategy=child_order1)

        child_order2 = new_order.create_child_order_strategy()
        child_order2.order_strategy_type("SINGLE")
        child_order2.order_session('NORMAL')
        child_order2.order_duration('GOOD_TILL_CANCEL')

        if SL_stop is not None:
            child_order2.order_type("STOP_LIMIT")
            child_order2.order_price(float(SL))
            child_order2.stop_price(float(SL_stop))
        else:
            child_order2.order_type("STOP")
            child_order2.stop_price(float(SL))

        child_order2.add_order_leg(order_leg=child_order_leg)
        new_order.add_child_order_strategy(child_order_strategy=child_order2)
        return new_order

    def make_STC_lim(self, Symbol:str, uQty:int, price:float, strike=None, action="STC", **kwarg):
        new_order=Order()
        new_order.order_strategy_type("SINGLE")
        new_order.order_type("LIMIT")
        new_order.order_duration('GOOD_TILL_CANCEL')
        new_order.order_price(float(price))

        order_leg = OrderLeg()
        order_leg.order_leg_quantity(quantity=int(uQty))

        if strike is not None:
            new_order.order_session('NORMAL')
            if action == "STC":
                order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
            elif action == "BTC":
                order_leg.order_leg_instruction(instruction="BUY_TO_CLOSE")
            order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
        else:
            new_order.order_session('SEAMLESS')
            if action == "STC":
                order_leg.order_leg_instruction(instruction="SELL")
            elif action == "BTC":
                order_leg.order_leg_instruction(instruction="BUY_TO_COVER")
            order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
        new_order.add_order_leg(order_leg=order_leg)
        return new_order

    def make_STC_SL(self, Symbol:str, uQty:int, SL:float, strike=None,
                    SL_stop:float=None, new_order=Order(), action="STC", **kwarg):
        new_order=Order()
        new_order.order_strategy_type("SINGLE")

        if SL_stop is not None:
            new_order.order_type("STOP_LIMIT")
            new_order.stop_price(float(SL_stop))
            new_order.order_price(float(SL))
        else:
            new_order.order_type("STOP")
            new_order.stop_price(float(SL))

        new_order.order_session('NORMAL')
        new_order.order_duration('GOOD_TILL_CANCEL')

        order_leg = OrderLeg()
        order_leg.order_leg_quantity(quantity=int(uQty))
        if strike is not None:
            if action == "STC":
                order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
            elif action == "BTC":
                order_leg.order_leg_instruction(instruction="BUY_TO_CLOSE")
            order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
        else:
            if action == "STC":
                order_leg.order_leg_instruction(instruction="SELL")
            elif action == "BTC":
                order_leg.order_leg_instruction(instruction="BUY_TO_COVER")
            order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
        new_order.add_order_leg(order_leg=order_leg)
        return new_order

    def make_STC_SL_trailstop(self, Symbol:str, uQty:int,  trail_stop_const:float, new_order=None, action="STC", **kwarg):
        if new_order is None:
            new_order = Order()
        new_order.order_strategy_type("SINGLE")
        new_order.order_strategy_type("SINGLE")
        new_order.order_type("TRAILING_STOP")
        new_order.order_session('NORMAL')
        new_order.order_duration('GOOD_TILL_CANCEL')
        new_order.stop_price_offset(trail_stop_const)
        new_order.stop_price_link_type('VALUE')
        new_order.stop_price_link_basis('BID')
        
        child_order_leg = OrderLeg()
        child_order_leg.order_leg_quantity(quantity=uQty)
        if len(Symbol.split("_")) > 1:
            if action == "STC":
                child_order_leg.order_leg_instruction(instruction="SELL_TO_CLOSE")
            elif action == "BTC":
                child_order_leg.order_leg_instruction(instruction="BUY_TO_CLOSE")
            elif action == "STO":
                child_order_leg.order_leg_instruction(instruction="SELL_TO_OPEN")
                new_order.stop_price_link_basis('ASK')
            child_order_leg.order_leg_asset(asset_type='OPTION', symbol=Symbol)
        else:
            if action == "STC":
                child_order_leg.order_leg_instruction(instruction="SELL")
            elif action == "BTC":
                child_order_leg.order_leg_instruction(instruction="BUY_TO_COVER")
            elif action == "STO":
                child_order_leg.order_leg_instruction(instruction="SELL_SHORT")
                new_order.stop_price_link_basis('ASK')            
            child_order_leg.order_leg_asset(asset_type='EQUITY', symbol=Symbol)
        new_order.add_order_leg(order_leg=child_order_leg)
        return new_order






