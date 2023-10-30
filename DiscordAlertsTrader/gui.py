#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr  3 18:18:43 2021

@author: adonay
"""
import os
import os.path as op
import threading
import pandas as pd
from datetime import datetime
import time
import re
import queue
import PySimpleGUIQt as sg
from PySide2.QtWidgets import QHeaderView

from DiscordAlertsTrader.brokerages import get_brokerage
from DiscordAlertsTrader import gui_generator as gg
from DiscordAlertsTrader import gui_layouts as gl
from DiscordAlertsTrader.discord_bot import DiscordBot
from DiscordAlertsTrader.configurator import cfg, channel_ids
from DiscordAlertsTrader.message_parser import parse_trade_alert, ordersymb_to_str
# A fix for Macs
os.environ['QT_MAC_WANTS_LAYER'] = '1'


def match_authors(author_str:str)->str:
    """Author have an identifier in discord, it will try to find full author name

    Parameters
    ----------
    author_str : str
        string to match the author

    Returns
    -------
    str
        author with identifier
    """
    if "#" in author_str:
        return author_str
    authors = []
    for chn in channel_ids.keys():
        at = pd.read_csv(op.join(cfg['general']['data_dir'] , f"{chn}_message_history.csv"))["Author"].unique()
        authors.extend(at)
    authors = list(dict.fromkeys(authors))
    
    authors += cfg['discord']['authors_subscribed'].split(',')
    authors = [a for a in authors if author_str.lower() in a.lower()]
    if len(authors) == 0:
        author = author_str
    elif len(authors) > 1:
        author = author_str
    else:
        author = authors[0]
    return author

def split_alert_message(gui_msg):
    # extra comas
    if len(gui_msg.split(','))>2:
        splt = gui_msg.split(',')
        author = splt[0]
        msg = ",".join(splt[1:])
    # one coma
    elif len(gui_msg.split(','))==2:
        author, msg = gui_msg.split(',')
    # one colon
    elif len(gui_msg.split(':'))==2:
        author, msg = gui_msg.split(':')
    # extra colons
    elif len(gui_msg.split(':'))>2:
        splt = gui_msg.split(':')
        author = splt[0]
        msg = ":".join(splt[1:])
        
    # no colon or coma
    else:
        print("No colon or coma in message, author not found, assuming no author")
        author = "author"
        msg = gui_msg
    return author, msg

def get_live_quotes(symbol, tracker, max_delay=2):
    dir_quotes = cfg['general']['data_dir'] + '/live_quotes'
    
    fquote = f"{dir_quotes}/{symbol}.csv"
    if not op.exists(fquote):
        quote = tracker.price_now(symbol, "both")
        if quote is None:
            return None, None        
        return quote
    
    with open(fquote, "r") as f:
        quotes = f.readlines()
    
    now = time.time()
    get_live = False
    try:
        tmp = quotes[-1].split(',') # in s  
        if len(tmp) == 3:
            timestamp, ask, bid = tmp
        else:
            timestamp, ask = tmp
            bid = ask
        bid = bid.strip().replace('\n', '')
        quote = [ask, bid]
    except:
        print("Error reading quote", symbol, quotes[-1])
        get_live = True
    
    timestamp = eval(timestamp)
    if max_delay is not None:
        if now - timestamp > max_delay:
            get_live = True
    
    if get_live:
        quote = tracker.price_now(symbol, "both")
        if quote is None:
            return None, None        
        return quote
    return quote

def fit_table_elms(Widget_element):
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()

# sg.theme('Dark Blue 3')
sg.SetOptions(font=("Helvitica 11"))

fnt_b  ="Helvitica 11"
fnt_h  ="Helvitica 11"

ly_cons, MLINE_KEY = gl.layout_console('Discord messages from all the channels', '-MLINE-')
ly_cons_subs, MLINE_SUBS_KEY = gl.layout_console('Discord messages only from subscribed authors',
                                       '-MLINEsub-')

print(1)
gui_data = {}
gui_data['port'] = gg.get_portf_data()
ly_port = gl.layout_portfolio(gui_data['port'], fnt_b, fnt_h)

gui_data['trades'] = gg.get_tracker_data()
ly_track = gl.layout_traders(gui_data['trades'], fnt_b, fnt_h)

gui_data['stats'] = gg.get_stats_data()
ly_stats = gl.layout_stats(gui_data['stats'], fnt_b, fnt_h)
print(2)

chns = channel_ids.keys()
ly_chns = []
for chn in chns:
    chn_fname = cfg['general']['data_dir']+f"/{chn}_message_history.csv"
    if not op.exists(chn_fname):
        os.makedirs(cfg['general']['data_dir'], exist_ok=True)
        pd.DataFrame(columns=cfg["col_names"]['chan_hist'].split(',')).to_csv(chn_fname, index=False)
    gui_data[chn] = gg.get_hist_msgs(chan_name=chn)
    ly_ch = gl.layout_chan_msg(chn, gui_data[chn], fnt_b, fnt_h)
    ly_chns.append(ly_ch)

bksession = get_brokerage()
ly_accnt = gl.layout_account(bksession, fnt_b, fnt_h)
ly_conf = gl.layout_config(fnt_b, cfg)
msg_tab = [[sg.TabGroup([[sg.Tab(c, h) for c, h in zip(chns, ly_chns)],
                        ], title_color='black')]]
layout = [[sg.TabGroup([
                        [sg.Tab("Msgs Subs", ly_cons_subs, font=fnt_b)],
                        [sg.Tab("Msgs All", ly_cons, font=fnt_b)], 
                        [sg.Tab('Portfolio', ly_port)],
                        [sg.Tab('Analysts Portfolio', ly_track)],
                        [sg.Tab('Analysts Stats', ly_stats)],
                        [sg.Tab('Msg History',msg_tab)],                        
                        [sg.Tab("Account", ly_accnt)],
                        [sg.Tab("Config", ly_conf)]
                        ], title_color='black', font=fnt_b)],
        ]
layout += gl.trigger_alerts_layout()
print(3)
window = sg.Window('Discord Alerts Trader', layout,size=(100, 800), # force_toplevel=True,
                    auto_size_text=True, resizable=True)
print(4)
def mprint_queue(queue_item_list, subscribed_author=False):
    # queue_item_list = [string, text_color, background_color]
    kwargs = {}
    text = queue_item_list[0]
    len_que = len(queue_item_list)
    if len_que == 2:
        kwargs["text_color"] = queue_item_list[1]
    elif len_que == 3:
        tcol = queue_item_list[1]
        tcol = "black" if tcol == "" else tcol
        kwargs["text_color"] = tcol

        bcol = queue_item_list[2]
        bcol = "white" if bcol == "" else bcol
        kwargs["background_color"] = bcol

    window[MLINE_KEY].print(text, **kwargs)
    if subscribed_author or len_que == 3:
        window[MLINE_SUBS_KEY].print(text, **kwargs)

def update_portfolios_thread(window):
    while True:
        time.sleep(60)
        window["_upd-portfolio_"].click()
        time.sleep(2)  
        window["_upd-track_"].click()
print(5)
event, values = window.read(.1)

els = ['_portfolio_', '_track_', ] + [f"{chn}_table" for chn in chns]
els = els + ['_orders_', '_positions_'] if bksession is not None else els
for el in els:
    try:
        fit_table_elms(window.Element(el).Widget)
    except:
        pass

for chn in chns:
    table = window[f"{chn}_table"].Widget.horizontalHeader()
    table.setSectionResizeMode(2, QHeaderView.Stretch)
    window[f"{chn}_table"].Widget.scrollToBottom()

print(6)
event, values = window.read(.1)
print(7)
trade_events = queue.Queue(maxsize=20)
alistner = DiscordBot(trade_events, brokerage=bksession, cfg=cfg)
print(8)
threading.Thread(target=update_portfolios_thread, args=(window,), daemon=True).start()
print(9)
event, values = window.read(.1)

# exclusion filters for the portfolio and analysts tabs
port_exc = {"Closed":False,
            "Open":False,
            "NegPnL":False,
            "PosPnL":False,
            "live PnL":False,
            "stocks":True,
            "options":False,
            'bto':False,
            "stc":False,
            }
track_exc = port_exc.copy()
stat_exc = port_exc.copy()
port_exc["Canceled"] = True
port_exc["Rejected"] = False

print(10)
dt, _  = gg.get_tracker_data(track_exc, **values)
window.Element('_track_').Update(values=dt)
fit_table_elms(window.Element("_track_").Widget)
dt, hdr = gg.get_portf_data(port_exc)
window.Element('_portfolio_').Update(values=dt)
fit_table_elms(window.Element("_portfolio_").Widget)
dt, hdr = gg.get_stats_data(stat_exc)
window.Element('_stat_').Update(values=dt)
fit_table_elms(window.Element("_stat_").Widget)


def run_gui():  
    subs_auth_msg = False
    auth_subs = cfg['discord']['authors_subscribed'].split(',')
    auth_subs = [i.split("#")[0].strip() for i in auth_subs]
    ori_color = 'black'
    while True: 
        event, values = window.read(1)#.1)

        if event == sg.WINDOW_CLOSED:
            break

        # Prefill trigger alert message
        if ('_portfolio_' in event and values['_portfolio_'] != []) or \
            ('_track_' in event and values['_track_'] != []):  
            if '_portfolio_' in event:
                pix = values['_portfolio_'][0] 
                dt, hdr = gg.get_portf_data(port_exc, **values)
                qty = dt[pix][hdr.index('filledQty')]
            else:
                pix = values['_track_'][0]
                dt, hdr = gg.get_tracker_data(track_exc, **values)
                qty = dt[pix][hdr.index('Qty')]  
            qty = qty if qty == "" else int(qty)            
            symb = dt[pix][hdr.index('Symbol')]
            auth = match_authors(dt[pix][hdr.index('Trader')])
            
            price = ""
            if "Live" in hdr:
                price = dt[pix][hdr.index('Live')]
            if price == "":
                price = dt[pix][hdr.index('S-Price-actual')]
            if price == "":
                price = dt[pix][hdr.index('S-Price')]
            price = price if price == "" else float(price)
            if "_" in symb:
                # option
                exp = r"(\w+)_(\d{6})([CP])([\d.]+)"        
                match = re.search(exp, symb, re.IGNORECASE)
                if match:
                    symbol, date, type, strike = match.groups()
                    symb_str = f"{auth}, STC {qty} {symbol} {strike}{type} {date[:2]}/{date[2:4]} @{price}"
            else:
                symb_str= f"{auth}, STC {qty} {symb} @{price}"
            window.Element("-subm-msg").Update(value=symb_str)
        # handle alert buttons
        elif event == '-toggle':
            state = window[event].GetText()
            butts = ['-alert_to-', '-alert_BTO', '-alert_STC', '-alert_STO', '-alert_BTC', '-alert_exitupdate', 'alert_quotes']
            if state == '▲':
                window[event].update(text='▼')            
            else:
                window[event].update(text='▲')
            for el in butts:
                window[el].update(visible=state == '▲')
                
        elif event.startswith('-alert_' ):
            print(event)
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()            

            action = event.split('_')[1]
            
            msg_split = split_alert_message(values['-subm-msg'])
            if len(msg_split) == 2:
                author, alert = msg_split
            else:
                author, alert = "author", msg_split[0]
            # fix missing price, none price, no action
            if "@" not in alert:
                alert += " @0.01"
            if  not len([p for p in ["BTO", "STO", "BTC", "STC"] if p in alert]):
                alert = "BTO " + alert                
            alert = alert.replace("@None", "@0.01").replace("@m", "@0.01")
            _, order = parse_trade_alert(alert)

            if order is None:
                window.Element(event).Update(button_color=ori_col)
                continue
            
            ask, bid = get_live_quotes(order['Symbol'], alistner.tracker)
            if action in ["BTO", "BTC"] or order['action'] in ["BTO", "BTC"]:
                price = ask
            elif action in ["STO", "STC"] or order['action'] in ["STO", "STC"]:
                price = bid
            else:
                price = ask
            if price is None:
                price = order.get('price', 0.01)
            symbol = ordersymb_to_str(order['Symbol'])
            if action =='exitupdate':
                msg =  f"{author}, Exit Update {symbol} PT 50% SL 50%"
            elif action == 'quotes': 
                action_msg = order['action'].replace('ExitUpdate', "BTO")
                msg =  f"{author}, {action_msg} {order.get('Qty', 1)} {symbol} @{price} | [ask {ask} bid {bid}]" 
            else:
                msg =  f"{author}, {action} {order.get('Qty', 1)} {symbol} @{price}" 
                
            window.Element("-subm-msg").Update(value=msg)
            window.Element(event).Update(button_color=ori_col)
            
        elif event == "_upd-portfolio_": # update button in portfolio
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            dt, _ = gg.get_portf_data(port_exc, **values)
            window.Element('_portfolio_').Update(values=dt)
            fit_table_elms(window.Element("_portfolio_").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event == '-slider-':
            font_string = 'Helvitica '
            font_string += str(int(values['-slider-']))
            # window.Element('_portfolio_').Update(font=font_string)
            sg.SetOptions(font=(font_string))
            
        elif event == "cfg_button":
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            for k, v in values.items():
                if k.startswith("cfg"):
                    if isinstance(window[k], sg.Checkbox):
                        continue
                    if window.Element(k).TextColor == 'red':
                        window.Element(k).Update(text_color=ori_color)
                    f1,f2 = k.replace("cfg_", "").split(".")
                    cfg[f1][f2] = str(v)
            window.Element(event).Update(button_color=ori_col)

        elif event.startswith("cfg"):
            print(event)
            if isinstance(window[event], sg.Checkbox):
                f1,f2 = event.replace("cfg_", "").split(".")
                print("before", cfg[f1][f2])
                cfg[f1][f2] = str(values[event])
                print("after", cfg[f1][f2])
            else:
                cur_color = window.Element(event).TextColor
                if cur_color != "red":
                    ori_color = cur_color
                window.Element(event).Update(text_color="red")
            
        elif event == "_upd-track_": # update button in analyst alerts
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            dt, _  = gg.get_tracker_data(track_exc, **values)
            window.Element('_track_').Update(values=dt)
            fit_table_elms(window.Element("_track_").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event == "_upd-stat_": # update button in analyst stats
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            dt, _  = gg.get_stats_data(stat_exc, **values)
            window.Element('_stat_').Update(values=dt)
            fit_table_elms(window.Element("_stat_").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event.startswith("-port-"): # radial click, update portfolio
            key =  event.replace("-port-", "")
            state = window.Element(event).get()
            port_exc[key] = state
            dt, _ = gg.get_portf_data(port_exc, **values)
            window.Element('_portfolio_').Update(values=dt)

        elif event.startswith("-track-"): # radial click, update analyst alerts
            key =  event.replace("-track-", "")
            state = window.Element(event).get()
            track_exc[key] = state
            dt, _ = gg.get_tracker_data(track_exc, **values)
            window.Element('_track_').Update(values=dt)

        elif event.startswith("-stat-"): # radial click, update analyst stats
            key =  event.replace("-stat-", "")
            state = window.Element(event).get()
            stat_exc[key] = state
            dt, _ = gg.get_stats_data(stat_exc, **values)
            window.Element('_stat_').Update(values=dt)

        elif event[-3:] == "UPD":
            chn = event[:-4]
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()

            args = {}
            for k, v in values.items():
                if k[:len(chn)] == chn:
                    args[k[len(chn)+1:]] = v
            dt, _  = gg.get_hist_msgs(chan_name=chn, **args)
            window.Element(f"{chn}_table").Update(values=dt)

            fit_table_elms(window.Element(f"{chn}_table").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event == 'acc_updt':
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()
            gl.update_acct_ly(bksession, window)
            fit_table_elms(window.Element(f"_positions_").Widget)
            fit_table_elms(window.Element(f"_orders_").Widget)
            window.Element(event).Update(button_color=ori_col)

        elif event == "-subm-alert":
            ori_col = window.Element(event).ButtonColor
            window.Element(event).Update(button_color=("black", "white"))
            window.refresh()    
            try:        
                author,msg = split_alert_message(values['-subm-msg'])
                author = match_authors(author.strip())
                msg = msg.strip().replace("SPXW", "SPX")
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                chan = "GUI_" + values["_chan_trigg_"]
                print(chan)
                new_msg = pd.Series({
                    'AuthorID': None,
                    'Author': author,
                    'Date': date, 
                    'Content': msg,
                    'Channel': chan
                    })
                alistner.new_msg_acts(new_msg, from_disc=False)
                window.Element(event).Update(button_color=ori_col)
            except Exception as e:
                print("Trigger alerts with error:", e)
                window.Element(event).Update(button_color=ori_col)
                continue

        try:
            event_feedb = trade_events.get(False)
            # if message from subscribed author or channel flag it to print in both consoles
            if event_feedb[1] == "blue":
                author = event_feedb[0].split("\n\t")[1].split(":")[0]
                chan = event_feedb[0].split(": \n\t")[0].split(" ")[-1]
                if any(a == author for a in auth_subs):
                    subs_auth_msg = True
                elif cfg['discord']['channelwise_subscription'].split(",") != [""] and \
                    any([c.strip() == chan for c in cfg['discord']['channelwise_subscription'].split(",")]):
                    subs_auth_msg = True
                elif cfg['discord']['auhtorwise_subscription'].split(",") != [""] and \
                    any([c.strip() == author for c in cfg['discord']['auhtorwise_subscription'].split(",")]):
                    subs_auth_msg = True
                else:
                    subs_auth_msg = False
            
            mprint_queue(event_feedb, subs_auth_msg)
        except queue.Empty:
            pass


def run_client():
    if len(cfg['discord']['discord_token']) < 50:
        str_prt = "Discord token not provided, no discord messages will be received. Add user token in config.ini"
        print(str_prt)
        time.sleep(3)
        trade_events.put([str_prt,"", "red"])
        return
    alistner.run(cfg['discord']['discord_token'])


def gui():   
    client_thread = threading.Thread(target=run_client, daemon=True)

    # start the threads
    client_thread.start()
    run_gui()

    # close the GUI window
    window.close()
    alistner.close_bot()
    exit()


if __name__ == '__main__':
    gui()
