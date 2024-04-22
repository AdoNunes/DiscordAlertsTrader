import pandas as pd
import re
import json
from datetime import datetime, timezone, timedelta
from DiscordAlertsTrader.message_parser import parse_trade_alert
from DiscordAlertsTrader.server_alert_formatting import (
    format_alert_date_price,
)
try:
    import webcolors
    from discordalerts.lib.util import get_stock_signal_from_rgb
    from discordalerts.lib.constants import Signal
except ImportError as e:
    print("Exception: ", e)
    print("Download this lib from https://github.com/Conceptron/discordalerts")

def format_0dte_weeklies(contract, message_date, remove_price=True):
    "remove price when stc title is bto"
    if "0DTE" in contract.upper():
        msg_date = message_date.strftime('%m/%d')
        contract = re.sub(r"0DTE", msg_date,contract, flags=re.IGNORECASE)
        if remove_price:
            contract = contract.split(" @")[0]
    elif "weeklies" in contract.lower():
        msg_date= message_date
        days_until_friday = (4 - msg_date.weekday() + 7) % 7
        msg_date += timedelta(days=days_until_friday)
        msg_date = msg_date.strftime('%m/%d')
        contract =  re.sub(r"Weeklies", msg_date,contract, flags=re.IGNORECASE)
        if remove_price:
            contract = contract.split(" @")[0]
    return contract

def kent_formatting(message):
    """
    Reformat Discord message from Kent
    """
    alert = ''
    for mb in message['embeds']:
        if mb['description']:
            alert += mb['description']
    return alert

def pbt_formatting(message):
    """
    Reformat Discord message from PBT
    """
    for mb in message['embeds']:
        if mb['description']:
            if 'color' not in mb:
                continue
            color = mb['color']
            rgb = webcolors.hex_to_rgb(color)
            signal = get_stock_signal_from_rgb(*rgb)
            desc = mb['description']
            if signal == Signal.BUY:
                action = "BTO"
                m = re.search(r'\*([A-Z]+)\*', desc)
                if m:
                    ticker = m.group(1)
                    m = re.search(r'\$(\d+\.\d+)', desc)
                    if m:
                        price = m.group(1)
                        alert = f"{action} {ticker} @{price}"
                        return alert
    return ''

