import re
from datetime import timezone
import pandas as pd
from DiscordAlertsTrader.message_parser import parse_trade_alert


def msg_custom_formated(message):
    "Example of custom message format, adds exits to BTOs, qty for SPX trades, closes BTOs for tracker"
    time_strf = "%Y-%m-%d %H:%M:%S.%f"
    # only for bryce channel
    if message.channel.id == 1093340247057772654:
        # change time to local as it will be sent as a dict
        msg_date = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None)
        msg_date_f = msg_date.strftime(time_strf)    

        alert = message.content
        price = re.search(r"@ ([\d.]+)", alert)
        if price is not None:
            price =  price.group(1)
        if "BTO SPX" in alert:
            if price is not None:
                qty =  max(int(800//(float(price)*100)), 1)
                alert.replace("BTO", f"BTO {qty}")
            alert += r" PT 20% SL 50% invTSbuy 20%"
        elif "BTO QQQ" in alert:
            alert += r" PT 50%TS35% SL 20% invTSbuy 5%"
            
        msg = pd.Series({'AuthorID': message.author.id,
                'Author': "Bryce000",
                'Date': msg_date_f, 
                'Content': alert,
                'Channel': "options-bryce"
                    })
        
        # Make stc so new BTO will get registered
        msg2 = msg.copy()
        msg2['Content'] = msg2['Content'].replace("BTO", "STC")
        msg['Channel'] =  "GUI_analysts"
        
        return [msg, msg2]
    
    # Enhanced, scale qty
    elif message.channel.id == 1126325195301462117:
        
        avg_trade_val = 24000
        user_trade_val = 500
        ratio = user_trade_val/avg_trade_val
        
        # get qty
        pattern = r"(BTO|STC) (\d+)"
        match = re.search(pattern, message.content)
        if match is not None:
            action = match.group(1)
            qty = int(match.group(2))
            new_qty = max(int(qty*ratio), 1)
            alert =  message.content.replace(match.group(0), f"{action} {new_qty}")
        else:
            alert =  message.content

        msg = pd.Series({'AuthorID': message.author.id,
                'Author': message.author.name,
                'Date': message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None), 
                'Content': alert,
                'Channel': message.channel.name
                    })
        return [msg]
    
    # change strike format of the alert example
    elif message.channel.id == 993892865554542820:
        
        msg_date = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None)
        msg_date_f = msg_date.strftime(time_strf) 
        author = message.author.name
        alert = message.content
        if len(alert) > 0:
            _, order = parse_trade_alert(alert.replace("@bid", "@1"))
            alert = f"{order['action']} {order['Symbol'].split('_')[0]} {int(float(order['strike'][:-1]))}{order['strike'][-1]} {order['expDate']} @{order['price']}"
        
            
        msg = pd.Series({'AuthorID': 0,
            'Author': author,
            'Date': msg_date_f, 
            'Content': alert,
            'Channel': "roybot"
            })
        return [msg]