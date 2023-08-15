import re
from datetime import datetime

def server_formatting(message):
    """Format server messages to standard alert format"""
    if message.guild.id == 542224582317441034:
        message = xtrades_formatting(message)
    elif message.guild.id == 836435995854897193:
        message = tradeproelite_formatting(message)
        
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

xtrades_msg_examples = [
    'STC GOOGL Aug 11 2023 $131.00 Call @ 1.29 (from: $1.37)',
    ':white_check_mark: Short NVDA Aug 4 2023 $452.50 Call @ $0.81  |  market : $0.85',
    ':whitecheckmark: Short NVDA Aug 4 2023 $452.50 Call @ $0.81  |  market : $0.85',
    ':whitecheckmark: Short NVDA Aug 4 2023 $452.50 Call @ $0.81  |  market : $0.85',
    ':whitecheckmark: Long SQ @ 65.53  |  current : $65.53',
    ':whitecheckmark: Closed RETO @ 2.32 *(from 1.94)*  |  current : $2.32',
    ':whitecheckmark: Long CXAI @ 8  |  current : $8.03',
    ]

# message.embeds[0].author.name 
# 'entered long', 
# 'averaged long
# 'added an update from the web platform.'

# 'STOPPED OUT:'
# 'STOPPED IN PROFIT:'
# 'entered short'
# 'covered short from the web platform.'

# message.embeds[0].title
# ':white_check_mark: Long QQQ Aug 18 2023 $365.00 Call @ 2.97  |  market : $2.97'
# ':white_check_mark: Closed QQQ Aug 18 2023 $365.00 Call @ 4.97 (from $2.97)  |  market : $2.97'
# ':white_check_mark: Short QQQ Aug 18 2023 $365.00 Put @ 2.97  |  market : $2.97'
# ':white_check_mark: Covered QQQ Aug 18 2023 $365.00 Put @ 4.97 (from $2.97)  |  market : $2.97'
# ':white_check_mark: Covered 0 Sep 18 2023 $365.00 Call @ 1.97 (from $2.67)  |  market : $2.67'

# 'STC CRM Sep 18 2023 $365.00 Call @ 1.97 (from $2.67)'

# 'Average accepted @ $0.12'
# # message.embeds[0].fields[0].name
# 'Risk'
# 'Standard'
# 'Lotto'

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