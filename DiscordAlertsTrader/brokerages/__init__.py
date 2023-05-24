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
        # bto_price_alert = self.portfolio.loc[open_trade, "Price-Alert"]
        # bto_price_current = self.portfolio.loc[open_trade, "Price-Current"]
        # stc_PnL = float((stc_price - bto_price)/bto_price) *100

        # xQty = sold_unts/ self.portfolio.loc[open_trade, "uQty"]

        # date = order_info["closeTime"]
        pass


def get_brokerage(name=cfg['general']['BROKERAGE']):
    if name.lower() == 'tda':
        from .TDA_api import TDA
        tda = TDA()
        tda.get_session()
        return tda
    elif name == "webull":
        NotImplemented
    elif name.lower() == 'etrade':
        from .eTrade_api import eTrade
        et = eTrade()
        try:
            et.get_session()
        except Exception as e:
            print("Got error: \n", e, "\n Trying again...if it fails again, rerun the application.")
            et.get_session()
        return et