def sirgoldman_formatting(message):
    """
    Reformat Discord message from sirgoldman
    """
    alert = ''
    for mb in message['embeds']:
        if mb['description']:
            if mb['title'].upper() == 'ENTRY':
                pattern = r'(\$[A-Z]+)\s*(\d+[.\d+]*[c|p|C|P])\s*@\s*(\d+(?:[.]\d+)?|\.\d+)'
                match = re.search(pattern, mb['description'], re.IGNORECASE)
                if match:
                    ticker, strike, price = match.groups()
                    try:
                        msg_date = datetime.strptime(message['timestamp'], '%Y-%m-%dT%H:%M:%S.%f%z')
                    except ValueError:
                        msg_date = datetime.strptime(message['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
                    msg_date = msg_date.strftime('%m/%d')
                    ext = mb['description'].replace("**","").split(price)[-1]
                    alert = f"BTO {ticker[1:]} {strike.upper()} {msg_date} @{price} {ext}"
            else:
                alert = f"{mb['title']}: {mb['description']}"
    return alert


def bishop_formatting(message):
    """
    Reformat Discord message from bishop
    """
    alert = ''
    for mb in message['embeds']:

        match = False
        if mb['title'] == "I'm entering":
            action = "BTO"
            match = True
            msg = mb['description']
            extra = mb['description'].split("@$")[1].split("\r\n\r\n*These are ONLY my opinions")[0].replace("\r\n\r\n", " ")
            pattern = "\*\*Option:\*\* ([A-Z]+) (\d.+) ([PC]) (\d+\/\d+)\\r\\n\\r\\n\*\*Entry:\*\* @\$(\d+\.\d+)"
        elif mb['title'].startswith("Trimming"):
            action = "STC"
            match = True
            msg = mb['title']
            extra = "  " + mb['description'].split("\r\n\r\n*These are ONLY my opinions")[0].replace("\r\n\r\n", " ")
            pattern = "([A-Z]+) (\d.+) ([PC]) (\d+\/\d+) @\$(\d+\.\d+)"

        if match:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                ticker, strike, otype, expdate, price = match.groups()
                qty = "3" if action == "BTO" else "1"
                extra = extra.replace(price, "")
                alert = f"{action} {qty} {ticker} {strike.upper()}{otype} {expdate} @{price} {extra}"
        if not match:
            alert = f"{mb['title']}: {mb['description']}"
    return alert


def flohai_formatting(message):
    """
    Reformat Discord message from flohai
    """
    alert = ''
    if not len(message['embeds']):
        return alert
    mb=message['embeds'][0]

    otype = 'P' if 'Put' in mb['title'] else "C" if "Call" in mb['title'] else ''
    if not len(otype):
        return alert
    ticker = mb['title'].split()[-1]
    info = mb['fields'][0]["value"]

    rating = re.search("\*\*AI Confidence Rating:\*\* ([\d.]+)%", info)
    if rating:
        rating = rating.group(1)
    else:
        return alert

    strike = re.search("\*\*Strike:\*\* ([\d.]+)", info).group(1)
    expiration = re.search("\*\*Expiration:\*\* (\d{1,2}/\d{1,2}/\d{4})", info).group(1)
    ask =  re.search("\*\*Ask:\*\* ([\d.]+)", info).group(1)

    alert = f"BTO {ticker} {strike}{otype} {expiration} @{ask} | SL: {rating}%"
    return alert

def tradir_formatting(message):

    alert = ''
    if not len(message['embeds'][0]['fields']):
        return alert

    for fld in message['embeds'][0]['fields']:
        if fld['name'] == "Symbol":
            symbol = fld['value']
        elif fld['name'] == "Strike":
            strike = fld['value']
        elif fld['name'] == "Expiration":
            expiration = fld['value']
        elif fld['name'] == "Call/Put":
            otype = "C" if fld['value']=='Call' else "P"
        elif fld['name'] == "Buy/Sell":
            action = "BTO" if fld['value']=='Buy' else "STC"
        elif fld['name'] == "AI Confidence":
            rating = fld['value']
    alert = f"{action} {symbol} {strike.replace('.0', '')}{otype} {expiration} @1| SL: {rating}"
    return alert


def flint_formatting(message):

    alert = ''
    for mb in message['embeds']:
        if mb['description']:
            alert += mb['description']
    if len(alert):
        pattern = r'([A-Z]+)\s*(\d+[.\d+]*[c|p|C|P])\s(\d{1,2}\/\d{1,2})\s*@\s*(\d+(?:[.]\d+)?|\.\d+)'
        match = re.search(pattern, alert, re.IGNORECASE)
        if match:
            out = match.groups()
            if len(out) == 4:
                ticker, strike, msg_date, price = out
            elif len(out) == 3:
                ticker,  strike, price = out
                try:
                    msg_date = datetime.strptime(message['timestamp'], '%Y-%m-%dT%H:%M:%S.%f%z')
                except ValueError:
                    msg_date = datetime.strptime(message['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
                msg_date = msg_date.strftime('%m/%d')
            else:
                print('ERROR: wrong number of groups in flint_formatting')
                return alert
            ext = alert.split(price)[-1]
            alert = f"BTO {ticker} {strike.upper()} {msg_date} @{price} {ext}"
    return alert


def moneymotive_formatting(message, msg_date_ob):

    if message['content'] is None:
        return alert
    alert = message['content']

    if "%" in alert: # just status update
        return alert

    if ":rotating_light:" in alert and "/" not in alert and "0DTE" not in alert:
        alert = alert.replace(":rotating_light:", "0DTE :rotating_light:")

    if "0DTE" in alert:
        alert = format_0dte_weeklies(alert, msg_date_ob, False)

    pattern = r'\$?(\w+)\s+([\d.]+)\s+(\w+)\s+(\d{1,2}\/\d{1,2})\s+@\s+([\d.]+)'
    match = re.search(pattern, alert, re.IGNORECASE)
    if match:
        ticker, strike, otype, expDate, price = match.groups()
        alert = f"BTO {ticker} {strike.upper()}{otype[0]} {expDate} @{price}"
    else:
        pattern = r'\$?(\w+)\s+([\d.]+)\s+(\w+)\s+@\s+([\d.]+)\s+\w*\s*(\d{1,2}\/\d{1,2})'
        match = re.search(pattern, alert, re.IGNORECASE)
        if match:
            ticker, strike, otype, price, expDate = match.groups()
            alert = f"BTO {ticker} {strike.upper()}{otype[0]} {expDate} @{price}"
    return alert

def makeplays_main_formatting(message, msg_date_ob):
    """
    Reformat Discord message from makeplays
    """
    alert = ''
    for mb in message['embeds']:
        if mb['title'] == "Open":
            alert = mb['description'].replace(" at ", " @ ")

            r'(?:BTO)?\s*([\d]+)?\s+([A-Z]+)\s*(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)?\s+([\d.]+)([C|P])\s+@\s*([\d.]+)'

            if "0DTE" in alert.upper() or "1DTE" in alert.upper():
                alert = format_0dte_weeklies(alert, msg_date_ob, False)
            if "BTO" not in alert:
                alert = f"BTO {alert}"

        elif mb['title'].startswith("Close"):
            alert = mb['description'].replace(" at ", " @ ")
            if "STC" not in alert:
                alert = f"STC {alert}"
    return alert

def kingmaker_main_formatting(message, msg_date_ob):
    """
    Reformat Discord message from makeplays
    """
    alert = ''
    for mb in message['embeds']:
        if mb['title'] == "Open":
            alert = mb['description'].replace(" buy ", " ").replace(" Buy ", " ")

            pattern = r'([A-Z]+)\s*(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)?\s+\$([\d.]+)\s+(Call|Calls|calls|Puts|puts)\s+@?\$?([\d.]+)'
            match = re.search(pattern, alert, re.IGNORECASE)
            if match:
                ticker, expDate, strike, otype, price = match.groups()
                alert = f"BTO {ticker} {strike.upper()}{otype[0].upper()} {expDate} @{price}"
        else:
            alert = f"{mb['title']}: {mb['description']}"

    return alert

def diesel_formatting(message, msg_date_ob):
    """
    Reformat Discord message from diesel
    """
    alert = ''

    if message['content'] is None:
        return alert
    alert = message['content']

    pattern = r'BTO\s+([A-Z]+)\s+([\d.]+)([c|p])\s*(\d{1,2}\/\d{1,2})?\s+@\s*([\d.]+)'
    match = re.search(pattern, alert, re.IGNORECASE)
    if match:
        ticker, strike, otype, expDate, price = match.groups()
        if expDate is None:
            bto = f"BTO {ticker} {strike.upper()}{otype[0]} 0DTE @{price}"
            alert = format_0dte_weeklies(alert, msg_date_ob, False)
        else:
            alert = f"BTO {ticker} {strike.upper()}{otype[0]} {expDate} @{price}"
    return alert


def eclipse_formatting(message):
    """
    message from eclipse to content message
    """
    if not message['content']:
        return ""

    alert = message['content']
    pattern = r'([A-Z]+)\s*(\d+[.\d+]*[c|p|C|P])\s*(\d{1,2}\/\d{1,2})?\s*@\s*(\d+(?:[.]\d+)?|\.\d+)'
    match = re.search(pattern, alert, re.IGNORECASE)
    if match:
        ticker, strike, expDate, price = match.groups()
        qty = re.search(r'(\d+)\s*Contracts', alert, re.IGNORECASE)
        qty = qty.group(1) if qty else "1"
        chall = ''
        if "Challenge Account" in alert:
            chall += " | Challenge Account"
        alert = f"BTO {qty} {ticker} {strike.upper()} {expDate} @{price}{chall}"
    else: # date might come first
        pattern = r'([A-Z]+)\s*(\d{1,2}\/\d{1,2})?\s*(\d+[.\d+]*[c|p|C|P])\s*@\s*(\d+(?:[.]\d+)?|\.\d+)'
        match = re.search(pattern, alert, re.IGNORECASE)
        if match:
            ticker, expDate, strike, price = match.groups()
            qty = re.search(r'(\d+)\s*Contracts', alert, re.IGNORECASE)
            qty = qty.group(1) if qty else "1"
            chall = ''
            if "Challenge Account" in alert:
                chall += " | Challenge Account"
            alert = f"BTO {qty} {ticker} {strike.upper()} {expDate} @{price}{chall}"
        else: # diff format
            pattern = r'\$?(\w+)\s+\$?([\d.]+)\s+(\w+)\s+(\d{1,2}\/\d{1,2})\s+@([\d.]+)'
            match = re.search(pattern, alert, re.IGNORECASE)
            if match:
                ticker, strike, otype, expDate, price = match.groups()
                qty = re.search(r'(\d+)\s*Contracts', alert, re.IGNORECASE)
                qty = qty.group(1) if qty else "1"
                alert = f"BTO {qty} {ticker} {strike.upper()}{otype[0]} {expDate} @{price}"
            else:
                pattern = r'\$([A-Z]+)\s+([\d.]+)\s+(CALL|PUT)\s+(\d{1,2}\/\d{1,2})\s+\@\s*([\d.]+)'
                match = re.search(pattern, alert, re.IGNORECASE)
                if match:
                    ticker, strike, otype, expDate, price = match.groups()
                    alert = f"BTO {ticker} {strike.upper()}{otype[0]} {expDate} @{price}"

    return alert

def bear_formatting(message):
    alert = ""
    for mb in message['embeds']:
        if mb['title'].replace(":", "") in ['Daytrade', "LOTTO", "Swing"]:
            description = mb['description']
            contract_match = re.search(r'\*\*Contract:\*\* \$([A-Z]+) (\d{1,2}\/\d{1,2}) ([\d.]+)([cCpP])', description)
            fill_match = re.search(r'\*\*Entry:\*\*\s*\@?\$?\s*([\d.]+)', description)

            if contract_match is None:
                contract_match = re.search(r'\*\*Ticker: \$([A-Z]+)\*\*.*\*Contract: (\d{1,2}\/\d{1,2})\s+([\d.]+)([cCpP])', description)
                fill_match = re.search(r'\*\*Entry:\s*\@?\$?\s*([\d.]+)\*\*', description)
                if contract_match is None:
                    alert = f"{mb['title']}: {mb['description']}"
                    continue
            contract, exp_date, strike, otype = contract_match.groups()
            if fill_match is not None:
                price= float(fill_match.groups()[0])
            else:
                price = None
            alert += f"BTO {contract} {strike}{otype.upper()} {exp_date} @{price} {mb['title']}"
        else:
            alert = f"{mb['title']}: {mb['description']}"
    return alert

def oculus_formatting(message, msg_date_ob):
    alert = message['content']
    if "%" in alert: # just status update
        return alert

    if "(0dte)" in alert.lower():
        alert = alert.replace("(0dte)", "0DTE")
        alert = alert = format_0dte_weeklies(alert, msg_date_ob, False)

    pattern = r'\$(\w+)\s+\$?(\d[\d,]+)\s+(\w+)\s+(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s+@([\d.]+)'
    match = re.search(pattern, alert, re.IGNORECASE)
    if match:
        ticker, strike, otype, expDate, price = match.groups()
        alert = f"BTO {ticker} {strike.upper()}{otype[0]} {expDate} @{price}"
    return alert


def convert_date(input_date):
    # Map month abbreviations to their numeric representation
    month_mapping = {
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
        'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
    }
    # Extract day, month abbreviation, and year
    day = input_date[:-5]
    month_abbrev = input_date[-5:-2]
    year = input_date[-2:]
    # Convert month abbreviation to numeric representation
    month = month_mapping.get(month_abbrev.upper(), '00')
    converted_date = f"{month}/{day}/20{year}"
    return converted_date

def theta_warrior_elite(message):
    alert = message['content']
    if alert is None:
        return ""
    pattern = re.search(r'\$(\w+).\S*\s*(BTO|STC)\s+(\d{1,2}\w{3}\d{2})\s+([\d.]+)([CPcp])\s+(?:at|@)\s+\$([\d.]+)', alert)
    if pattern:
        ticker, action, exp_date, strike, otype,  price = pattern.groups()
        exp_date = convert_date(exp_date)

        if action == "BTO":
            alert = f"{action} 4 {ticker} {strike}{otype} {exp_date} @{price}"
        elif action == "STC":
            alert = f"{action} {ticker} {strike}{otype} {exp_date} @{price}"
            if 'trim' in message['content'].lower():
                alert += " trim"

            alert = format_0dte_weeklies(alert, message, False)
    return alert

def parse_hist_msg(fname, author):

    with open(fname, 'r', encoding='utf-8') as f:
        data = json.load(f)

    msgs = []
    for msg in data["messages"]:
        try:
            msg_date = datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%S.%f%z')
        except ValueError:
            msg_date = datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
        dt_in_est = msg_date.strftime('%m/%d/%Y %H:%M:%S.%f')
        msg_date_ob = datetime.strptime(dt_in_est, '%m/%d/%Y %H:%M:%S.%f')
        if author in ['demon', 'bryce', 'moustache']:
            if msg['content'].startswith("STC") and "@" not in msg['content']:
                msg['content'] += " @ 1"
            contract = format_0dte_weeklies(msg["content"].replace("@Demon alerts", ''), msg_date_ob, False)
            content = format_alert_date_price(contract)
        elif author == "kent":
            content = kent_formatting(msg)
        elif author == "sirgoldman":
            content = sirgoldman_formatting(msg)
        elif author in ["flohai_0dte", "flohai_weely"]:
            content = flohai_formatting(msg)
        elif author == "tradir":
            content = tradir_formatting(msg)
        elif author == "bishop":
            content = bishop_formatting(msg)
        elif author == "flint":
            content = flint_formatting(msg)
        elif author.startswith("moneymotive"):
            content = moneymotive_formatting(msg, msg_date_ob)
        elif author == "eclipse":
            content = eclipse_formatting(msg)
        elif author == "diesel":
            content = diesel_formatting(msg, msg_date_ob)
        elif author == "oculus":
            content = oculus_formatting(msg, msg_date_ob)
        elif author == "bear":
            content = bear_formatting(msg)
        elif author == "theta_warrior_elite":
            content = theta_warrior_elite(msg)
        elif author == "makeplays":
            content = makeplays_main_formatting(msg, msg_date_ob)
        elif author == "kingmaker":
            content = kingmaker_main_formatting(msg, msg_date_ob)
        elif author in ["em_alerts", "tpe_team", "em_challenge"]:
            content = msg["content"]
            msg["author"]["name"] = msg["author"]["name"].lower()
        elif author == "vader":
            content = msg["content"]
            msg["author"]["name"] = "vader"
        elif author == "pbt":
            content = pbt_formatting(msg)
            msg["author"]["name"] = "pbt"


        pars, order = parse_trade_alert(content)
        msgs.append([msg_date.strftime('%m/%d/%Y %H:%M:%S.%f'), msg["author"]["name"], content, pars, msg['content']])

    df = pd.DataFrame(msgs, columns=['Date', 'Author', 'Content', 'parsed', 'original'])
    return df


if __name__ == "__main__":
    author = "bear"

    if author == "demon":
        fname = '../DiscordChatExporter.Cli/demon/DemonTrading(after 2023-11-30).json'
    elif author == "bryce":
        fname = "../DiscordChatExporter.Cli/bryce/Aurora Trading _bryces-options [846415903671320598].json"
    elif author == "kent":
        fname = "../DiscordChatExporter.Cli\kent\kent.json"
    elif author == "sirgoldman":
        fname = "../DiscordChatExporter.Cli/goldman/sirgoldman.json"
    elif author == "flohai_0dte":
        fname = "../DiscordChatExporter.Cli/flowai/Floh AI  0-dte.json"
    elif author == "flohai_weely":
        fname = "../DiscordChatExporter.Cli/flowai/Floh AI weeklies.json"
    elif author == "tradir":
        fname = "../DiscordChatExporter.Cli/tradir/tradir.json"
    elif author == "moustache":
        fname = "../DiscordChatExporter.Cli/Moustache - IV - ALERTS - moustache-trades [1136097072374878299].json"
    elif author == "bishop":
        fname = "data/parsed/bishop-trades.json"
    elif author == "bear":
        fname = "data/exported/bear_trades.json"
    elif author == "oculus":
        fname = "data/exported/oculus_trades.json"

    elif author == 'bulltrades':
        fname = "data/exported/BullTrades.net_-_Alerts_-_analyst-alerts_738943464259059752.csv"
        df = pd.read_csv(fname)
        msgs = []
        for _, row in df.iterrows():
            if pd.isna(row['Content']):
                continue
            pars, order = parse_trade_alert(row['Content'])
            date_msg = datetime.strptime(row["Date"][:26], '%Y-%m-%dT%H:%M:%S.%f').strftime('%m/%d/%Y %H:%M:%S.%f')
            msgs.append([date_msg, row["Author"], row['Content'], pars])
            df = pd.DataFrame(msgs, columns=['Date', 'Author', 'Content', 'parsed'])
            fname_out = f'data/parsed/{author}_parsed.csv'
            df.to_csv(fname_out, index=False)
            exit()
    fname_out = f'data/parsed/{author}_parsed.csv'
    df = parse_hist_msg(fname, author)
    df.to_csv(fname_out, index=False)
