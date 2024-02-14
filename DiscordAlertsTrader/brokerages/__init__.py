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

    @abstractmethod
    def get_order_info(self, order_id):
        pass


def get_brokerage(name=cfg['general']['BROKERAGE']):
    if name.lower() == 'tda':
        from .TDA_api import TDA
        accountId = cfg['TDA']['accountId']
        accountId = None if len(accountId) == 0 else accountId
        tda = TDA(accountId=accountId)
        tda.get_session()
        return tda
    elif name.lower() == 'tradestation':
        from .tradestation_api import TS
        accountId = cfg['tradestation']['accountId']
        accountId = None if len(accountId) == 0 else accountId
        ts = TS(accountId=accountId)
        ts.get_session()
        return ts
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