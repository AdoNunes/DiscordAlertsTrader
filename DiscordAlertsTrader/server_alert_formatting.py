import re
from datetime import datetime, timedelta

def server_formatting(message):
    """Format server messages to standard alert format"""
    if message.guild.id == 542224582317441034:
        message = xtrades_formatting(message)
    elif message.guild.id == 836435995854897193:
        message = tradeproelite_formatting(message)
    elif message.guild.id == 826258453391081524:
        message = aurora_trading_formatting(message)

    return message


def tradeproelite_formatting(message_):
    """
    Reformat Discord message from TPE to change generate alerts bot to author
    TPE guild id: 836435995854897193
    """
    # Don't do anything if not Xtrade message
    if message_.guild.id != 836435995854897193:
        return message_
    
    # Change bot to author
    if message_.author.name == 'EnhancedMarket':
        message = MessageCopy(message_)
        message.author.name = 'enhancedmarket'
        message.author.discriminator = '0'
        return message
    
    return message_


def xtrades_formatting(message_):
    """
    Reformat Discord message from Xtrades to a sandard alert format
    Xtrades guild id: 542224582317441034
    """
    # Don't do anything if not Xtrade message
    if message_.guild.id != 542224582317441034:
        return message_
    
    # return None if not Xtrade bot
    if message_.author.name != 'Xcapture':
        message_.content = message_.content.replace('BTO', 'BTO_msg').replace('STC', 'STC_msg')\
            .replace('STO', 'STO_msg').replace('BTC', 'BTC_msg')
        return message_
    
    message = MessageCopy(message_)
    
    # get action and author
    actions = {
        'entered long': 'BTO',
        'entered long from the web platform.': 'BTO',
        'averaged long': 'BTO_avg',
        'added an update from the web platform.': 'exitupdate',
        'STOPPED OUT:': 'STC',
        'STOPPED IN PROFIT:': 'STC',
        'closed long from the web platform.': "STC",
        'closed long': "STC",
        'entered short': 'STO',        
        "entered short from the web platform.": "STO",
        'covered short from the web platform.': 'BTC',
        "covered short": "BTC",
    }
    author_name = message.embeds[0].author.name
    if author_name is None:
        return message
    for action_str, action_code in actions.items():
        if action_str in author_name:
            action = action_code
            pattern = re.compile(f"(.+?) {action_str}")
            match = pattern.match(author_name)
            if match:
                author = match.group(1)
                message.author.name = author
                message.author.discriminator = "0"
                message.author.bot = False
                break
    else:
        print('ERROR: unknown action')
        print(message.embeds[0].author.name)
        return message

    # format alert
    if action in ["BTO", "STC", "STO", "BTC"]:        
        pattern = re.compile(r'(?:\:\S+ )?(\w+) (\w+)(?: (\w+ \d+ \d+) \$?(\d+\.\d+) (\w+))? @ \$?(\d+(?:\.\d+)?)', re.IGNORECASE)
        msg = message.embeds[0].title.replace("**","").replace("_","")
        match = pattern.match(msg)
        if match:
            direction, stock, expiration_date, strike, option_type, price = match.groups()          
            
            market_pattern = re.compile(r'(?:market|current) : \$(\d+(?:\.\d+)?)')
            match = market_pattern.search(msg)
            if match:
                price = match.group(1)
            else:
                price = f"{price} (alert price)"
            
            if strike is not None:
                expiration_date = datetime.strptime(expiration_date, '%b %d %Y').strftime('%m/%d/%y')
                alert = f"{action} {stock} {strike.replace('.00', '')}{option_type[0]} {expiration_date} @{price}"
            else:
                alert = f"{action} {stock} @{price}"
            
            # add SL and TP and other fields
            for mb in message.embeds:
                for fld in mb.fields:
                    if hasattr(fld, 'value'):
                        alert += f" | {fld.name}: {fld.value}"
            descp = message.embeds[0].description.split("[VIEW DETAILS]")[0].replace('\r\n', ' ')
            alert += f" | {descp}"
            
            message.content = alert
            return message
        print("no match", msg)
    else:
        alert = ""        
        # add Sl and TP and other fields
        for mb in message.embeds:
            for fld in mb.fields:
                if hasattr(fld, 'value'):
                    alert += f" | {fld.name}: {fld.value}"
        descp = message.embeds[0].description.split("[VIEW DETAILS]")[0].replace('\r\n', ' ')
        alert += f" | {descp}" 
        message.content = alert
        return message

