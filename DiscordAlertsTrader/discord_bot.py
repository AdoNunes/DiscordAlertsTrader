
import os
import time
import pandas as pd
from datetime import datetime, timezone
import threading
from colorama import Fore, init
import discord # this is discord.py-self package not discord

from .message_parser import parse_trade_alert
from .configurator import cfg
from .configurator import channel_ids
from .alerts_trader import AlertsTrader
from .alerts_tracker import AlertsTracker
try:
    from .fend_bot import bot_msgs
    with_fend = True
except ImportError:
    with_fend = False


init(autoreset=True)

class dummy_queue():
    def __init__(self, maxsize=10):
        self.maxsize = maxsize
        self.queue = []

    def put(self, item):
        if len(self.queue) >= self.maxsize:
            self.queue.pop(0)
        self.queue.append(item)


class DiscordBot(discord.Client):
    def __init__(self, 
                 queue_prints=dummy_queue(maxsize=10), 
                 live_quotes=True, 
                 brokerage=None,
                 tracker_portfolio_fname=cfg['portfolio_names']["tracker_portfolio_name"]):
        super().__init__()
        self.channel_IDS = channel_ids
        self.time_strf = "%Y-%m-%d %H:%M:%S.%f"
        self.queue_prints = queue_prints
        self.bksession = brokerage
        self.live_quotes = live_quotes
        if brokerage is not None:
            self.trader = AlertsTrader(queue_prints=self.queue_prints, brokerage=brokerage)       
        self.tracker = AlertsTracker(brokerage=brokerage, portfolio_fname=tracker_portfolio_fname)
        self.load_data()        

        if live_quotes and brokerage is not None: # and brokerage.name == 'tda':
            self.thread_liveq =  threading.Thread(target=self.track_live_quotes)
            self.thread_liveq.start()

    def close_bot(self):
        if self.bksession is not None:
            self.trader.update_portfolio = False
            self.live_quotes = False

    def track_live_quotes(self):
        dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
        os.makedirs(dir_quotes, exist_ok=True)

        while self.live_quotes:
            # Skip closed market
            now = datetime.now()
            weekday, hour = now.weekday(), now.hour
            if  weekday >= 5 or (hour < 9 and hour >= 17):  
                time.sleep(60)
                continue

            # get unique symbols  from portfolios
            track_symb = set(self.tracker.portfolio.loc[self.tracker.portfolio['isOpen']==1, 'Symbol'].to_list() + \
                self.trader.portfolio.loc[self.trader.portfolio['isOpen']==1, 'Symbol'].to_list())
            # save quotes to file
            try:
                quote = self.bksession.get_quotes(track_symb)
            except Exception as e:
                print('error during live quote:', e)
                continue
            if quote is None:
                continue
            
            for q in quote: 
                if quote[q]['description'] == 'Symbol not found':
                    continue
                timestamp = quote[q]['quoteTimeInLong']//1000  # in ms
                do_header = not os.path.exists(f"{dir_quotes}/{quote[q]['symbol']}.csv")
                with open(f"{dir_quotes}/{quote[q]['symbol']}.csv", "a+") as f:
                    if do_header:
                        f.write(f"timestamp, quote\n")
                    f.write(f"{timestamp}, {quote[q]['askPrice']}\n")
            
            # Sleep for up to 5 secs    
            toc = (datetime.now() - now).total_seconds()
            if toc < 5 and self.live_quotes:
                time.sleep(5-toc)

    def load_data(self):
        self.chn_hist= {}
        self.chn_hist_fname = {}
        for ch in self.channel_IDS.keys():
            dt_fname = f"{cfg['general']['data_dir']}/{ch}_message_history.csv"
            if not os.path.exists(dt_fname):
                ch_dt = pd.DataFrame(columns=cfg['col_names']['chan_hist'].split(","))
                ch_dt.to_csv(dt_fname, index=False)
                ch_dt.to_csv(f"{cfg['general']['data_dir']}/{ch}_message_history_temp.csv", index=False)
            else:
                ch_dt = pd.read_csv(dt_fname)

            self.chn_hist_fname[ch] = dt_fname
            self.chn_hist[ch]= ch_dt

    async def on_ready(self):
        print('Logged on as', self.user , '\n loading previous messages')
        # pass channel object to trader
        # if self.bksession is not None and cfg['discord'].getboolean('notify_alerts_to_discord') and \
        #     len(cfg['discord'].get('send_alerts_to_chan')):
            # self.trader.discord_channel = await self.fetch_channel(cfg['discord'].get('send_alerts_to_chan'))
            # self.trader.discord_send = self.send_msg            
        await self.load_previous_msgs()

    async def send_msg(self, msg, channel=None):
        if channel is None:
            # channel = await self.fetch_channel(cfg['discord'].get('send_alerts_to_chan'))
            await channel.send(msg)
    
    async def on_message(self, message):
        # handle fend bot messages
        if with_fend:
            alert = bot_msgs(message)
            if alert is not None:
                self.new_msg_acts(alert, False)
                return
        # only respond to channels in config or authorwise subscription
        author = f"{message.author.name}#{message.author.discriminator}"    
        if message.channel.id not in self.channel_IDS.values() and \
            author not in cfg['discord']['auhtorwise_subscription'].split(","):
            return
        if message.content == 'ping':
            await message.channel.send('pong')
        if not len(message.content):
            return
        self.new_msg_acts(message)
        

    async def on_message_edit(self, before, after):
        # Ignore if the message is not from a user or if the bot itself edited the message
        if after.channel.id not in self.channel_IDS.values() or  before.author.bot:
            return

        str_prt = f"Message edited by {before.author}: '{before.content}' -> '{after.content}'"
        self.queue_prints.put([str_prt, "black"])
        print(Fore.BLUE + str_prt)

    async def load_previous_msgs(self):
        await self.wait_until_ready()
        for ch, ch_id in self.channel_IDS.items():
            channel = self.get_channel(ch_id)
            if channel is None:
                print("channel not found:", ch)
                continue
            
            if len(self.chn_hist[ch]):
                msg_last = self.chn_hist[ch].iloc[-1]
                date_After = datetime.strptime(msg_last.Date, self.time_strf) 
                iterator = channel.history(after=date_After, oldest_first=True)
            else:
                # iterator = channel.history(oldest_first=True)
                continue
                
            print("In", channel)
            async for message in iterator:
                self.new_msg_acts(message)
        print("Done")        
        self.tracker.close_expired()

    def new_msg_acts(self, message, from_disc=True):
        if from_disc:
            msg_date = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None)
            msg_date_f = msg_date.strftime(self.time_strf)    
            if message.channel.id in self.channel_IDS.values():
                chn_ix = list(self.channel_IDS.values()).index(message.channel.id)
                chn = list(self.channel_IDS.keys())[chn_ix]
            else:
                chn = None
            msg = pd.Series({'AuthorID': message.author.id,
                            'Author': f"{message.author.name}#{message.author.discriminator}".replace("#0", ""),
                            'Date': msg_date_f, 
                            'Content': message.content,
                            'Channel': chn
                            })
        else:
            msg = message
        chn = msg['Channel']
        shrt_date = datetime.strptime(msg["Date"], self.time_strf).strftime('%Y-%m-%d %H:%M:%S')
        self.queue_prints.put([f"\n{shrt_date} {msg['Channel']}: \n\t{msg['Author']}: {msg['Content']} ", "blue"])
        print(Fore.BLUE + f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")

        pars, order =  parse_trade_alert(msg['Content'])
        if pars is None:
            if self.chn_hist.get(chn) is not None:
                msg['Parsed'] = ""
                self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
            return
        else:
            if order['asset'] == "option":
                # get option date with year
                opt_dt = datetime.strptime(f"{order['expDate']} {datetime.now().year}" , "%m/%d %Y")
                today = datetime.now().date()
                past = opt_dt.date() < today
                if past:
                    str_msg = f"Option date in the past: {order['expDate']}"
                    self.queue_prints.put([f"\t {str_msg}", "green"])
                    print(Fore.GREEN + f"\t {str_msg}")
                    msg['Parsed'] = str_msg
                    if self.chn_hist.get(chn) is not None:
                        self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
                        self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
                    return
                
            order['Trader'], order["Date"] = msg['Author'], msg["Date"]
            order_date = datetime.strptime(order["Date"], "%Y-%m-%d %H:%M:%S.%f")
            date_diff = datetime.now() - order_date
            print(f"time difference is {date_diff.total_seconds()}")

            live_alert = True if date_diff.seconds < 90 else False
            str_msg = pars
            if live_alert and self.bksession is not None: 
                str_msg += " " + self.trader.price_now(order['Symbol'], order["action"], pflag=0)
            self.queue_prints.put([f"\t {str_msg}", "green"])
            print(Fore.GREEN + f"\t {str_msg}")
            
            track_out = self.tracker.trade_alert(order, live_alert, chn)
            self.queue_prints.put([f"{track_out}", "red"])
            if self.do_trade_alert(msg['Author'], msg['Channel']):
                order["Trader"] = msg['Author']
                if len(cfg["order_configs"]["default_trailstop"]) and order.get("SL") is None and order.get("PT1") is None:
                    order['SL'] = cfg["order_configs"]["default_trailstop"] + "%"
                self.trader.new_trade_alert(order, pars, msg['Content'])
        
        if self.chn_hist.get(chn) is not None:
            msg['Parsed'] = pars
            self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
            self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)

    def do_trade_alert(self, author, channel):
        "Decide if alert should be traded"
        if author in cfg['discord']['authors_subscribed'].split(",") and self.bksession is not None:
            return True
        elif channel in cfg['discord']['channelwise_subscription'].split(",") and self.bksession is not None:
            return True
        else:
            return False

if __name__ == '__main__':
    client = DiscordBot()
    client.run(cfg['discord']['discord_token'])



