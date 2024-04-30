"""
See https://http-docs.thetadata.us/docs/theta-data-rest-api-v2/vuoxgmabm17e9-using-the-python-api-and-the-rest-api for instructions on how to use thetadata's REST API
"""

from datetime import date, datetime, timedelta, time
import io
from typing import List
import os.path as op
from colorama import Fore
import pandas as pd
import pytz
import requests
import numpy as np

from thetadata import DataType, DateRange, OptionReqType, OptionRight
from thetadata import ThetaClient

from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.port_sim import save_or_append_quote
from DiscordAlertsTrader.message_parser import parse_symbol

def get_timestamp(row):
        date_time = (row[DataType.DATE] + timedelta(milliseconds=row[DataType.MS_OF_DAY])) # ET
        date_time = date_time.replace(tzinfo=pytz.timezone('US/Eastern'))
        return date_time.timestamp()

def get_timestamp_(row):
        date_time = ( datetime.strptime(str(int(row['date'])), "%Y%m%d")  + timedelta(milliseconds=row['ms_of_day'])) # ET
        date_time = pytz.timezone('America/New_York').localize(date_time).astimezone(pytz.utc)
        return date_time.timestamp()

def ms_to_time(ms_of_day: int) -> datetime.time:
    """Converts milliseconds of day to a time object."""
    return datetime(year=2000, month=1, day=1, hour=int((ms_of_day / (1000 * 60 * 60)) % 24),
                    minute=int(ms_of_day / (1000 * 60)) % 60, second=int((ms_of_day / 1000) % 60),
                    microsecond=(ms_of_day % 1000) * 1000).time()


def _format_strike(strike: float) -> int:
    """Round USD to the nearest tenth of a cent, acceptable by the terminal."""
    return round(strike * 1000)


def _format_date(dt: date) -> str:
    """Format a date obj into a string acceptable by the terminal."""
    return dt.strftime("%Y%m%d")