def aurora_trading_formatting(message_):
    """
    Reformat Discord message from aurora_trading to content message
    """
    
    def format_0dte_weeklies(contract, message):
        if "0DTE" in contract:
            msg_date = message.created_at.strftime('%m/%d')
            contract = contract.replace("0DTE", msg_date).split(" @")[0]
        elif "Weeklies" in contract:
            msg_date= message.created_at
            days_until_friday = (4 - msg_date.weekday() + 7) % 7
            msg_date += timedelta(days=days_until_friday)
            msg_date = msg_date.strftime('%m/%d')
            contract = contract.replace("Weeklies", msg_date).split(" @")[0]
        return contract
    
    def format_alert(alert):
        pattern = r'\b(BTO|STC)\b\s*(\d+)?\s*([A-Z]+)\s*(\d{1,2}\/\d{1,2})?(?:\/202\d|\/2\d)?(?:C|P)?\s*(\d+[.\d+]*[cp]?)?(?:\s*@\s*[$]*[ ]*(\d+(?:[,.]\d+)?|\.\d+))?'
        match = re.search(pattern, alert, re.IGNORECASE)
        if match:
            action, quantity, ticker, expDate, strike, price = match.groups()

            asset_type = 'option' if strike and expDate else 'stock'
            symbol =  ticker.upper()
            price =  f" @ {float(price.replace(',', '.'))}" if price else ""
        
            if asset_type == 'option':
                # fix missing strike, assume Call            
                if "c" not in strike.lower() and "p" not in strike.lower():
                    strike = strike + "c"
                alert = f"{action.upper()} {symbol} {strike.upper()} {expDate}{price}"
            elif asset_type == 'stock':
                alert = f"{action.upper()} {symbol}{price}"
        return alert
    
    # Don't do anything if not server message
    if message_.guild.id != 826258453391081524:
        return message_
    
    message = MessageCopy(message_)
    # format Bryce trades
    if message_.channel.id == 846415903671320598:   
        message.content = format_alert(message.content)
    # format ace trades
    elif message_.channel.id == 885627509121618010:
        alert = ""
        for mb in message.embeds:
            if mb.title == 'Options Entry':
                description = mb.description
                # Extract the required information using regex
                contract_match = re.search(r'\*\*\[🎟️\] Contract:\*\* __([^_]+)__', description)
                fill_match = re.search(r'\*\*\[🍉\] My Fill:\*\* ([\d.]+)', description)
                risk_match = re.search(r'\*\*\[🚨\]  Risk:\*\* ([\d/]+)', description)
                extra_info_match = re.search(r'\*\*\[🗨️\] Comment:\*\* ([^\n]+)', description)
                
                if contract_match:
                    contract = contract_match.group(1).strip().replace(" - ", " ")
                    # Check for 0DTE and replace with today's date
                    contract = format_0dte_weeklies(contract, message)
                    contract = format_alert(contract)                    
                    alert += f"{contract}"
                if fill_match :
                    fill = fill_match.group(1).strip()
                    alert += f" @{fill}"
                if risk_match:
                    risk = risk_match.group(1).strip()
                    alert += f" risk: {risk}"
                if extra_info_match:
                    extra_info = extra_info_match.group(1).strip()
                    alert += f" | comment: {extra_info}"
            elif mb.title in ["Options Close", 'Options Scale']:
                description = mb.description
                # Extract the required information using regex
                contract_match = re.search(r'\*\*\[🎟️\] Contract:\*\* __([^_]+)__', description)
                fill_match = re.search(r'\*\*\[✂️] Scaling Price:\*\* ([\d.]+)', description)
                extra_info_match = re.search(r'\*\*\[🗨️\] Comment:\*\* ([^\n]+)', description)
                
                if contract_match:
                    contract = contract_match.group(1).strip().replace(" - ", " ")
                    # Check for 0DTE and weeklies
                    contract = format_0dte_weeklies(contract, message)
                    contract = format_alert(contract) 
                    alert += f"{contract}"
                if fill_match :
                    fill = fill_match.group(1).strip()
                    alert += f" @{fill}"
                if extra_info_match:
                    extra_info = extra_info_match.group(1).strip()
                    alert += f" | comment: {extra_info}"
                if mb.title == 'Options Scale':
                    alert += " | partial scale"
                
            elif mb.description:
                alert += f"(not parsed) {mb.description}"
        if len(alert):  
            message.content = alert

    return message


class MessageCopy:
    def __init__(self, original_message):
        self.created_at = original_message.created_at
        self.channel = ChannelCopy(original_message.channel)
        self.author = AuthorCopy(original_message.author)
        self.guild = GuildCopy(original_message.guild)
        self.embeds = [EmbedCopy(embed) for embed in original_message.embeds]
        self.content = original_message.content

class AuthorCopy:
    def __init__(self, original_author):
        self.name = original_author.name
        self.discriminator = original_author.discriminator
        self.id = original_author.id
        self.bot =  original_author.bot

class ChannelCopy:
    def __init__(self, original_channel):
        self.id = original_channel.id

class GuildCopy:
    def __init__(self, original_guild):
        self.id = original_guild.id

class EmbedFieldCopy:
    def __init__(self, original_field):
        self.name = original_field.name
        self.value = original_field.value

class EmbedCopy:
    def __init__(self, original_embed):
        self.author = AuthorCopy(original_embed.author)
        self.title = original_embed.title
        self.description = original_embed.description
        self.fields = [EmbedFieldCopy(field) for field in original_embed.fields]