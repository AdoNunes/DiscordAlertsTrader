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
                qty =  max(int(500//(float(price)*100)), 1)
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

