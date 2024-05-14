import requests
import os
from datetime import timedelta, datetime
import pandas as pd 
from DiscordAlertsTrader.configurator import cfg
import matplotlib.pyplot as plt

def get_poly_data_rest(asset, start, end, range):
    """
    asset : str : ticker symbol, options be like O:TSLA240209C00200000
    start : int : start time in milliseconds
    end : int : end time in milliseconds
    range : str : time range, minute or second
    """
    url = f"https://api.polygon.io/v2/aggs/ticker/{asset}/range/1/{range}/{start}/{end}?adjusted=true&sort=asc&limit=50000&apiKey={cfg['polygon']['key']}"
    print(url)
    resp = requests.request("GET", url)
    if 'error' in resp.text:
        print(resp.text)
        return None
    return resp.json()


def get_poly_data(asset, start, end, range, ask='h', bid = 'l', asset_type='O', 
                  dir_quotes=cfg['general']['data_dir'] + '/hist_quotes_poly'):
    """
    asset : str : ticker symbol, options be like O:TSLA240209C00200000
    start : int : start time in milliseconds
    end : int : end time in milliseconds
    range : str : time range, minute or second
    ask : str : ask column name (h for high), if None will return all fields
    bid : str : bid column name (l for low)
    asset_type: str : asset type, O for option S for stock
    dir_quotes : str : directory to save quotes
    
    c The close price for the symbol in the given time period.
    h The highest price for the symbol in the given time period.
    l The lowest price for the symbol in the given time period.
    n The number of transactions in the aggregate window.
    o The open price for the symbol in the given time period.
    t The Unix Msec timestamp for the start of the aggregate window.
    v The trading volume of the symbol in the given time period.
    vw The volume weighted average price.
    """

    if asset_type == 'O':
        symbol = option_to_poly(asset)
    elif asset_type == 'S':
        symbol = asset
    
    fetch = True
    if dir_quotes is not None:
        # check if it exists
        fquote = f"{dir_quotes}/{symbol}.csv"
        if os.path.exists(fquote):
            df = pd.read_csv(fquote)

            dates = pd.to_datetime(df['t']/1000, unit='s').dt.date
            start_ = start + timedelta(days=1)
            if start_ in dates.values and end in dates.values:
                print(f"Found data for {symbol}: {start} to {end}")
                df = df[(dates >= start) & (dates <= end)]
                df.reset_index(drop=True, inplace=True)
                fetch = False
    if fetch:
        res = get_poly_data_rest(symbol, start, end, range)
        df = pd.DataFrame(res['results'])
        df['timestamp'] = df['t']/1000
        if dir_quotes is not None: 
            try:
                quotes = pd.read_csv(fquote)
                quotes = pd.concat([df, quotes], ignore_index=True)
                quotes = quotes.sort_values(by=['timestamp']).drop_duplicates(subset=['timestamp'])
                quotes.to_csv(fquote, index=False)                
            except FileNotFoundError:
                df.to_csv(fquote, index=False)

    if ask is None:
        return df
    
    df['ask'] = df[ask]
    df['bid'] = df[bid]
    df['timestamp'] = df['t']
    df = df[['timestamp', 'ask', 'bid']]
    return df


def format_strike(strike):    
    strike_r = f"{strike}".split(".")[0]
    strike_r = f"{strike_r:0>5}"
    if "." in str(strike):
        strike_f = f"{strike}".split(".")[1]
        strike_r += f"{strike_f:0<3}"
    else:
        strike_r += "000"
    return strike_r

def option_to_poly(option:str):
    """
    option : str : option symbol,
    option ouput  be like O:TSLA240209C00200000
    """
    asset, oinfo = option.split("_")
    date = oinfo[4:6] + oinfo[:4]
    strike = format_strike(oinfo[7:])
    return f"O:{asset}{date}{oinfo[6]}{strike}"