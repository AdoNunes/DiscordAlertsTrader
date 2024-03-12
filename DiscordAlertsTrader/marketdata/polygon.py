import requests
import pytz
from datetime import datetime
import pandas as pd 
from DiscordAlertsTrader.configurator import cfg

def get_poly_data(asset, start, end, range):
    """
    asset : str : ticker symbol, options be like O:TSLA240209C00200000
    start : int : start time in milliseconds
    end : int : end time in milliseconds
    range : str : time range, minute or second
    """
    url = f"https://api.polygon.io/v2/aggs/ticker/{asset}/range/1/{range}/{start}/{end}?adjusted=true&sort=asc&limit=50000&apiKey={cfg['polygon']['key']}"
    resp = requests.request("GET", url)
    if 'error' in resp.text:
        print(resp.text)
        return None
    return resp.json()


def get_poly_data_formatted(asset, start, end, range):
    """
    asset : str : ticker symbol, options be like O:TSLA240209C00200000
    start : int : start time in milliseconds
    end : int : end time in milliseconds
    range : str : time range, minute or second
    """
    data = get_poly_data(option_to_poly(asset), start, end, range)
    # local_timezone = pytz.timezone('America/New_York')
    # # match theta where 9 30 is utc but actually is EST
    # for ix, d in enumerate(data['results']):
    #     data['results'][ix]['t'] = datetime.strptime(datetime.fromtimestamp(d['t']/1000).replace(tzinfo=pytz.utc).astimezone(local_timezone).strftime('%m/%d/%Y %H:%M:%S'),
    #                             '%m/%d/%Y %H:%M:%S').timestamp()
    df = pd.DataFrame(data['results'])
    return df


def get_poly_data_askbid(asset, start, end, range, ask='h', bid = 'l'):
    """
    asset : str : ticker symbol, options be like O:TSLA240209C00200000
    start : int : start time in milliseconds
    end : int : end time in milliseconds
    range : str : time range, minute or second
    ask : str : ask column name (h for high)
    bid : str : bid column name (l for low)
    
    c The close price for the symbol in the given time period.
    h The highest price for the symbol in the given time period.
    l The lowest price for the symbol in the given time period.
    n The number of transactions in the aggregate window.
    o The open price for the symbol in the given time period.
    t The Unix Msec timestamp for the start of the aggregate window.
    v The trading volume of the symbol in the given time period.
    vw The volume weighted average price.
    """
    df = get_poly_data_formatted(asset, start, end, range)
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