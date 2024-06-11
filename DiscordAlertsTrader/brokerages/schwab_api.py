import schwab
from DiscordAlertsTrader.configurator import cfg

import httpx
import os

from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.brokerages import BaseBroker, retry_on_exception


class SW(BaseBroker):
    def __init__(self, accountId=None):
        """
        accountId: id of the account
        """
        self.name = 'ts'
        self.accountId = accountId

    def get_session(self):       
        if len(cfg['schwab']['key']) < 10:
            raise ValueError( "No Schawb secret key found, fill it in the config.ini file")
        
        if not os.path.exists('schwab_token.json'):
            # Create a new session
            self.session = schwab.auth.client_from_manual_flow(cfg['schwab']['key'],
                                                            cfg['schwab']['secret'],
                                                            cfg['schwab']['redirect_url'], 
                                                            token_path='schwab_token.json')
        else:
            self.session = schwab.auth.client_from_token_file('schwab_token.json',
                                                              cfg['schwab']['key'],
                                                              cfg['schwab']['secret'])
        
        resp = self.session.get_account_numbers()
        assert resp.status_code == httpx.codes.OK
        self.accountId = resp.json()[0]['hashValue']
            
        success = not self.session.session.is_closed
        if success:
            print("Logged in Schwab successfully")
        else:
            print("Failed to login Schwab")
        return success
    

    def _convert_option_fromsw(self, ticker):
        """
        Convert ticker from 'SPX yearmonthdayC00011000' to 'SPX_monthdayyearC110' format.
        
        Parameters:
        ticker (str): Ticker in the original format.
        
        Returns:
        str: Ticker in the desired format.
        """
        if " " not in ticker:
            return ticker
        splits =  ticker.split(" ")  # Split the ticker by spaces
        symb, date_part =splits[0], splits[-1]
        date_part = date_part.strip()
        formatted_date = date_part[2:6] +date_part[:2]   # Reformat the date part
        right = date_part[6]
        strike = int(date_part[7:])/1000
        return f"{symb}_{formatted_date}{right}{strike}".replace(".0", "")  # Combine the parts in the desired format
    
    def _convert_option_tosw(self, ticker):
            """
            Convert ticker from 'SPX_monthdayyearC110' to 'SPX yearmonthdayC00110000' format.
            
            Parameters:
            ticker (str): Ticker in the original format.
            
            Returns:
            str: Ticker in the desired format.
            """
            if "_" not in ticker:
                return ticker
            symb, date_part = ticker.split("_")  # Split the ticker by spaces
            formatted_date = date_part[4:6] + date_part[:4]   # Reformat the date part
            right = date_part[6]
            strike = f"{int(float(date_part[7:]) * 1000):08d}"
            symb = symb.split()[0].strip().ljust(6)
            return f"{symb}{formatted_date}{right}{strike}"  # Combine the parts in the desired format
        
    @retry_on_exception(sleep=1)
    def get_quotes(self, symbol:list):
        
        symbol = [self._convert_option_tosw(s) for s in symbol]
        resp = self.session.get_quotes(symbol)
        assert resp.status_code == httpx.codes.OK    

        resp = resp.json()
        quotes = {}
        for symb, vals in resp.items():
            if symb == 'errors':
                continue
            ticker = self._convert_option_fromsw(symb)
            quote = vals['quote']
            quoteTimeInLong = quote.get("tradeTime")*1000
        
            quotes[ticker] = {
                            'symbol' : ticker,
                            'description': "",
                            'askPrice': float(quote.get("askPrice")),  
                            'bidPrice': float(quote.get("bidPrice")),    
                            'lastPrice': float(quote.get("lastPrice")),
                            'quoteTimeInLong': quoteTimeInLong,
                            "status": '',
                            "OpenInterest": float(quote.get('openInterest')),  
                            "BidSize": float(quote.get('bidSize')), 
                            "AskSize": float(quote.get('askSize')), 
                            "LastSize": float(quote.get('lastSize')),
                            }
        
        for k in resp.get('errors', []):
            if k is not None:
                for symbol in resp['errors'][k]:
                    ticker = self._convert_option_fromsw(symbol)
                    quotes[ticker] = {
                                    'symbol' : ticker,
                                    'description': 'Symbol not found',
                                    'askPrice': 0,  
                                    'bidPrice': 0,    
                                    'quoteTimeInLong': 0,
                                    "status": ''
                                    }
        return quotes
    
    
    def send_order(self, side, symbol, order_type, quantity, price=None, stop_price=None):
        pass


    def cancel_order(self, order_id):
        pass


    def get_orders(self):
        pass

    def get_order_info(self, order_id):
        pass