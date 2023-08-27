from abc import ABC, abstractmethod
from ..configurator import cfg

class BaseBroker(ABC):
    @abstractmethod
    def __init__(self, api_key, secret_key, passphrase):
        pass

    @abstractmethod
    def get_session(self):
        pass

    @abstractmethod
    def get_quotes(self, symbol):
        pass

    @abstractmethod
    def send_order(self, side, symbol, order_type, quantity, price=None, stop_price=None):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_orders(self):
        pass

    # @abstractmethod
    # def get_order_status(self, order_id):
    #     pass
    
    def get_order_info(self, order_id):
        #     sold_unts = order_info['orderLegCollection'][0]['quantity']

        # if 'price' in order_info.keys():
        #     stc_price = order_info['price']
        # elif 'stopPrice' in order_info.keys():
        #     stc_price = order_info['stopPrice']
        # elif "orderActivityCollection" in order_info.keys():
        #     prics = []
        #     for ind in order_info["orderActivityCollection"]:
        #         prics.append([ind['quantity'], ind['executionLegs'][0]['price']])
        #         n_tot= sum([i[0] for i in prics])
        #     stc_price =  sum([i[0]*i[1] for i in prics])/ n_tot

        # bto_price = self.portfolio.loc[open_trade, "Price"]
        # bto_price_alert = self.portfolio.loc[open_trade, "Price-alert"]
        # bto_price_actual = self.portfolio.loc[open_trade, "Price-actual"]
        # stc_PnL = float((stc_price - bto_price)/bto_price) *100

        # xQty = sold_unts/ self.portfolio.loc[open_trade, "Qty"]

        # date = order_info["closeTime"]
        pass


def get_brokerage(name=cfg['general']['BROKERAGE']):
    if name.lower() == 'tda':
        from .TDA_api import TDA
        accountId = cfg['TDA']['accountId']
        accountId = None if len(accountId) == 0 else accountId
        tda = TDA(accountId=accountId)
        tda.get_session()
        return tda
    elif name.lower() == "webull":
        from .weBull_api import weBull
        wb = weBull()
        success = wb.get_session()
        if success:
            return wb
        else:
            raise Exception("Failed to get session for weBull")
    elif name.lower() == 'etrade':
        from .eTrade_api import eTrade
        accountId = cfg['etrade']['accountId']
        accountId = None if len(accountId) == 0 else accountId
        et = eTrade(accountId=accountId)
        try:
            et.get_session()
        except Exception as e:
            print("Got error: \n", e, "\n Trying again...if it fails again, rerun the application.")
            et.get_session()
        return et
    # todo : implement stub in ibkr module
    elif name.lower() == 'ibkr':
        from .ibkr_api import Ibkr
        accountId = cfg['ibkr']['accountId']
        accountId = None if len(accountId) == 0 else accountId
        ibkr = Ibkr(accountId=accountId)
        try:
            ibkr.get_session()
        except Exception as e:
            print("Got error: \n", e, "\n Trying again...if it fails again, rerun the application.")
            ibkr.get_session() 
        return ibkr