class ThetaClientAPI:
    def __init__(self):
         self.client = ThetaClient(launch=False)
         self.dir_quotes = cfg['general']['data_dir'] + '/hist_quotes'

    def get_hist_trades(self, symbol: str, date_range: List[date], interval_size: int=1000):
        """send request and get historical trades for an option symbol"""

        symb_info = parse_symbol(symbol)
        expdate = date(symb_info['exp_year'], symb_info['exp_month'], symb_info['exp_day']).strftime("%Y%m%d")
        root = symb_info['symbol']
        right = symb_info['put_or_call']
        strike = _format_strike(symb_info['strike'])
        date_s = _format_date(date_range[0])
        date_e = _format_date(date_range[1])

        url = f'http://127.0.0.1:25510/v2/hist/option/trade_quote?exp={expdate}&right={right}&strike={strike}&start_date={date_s}&end_date={date_e}&use_csv=true&root={root}&rth=true'
        header ={'Accept': 'application/json'}
        response = requests.get(url, headers=header)

        if  response.content == b'No data for contract.':
            return None
        # get quotes and trades to merge the with second level quotes
        df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
        # Apply the function row-wise to compute the timestamp and store it in a new column
        df['timestamp'] = df.apply(get_timestamp_, axis=1)
        df['timestamp'] = df['timestamp'].astype(int)
        df['volume'] = df['size']
        df['last'] = df['price']
        df = df[['timestamp', 'bid', 'ask', 'last', 'volume']]
        # round to second and group by second
        agg_funcs = {'bid': 'last',
                    'ask': 'last',
                    'last': 'last',
                    'volume': 'sum'}
        df_last = df.groupby('timestamp').agg(agg_funcs).reset_index()
        df_last['count'] = df.groupby('timestamp').size().values

        # get quotes
        url = f'http://127.0.0.1:25510/v2/hist/option/quote?exp={expdate}&right={right}&strike={strike}&start_date={date_s}&end_date={date_e}&use_csv=true&root={root}&ivl={interval_size}'
        header ={'Accept': 'application/json'}
        response_quotes = requests.get(url, headers=header)
        df_q = pd.read_csv(io.StringIO(response_quotes.content.decode('utf-8')))
        df_q['timestamp'] = df_q.apply(get_timestamp_, axis=1)
        df_q = df_q[['timestamp', "ask", "bid"]]
        # merge quotes and trades
        merged_df = pd.merge(df_last, df_q, on='timestamp', how='right')
        # rename cols
        merged_df.rename(columns={'ask_y': 'ask', 'bid_y': 'bid'}, inplace=True)
        merged_df = merged_df[['timestamp', 'bid', 'ask', 'last', 'volume']]
        merged_df['last'] = merged_df['last'].ffill()
        return merged_df

    def get_geeks(self, symbol: str, date_range: List[date], interval_size: int=1000, get_trades=True):
        """send request and get historical trades for an option symbol"""

        # symbol = "ACB_040524C6.5"
        # date_range = [date(2024, 4, 5), date(2024, 4, 5)]
        symb_info = parse_symbol(symbol)
        expdate = date(symb_info['exp_year'], symb_info['exp_month'], symb_info['exp_day']).strftime("%Y%m%d")
        root = symb_info['symbol']
        right = symb_info['put_or_call']
        strike = _format_strike(symb_info['strike'])
        date_s = _format_date(date_range[0])
        date_e = _format_date(date_range[1])

        fquote = f"{self.dir_quotes}/{symbol}.csv"
        fetch_data = True
        if op.exists(fquote):
            df = pd.read_csv(fquote)
            df['date'] = pd.to_datetime(df['timestamp'], unit='s').dt.date
            ds,de =  pd.to_datetime(date_s).date(),  pd.to_datetime(date_e).date()
            if ds in df['date'].values and de in df['date'].values:
                print(f"{Fore.GREEN} Found data for {symbol}: {date_s} to {date_e}")
                fetch_data = False
                data = df[(df['date']>=ds) & (df['date']<=de)]

        if fetch_data:
            print(f"{Fore.YELLOW} Fetching data from thetadata for {symbol}: {date_s} to {date_e}")
            url = f'http://127.0.0.1:25510/v2/hist/option/greeks?exp={expdate}&right={right}&strike={strike}&start_date={date_s}&end_date={date_e}&use_csv=true&root={root}&rth=true&ivl={interval_size}' 
            header ={'Accept': 'application/json'}
            response = requests.get(url, headers=header)
            if response.content.startswith(b'No data for'):
                return None
            df_q = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            df_q['timestamp'] = df_q.apply(get_timestamp_, axis=1)
            if not get_trades:
                return df_q
            
            trades = self.get_hist_trades( symbol, date_range, interval_size)
            merged_df = pd.merge(trades[['timestamp', 'last', 'volume']], df_q, on='timestamp', how='right')
            data = merged_df[['timestamp', 'bid', 'ask', 'last', 'volume', 'delta', 'theta',
                            'vega', 'lambda', 'implied_vol', 'underlying_price']]
            save_or_append_quote(data, symbol, self.dir_quotes)
        
        return data

    def get_delta_strike(self, ticker: str, exp_date: str, delta:float, right:str, timestamp:int, stock_price = None):
        """gets the strike for a given delta, if not found returns the closest delta

        Parameters
        ----------
        ticker : str
            root ticker
        exp_date : str
            yyyymmdd eg 20220930
        delta : float
            fraction delta, 40 delta = 0.4
        right : str
            either C or P
        timesetamp : int
            time when to look for delta

        Returns
        -------
        _type_
            _description_
        """
        
        url = f"http://127.0.0.1:25510/v2/list/strikes?root={ticker}&exp={exp_date}"
        header ={'Accept': 'application/json'}
        response = requests.get(url, headers=header)
        if response.content.startswith(b'No data for'):
            return None
        
        # get strikes, use underlying stock price if not available
        strikes = response.json()['response']
        if stock_price is None:
            mid = round(len(strikes)/2)
        else:
            mid = np.argmin([abs(s - stock_price*1000) for s in strikes])  
        st_done = []
        st_info = []
        cnt = 0
        while True:
            strike = strikes[min(mid, len(strikes)-1)]
            # date to ny time
            dt = datetime.fromtimestamp(timestamp, tz=pytz.utc).astimezone(pytz.timezone('America/New_York'))
            date_s = dt.date().strftime("%Y%m%d")
            url = f'http://127.0.0.1:25510/v2/hist/option/greeks?exp={exp_date}&right={right}&strike={strike}&start_date={date_s}&end_date={date_s}&use_csv=true&root={ticker}&rth=true&ivl=1000' 
            header ={'Accept': 'application/json'}
            print('getting delta for strike', strike)
            response = requests.get(url, headers=header)
            if response.content.startswith(b'No data for'):
                cnt += 1
                if cnt > 25:
                    print("stuck in the loop, returning")
                    return None, None
                continue
            df_q = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            
            # delete zeros bid-ask, geeks are wrong
            df_q = df_q[ (df_q['ask']!=0)].reset_index(drop=True)
            if not len(df_q):
                mid += 1
                cnt += 1
                if cnt > 25:
                    print("stuck in the loop, returning")
                    return None, None
                continue
            # get geeks at time
            ms_of_day = (dt.hour*3600 + dt.minute*60 + dt.second)* 1000 
            ix_g = np.argmin(abs(df_q['ms_of_day'] - ms_of_day))
            this_delta = df_q.iloc[ix_g]['delta']
            
            print("delta", this_delta, strike)
            if abs(abs(this_delta) - delta) < 0.1:
                break
            elif this_delta > delta:
                mid += 1
            elif this_delta < delta:
                mid -= 1
            else:
                sss
            if strike in st_done:
                
                st_done.append(strike)
                st_info.append((strike, this_delta))
                inx_closer = np.argmin([abs(s[1] - delta) for s in st_info])
                this_delta = st_info[inx_closer][1]
                print("no delta found, closest is", this_delta, st_info[inx_closer][0])
                break
            st_done.append(strike)
            st_info.append((strike, this_delta))
        
        exp_date_f = datetime.strptime(exp_date, "%Y%m%d").strftime("%m%d%y")
        return f"{ticker}_{exp_date_f}{right}{strike/1000}".replace(".0", ""), this_delta


    def get_hist_quotes(self, symbol: str, date_range: List[date], interval_size: int=1000):
        """send request and get historical quotes for an option symbol"""
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
                print(f"Found data for {symbol}: {drange.start} to {drange.end}")
                fetch_data = False
                data = df[(df['date']>=drange.start) & (df['date']<=drange.end)]

        if fetch_data:
            print(f"Fetching data from thetadata for {symbol}: {drange.start} to {drange.end}")
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


    def get_hist_quotes_stock(self, symbol: str, date_range: List[date], interval_size: int=1000):
        # symbol: AAPL
        # date_range: [date(2021, 9, 24), date(2021, 9, 24)] start and end date, or start date only
        # interval_size: 1000 (milliseconds)

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
                # print(f"Found data for {symbol}: {drange.start} to {drange.end}")
                fetch_data = False
                data = df[(df['date']>=drange.start) & (df['date']<=drange.end)]

        if fetch_data:
            # print(f"Fetching data from thetadata for {symbol}: {drange.start} to {drange.end}")
            data = self.client.get_hist_stock_REST(
                req=OptionReqType.QUOTE,
                root=symbol,
                date_range=drange,
                interval_size=interval_size,
                use_rth=False,
            )

            # Apply the function row-wise to compute the timestamp and store it in a new column
            data['timestamp'] = data.apply(get_timestamp, axis=1)
            data['timestamp'] = data['timestamp'].astype(int)
            data['bid'] = data[DataType.BID]
            data['ask'] = data[DataType.ASK]
            data = data[['timestamp', 'bid', 'ask']]
            data = data[(data['ask']!=0) | (data['bid']!=0)]
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
    # symbol = "RDW_022324C3"
    # date_range = [date(2024, 2, 23)]
    # quotes = client.get_hist_quotes(symbol, date_range)
    # print(quotes)

    data = client.client.get_hist_stock_REST(
        req=OptionReqType.QUOTE,
        root='FLGC',
        date_range=DateRange(date(2024, 3, 25), date(2024, 3, 25)),
        interval_size=1000,
        use_rth=True,
    )

    print(data.head())
