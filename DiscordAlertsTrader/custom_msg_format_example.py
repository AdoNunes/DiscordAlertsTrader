import re
from datetime import timezone
import pandas as pd



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
        
        avg_trade_val = 5000
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