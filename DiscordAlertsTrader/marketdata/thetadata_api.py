"""
See https://http-docs.thetadata.us/docs/theta-data-rest-api-v2/vuoxgmabm17e9-using-the-python-api-and-the-rest-api for instructions on how to use thetadata's REST API
"""

from datetime import date, datetime, timedelta
import re
from typing import List
import os.path as op
from colorama import Fore
import pandas as pd
import pytz

from thetadata import DataType, DateRange, OptionReqType, OptionRight
from thetadata import ThetaClient

from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.port_sim import save_or_append_quote

def get_timestamp(row):
        date_time = (row[DataType.DATE] + timedelta(milliseconds=row[DataType.MS_OF_DAY])) # ET
        date_time = date_time.replace(tzinfo=pytz.timezone('US/Eastern'))
        return date_time.timestamp()

def parse_symbol(symbol:str):
    # symbol: APPL_092623P426
    match = re.match(r"^([A-Z]+)_(\d{2})(\d{2})(\d{2})([CP])((?:\d+)(?:\.\d+)?)", symbol)

    if match:
        option ={
            "symbol": match.group(1),
            "exp_month": int(match.group(2)),
            "exp_day": int(match.group(3)),
            "exp_year": 2000+int(match.group(4)),
            "put_or_call": match.group(5),
            "strike": eval(match.group(6))
            }
        return option

class ThetaClientAPI:
    def __init__(self):
         self.client = ThetaClient(launch=False)
         self.dir_quotes = cfg['general']['data_dir'] + '/hist_quotes'

    def get_hist_quotes(self, symbol: str, date_range: List[date], interval_size: int=1000):
        # symbol: APPL_092623P426
        # date_range: [date(2021, 9, 24), date(2021, 9, 24)] start and end date, or start date only
        # interval_size: 1000 (milliseconds)

        option = parse_symbol(symbol)
        exp = date(option['exp_year'], option['exp_month'], option['exp_day'])
        right = OptionRight.PUT if option['put_or_call'] == 'P' else OptionRight.CALL
        if len(date_range) == 1:
            drange = DateRange(date_range[0], date_range[0])
        else:
            drange = DateRange(date_range[0], date_range[1])

        fquote = f"{self.dir_quotes}/{symbol}.csv"
        fetch_data = True
        if op.exists(fquote):
            df = pd.read_csv(fquote)
            df['date'] = pd.to_datetime(df['timestamp'], unit='s').dt.date
            if drange.start in df['date'].values and drange.end in df['date'].values:
                print(f"{Fore.GREEN} Found data for {symbol}: {drange.start} to {drange.end}")
                fetch_data = False
                data = df[(df['date']>=drange.start) & (df['date']<=drange.end)]

        if fetch_data:
            print(f"{Fore.YELLOW} Fetching data from thetadata for {symbol}: {drange.start} to {drange.end}")
            data = self.client.get_hist_option_REST(
                req=OptionReqType.QUOTE,
                root=option['symbol'],
                exp=exp,
                strike=option['strike'],
                right=right,
                date_range=drange,
                interval_size=interval_size
            )

            # Apply the function row-wise to compute the timestamp and store it in a new column
            data['timestamp'] = data.apply(get_timestamp, axis=1)
            data['timestamp'] = data['timestamp'].astype(int)
            data['bid'] = data[DataType.BID]
            data['ask'] = data[DataType.ASK]
            data = data[['timestamp', 'bid', 'ask']]
            data[(data['ask']==0) & (data['bid']==0)] = pd.NA
            # data = data[(data['ask']!=0)] # remove zero ask & (data['bid']!=0)
            
            save_or_append_quote(data, symbol, self.dir_quotes)
        
        return data

    def get_price_at_time(self, symbol: str, unixtime: int, price_type: str="BTO"):
        # example args
        # symbol: APPL_092623P426
        # unixtime: 1632480000 (this is actually ET unixtime)

        fquote = f"{self.dir_quotes}/{symbol}.csv"
        side = 'ask' if price_type in ['BTO', 'BTC'] else 'bid'
        unixtime_date = pd.to_datetime(unixtime, unit='s').date()
        fetch_quote = True
        if op.exists(fquote):
            df = pd.read_csv(fquote)
            df['date'] = pd.to_datetime(df['timestamp'], unit='s').dt.date
            if unixtime_date in df['date'].values:
                df_date = df[df['date']==unixtime_date]
                if df_date['timestamp'].min() <= unixtime <= df_date['timestamp'].max():
                    print(f"{Fore.YELLOW} Found data for {symbol} at {datetime.fromtimestamp(unixtime)}")
                    fetch_quote = False
                    quotes = df_date

        
        if fetch_quote:
            date = pd.to_datetime(unixtime, unit='s').date()
            try:
                quotes = self.get_hist_quotes(symbol, [date])
            except Exception as e:
                print(f"{Fore.RED} Error: {e}")
                return -1, 0
            save_or_append_quote(quotes, symbol, self.dir_quotes)

        idx = quotes['timestamp'].searchsorted(unixtime, side='right')
        if idx < len(quotes):
            return quotes[side].iloc[idx], quotes['timestamp'].iloc[idx] - unixtime
        
        print(f"{Fore.RED} Error: price for {symbol} not found at {datetime.fromtimestamp(unixtime)}")
        return -1, 0


if __name__ == "__main__":
    client = ThetaClientAPI()
    symbol = "RDW_022324C3"
    date_range = [date(2024, 2, 23)]
    quotes = client.get_hist_quotes(symbol, date_range)
    print(quotes)