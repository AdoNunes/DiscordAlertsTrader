
import os
import time
import pandas as pd
from datetime import datetime, timezone
import threading
from colorama import Fore, Back, Style, init
import discord # this is discord.py-self package not discord

from .message_parser import parser_alerts
from .configurator import cfg
from .configurator import channel_ids
from .alerts_trader import AlertsTrader
from .alerts_tracker import AlertsTracker




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
    def __init__(self, queue_prints=dummy_queue(maxsize=10), live_quotes=True, brokerage=None):
        super().__init__()
        self.channel_IDS = channel_ids
        self.time_strf = "%Y-%m-%d %H:%M:%S.%f"
        self.queue_prints = queue_prints
        self.bksession = brokerage
        self.live_quotes = live_quotes
        if brokerage is not None:
            self.trader = AlertsTrader(queue_prints=self.queue_prints, brokerage=brokerage)       
        self.tracker = AlertsTracker(brokerage=brokerage)
        self.load_data()        

        if live_quotes and brokerage is not None:
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
            except ConnectionError as e:
                print('error during live quote:', e)
            
            for q in quote: 
                if quote[q]['description'] == 'Symbol not found':
                    continue
                timestamp = quote[q]['quoteTimeInLong']//1000  # in ms
                do_header = not os.path.exists(f"{dir_quotes}/{quote[q]['symbol']}.csv")
                with open(f"{dir_quotes}/{quote[q]['symbol']}.csv", "a+") as f:
                    if do_header:
                        f.write(f"timestamp, quote\n")
                    f.write(f"{timestamp}, {quote[q]['bidPrice']}\n")
            
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
        await self.load_previous_msgs()

    async def on_message(self, message):
        # only respond to channels in config        
        if message.channel.id not in self.channel_IDS.values():
            # print('not in cfg', message)
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
        self.queue_prints.put([str_prt, "blue"])
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
                            'Author': f"{message.author.name}#{message.author.discriminator}",
                            'Date': msg_date_f, 
                            'Content': message.content,
                            'Channel': chn
                            })
        else:
            msg = message

        shrt_date = datetime.strptime(msg["Date"], self.time_strf).strftime('%Y-%m-%d %H:%M:%S')
        self.queue_prints.put([f"{shrt_date} \t {msg['Author']}: {msg['Content']} ", "blue"])
        print(Fore.BLUE + f"{shrt_date} \t {msg['Author']}: {msg['Content']} ")

        pars, order =  parser_alerts(msg['Content'])
        if pars is None and self.chn_hist.get(chn) is not None:
            msg['Parsed'] = ""
            self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
            self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)
            return
        else:
            order['Trader'], order["Date"] = msg['Author'], msg["Date"]
            order_date = datetime.strptime(order["Date"], "%Y-%m-%d %H:%M:%S.%f")
            date_diff = datetime.now() - order_date
            print(f"time difference is {date_diff.total_seconds()}")

            live_alert = True if date_diff.seconds < 90 else False
            str_msg = pars
            if live_alert and self.bksession is not None: 
                str_msg += " " + self.trader.price_now(order['Symbol'], order["action"], pflag=0)
            self.queue_prints.put([f"\t \t {str_msg}", "green"])
            print(Fore.GREEN + f"\t \t {str_msg}")
            
            track_out = self.tracker.trade_alert(order, live_alert, chn)
            self.queue_prints.put([f"\t \t tracker log: {track_out}", "red"])
            if msg['Author'] in cfg['discord']['authors_subscribed'] and  self.bksession is not None:
                order["Trader"] = msg['Author']
                if len(cfg["order_configs"]["default_trailstop"]):
                    order['SL'] = cfg["order_configs"]["default_trailstop"] + "%"
                self.trader.new_trade_alert(order, pars, msg['Content'])
        
        if self.chn_hist.get(chn) is not None:
            msg['Parsed'] = pars
            self.chn_hist[chn] = pd.concat([self.chn_hist[chn], msg.to_frame().transpose()],axis=0, ignore_index=True)
            self.chn_hist[chn].to_csv(self.chn_hist_fname[chn], index=False)



if __name__ == '__main__':
    client = DiscordBot()
    client.run(cfg['discord']['discord_token'])



