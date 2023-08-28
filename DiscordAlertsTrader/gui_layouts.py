#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 27 11:54:36 2021

@author: adonay
"""

import PySimpleGUIQt as sg
from . import gui_generator as gg


tip = "coma separed patterns, e.g. string1,string2"
tlp_date = "Date can be:\n-a date mm/dd/yyyy, mm/dd\n-a period: today, yesterday, week, biweek, month, mtd, ytd"

def layout_console(ttl='Discord messages from subscribed channels', 
                   key='-MLINE-__WRITE ONLY__'):
    layout = [[sg.Text(ttl, size=(100,1))],
              [sg.Multiline(size=(1200,None), key=key, autoscroll=True, enable_events=False),sg.Stretch()]]
    return layout, key

def trigger_alerts_layout():
    tp_chan = "Select portfolios to trigger alert.\'nuser' for your portfolio only. Will bypass false do_BTO and do_BTC and make the trade \n" +\
                "'analysts' for the alerts tracker,\n'all' for both"
    tp_trig = "Click portfolio row number to prefill the STC alert. Alerts can look like\n" +\
                "BTO: Author#1234, BTO 1 AAA 115C 05/30 @2.5 PT 3.5TS30% PT2 4 SL TS40%, '%' for percentage, TS for Trailing Stop\n" +\
                "STC: Author#1234, STC 1 AAA 115C 05/30 @3\n" +\
                "STO: Author#1234, STC 1 AAA 115C 05/30 @2.5 PT 40% SL 50% \n" +\
                "BTC: Author#1234, STC 1 AAA 115C 05/30 @2 \n" +\
                "Exit Update: Author#1234, exit update AAA 115C 05/30 PT 80% SL 2\n"
    lay = [[
           sg.Text('to portfolio:', tooltip=tp_chan),
           sg.Combo(['both', 'user', 'analysts'], default_value='analysts', key="_chan_trigg_",tooltip=tp_chan, readonly=True, size=(15,1)),
           
           sg.Button('▲', key='-toggle',   enable_events=True, 
                                 tooltip='Show/hide change alert action'),
            sg.Input(default_text="Author#1234, STC 1 AAA 115C 05/30 @2.5 [click portfolio row number to prefill]",
                    size= (100,1), key="-subm-msg",
                    tooltip=tp_trig),
           sg.Button("Trigger alert", key="-subm-alert", 
                     tooltip="Will generate alert in user or/and analysts portfolio, useful to close or open a position", size= (20,1)),
           sg.Stretch()], 
           [sg.Text('                   Change alert to:', key='-alert_to-', tooltip="Change  current alert in tigger alert", visible=False),
            sg.Button("BTO", key='-alert_BTO', size=(10,1), tooltip="Once clicked portfolio row change prefilled STC to BTO", visible=False),
            sg.Button("STC", key='-alert_STC', size=(10,1), tooltip="Once clicked portfolio row change prefilled to STC", visible=False),
            sg.Button("STO", key='-alert_STO', size=(10,1), tooltip="Once clicked portfolio row change prefilled STC to BTO", visible=False),
            sg.Button("BTC", key='-alert_BTC', size=(10,1), tooltip="Once clicked portfolio row change prefilled to STC", visible=False),
            sg.Button("ExitUpdate", key='-alert_exitupdate', size=(20,1), tooltip="Once clicked portfolio row change prefilled STC to exit update", visible=False),
            sg.Stretch()
           ]
           ]
    return lay

def layout_portfolio(data_n_headers, font_body, font_header):
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
         [sg.Column([[
            sg.Text('Include:  Authors: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'port_filt_author',tooltip=tip),
            sg.Text('Date from: ', tooltip=tlp_date), sg.Input(key=f'port_filt_date_frm', default_text='week', tooltip=tlp_date),
            sg.Text(' To: ', tooltip=tlp_date), sg.Input(key=f'port_filt_date_to', tooltip=tlp_date),
            sg.Text(' Symbols: ', tooltip=tip), sg.Input(key=f'port_filt_sym', tooltip=tip),
            sg.Text(' Channels: ',tooltip=tip), sg.Input(key=f'port_filt_chn',tooltip=tip)
            ],                                        
            [sg.Text("Exclude: |"),
            sg.Checkbox("Closed", key="-port-Closed", enable_events=True),
            sg.Checkbox("Open", key="-port-Open", enable_events=True),
            sg.Checkbox("Cancelled", key="-port-Cancelled", default=True, enable_events=True),
            sg.Checkbox("Neg PnL", key="-port-NegPnL", enable_events=True),
            sg.Checkbox("Pos PnL", key="-port-PosPnL", enable_events=True),
            sg.Checkbox("Live PnL", key="-port-live PnL", enable_events=True),
            sg.Checkbox("Stocks", key="-port-stocks", default=True, enable_events=True),
            sg.Checkbox("Options", key="-port-options", enable_events=True),
            sg.Text('| Authors: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'port_exc_author', tooltip=tip),
            sg.Text('Channels: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'port_exc_chn',tooltip=tip),
            ],
            [sg.ReadButton("Update", button_color=('white', 'black'),bind_return_key=True, key="_upd-portfolio_")]])],
         [sg.Column([[sg.Table(values=values,
                        headings=data_n_headers[1],
                        display_row_numbers=True,
                        auto_size_columns=True,
                        header_font=font_header,
                        text_color='black',
                        font=font_body,
                        justification='left',
                        alternating_row_color='grey',
                        # num_rows=30, #len(data_n_headers[0]),
                        enable_events=True,
                        key='_portfolio_'), sg.Stretch()]])]
         ]
    return layout


def layout_traders(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [[
        sg.Column([
            [
            sg.Text('Include:  Authors: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'track_filt_author',tooltip=tip),
            sg.Text('Date from: ', tooltip=tlp_date), 
            sg.Input(key=f'track_filt_date_frm', default_text='week', tooltip=tlp_date),
            sg.Text(' To: ', tooltip=tlp_date), sg.Input(key=f'track_filt_date_to', tooltip=tlp_date),
            sg.Text(' Symbols: ',tooltip=tip), sg.Input(key=f'track_filt_sym',tooltip=tip),
            sg.Text(' Channels: ',tooltip=tip), sg.Input(key=f'track_filt_chn',tooltip=tip)
            ],[ 
            sg.Text("Exclude: |"),
            sg.Checkbox("Closed", key="-track-Closed", enable_events=True),
            sg.Checkbox("Open", key="-track-Open", enable_events=True),
            sg.Checkbox("Neg PnL", key="-track-NegPnL", enable_events=True),
            sg.Checkbox("Pos PnL", key="-track-PosPnL", enable_events=True),
            sg.Checkbox("Live PnL", key="-track-live PnL", enable_events=True), 
            sg.Checkbox("Stocks", key="-track-stocks", default=True, enable_events=True),
            sg.Checkbox("Options", key="-track-options", enable_events=True),
            sg.Text('| Authors: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'track_exc_author', tooltip=tip),
            sg.Text('Channels: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'track_exc_chn',tooltip=tip),
            ],[sg.ReadButton("Update", button_color=('white', 'black'),bind_return_key=True, key="_upd-track_")]
            ])],
         [sg.Column([
            [
            sg.Table(values=values,
                headings=data_n_headers[1],
                display_row_numbers=True,
                auto_size_columns=True,
                header_font=font_header,
                text_color='black',
                font=font_body,
                justification='left',
                alternating_row_color='grey',
                enable_events=True,
                # num_rows=30, #len(data_n_headers[0]),
                key='_track_'), sg.Stretch()]])]
         ]
    return layout


def layout_stats(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
        [sg.Column([[sg.Text('Include:  Authors: ', auto_size_text=True, tooltip=tip), sg.Input(key=f'stat_filt_author', tooltip=tip),
                     sg.Text('Date from:', tooltip=tlp_date), 
                     sg.Input(key=f'stat_filt_date_frm', default_text='week', tooltip=tlp_date),
                     sg.Text(' To:', size=(5, 1), tooltip=tlp_date), 
                     sg.Input(key=f'stat_filt_date_to', tooltip=tlp_date),
                     sg.Text(' Symbols:'), sg.Input(key=f'stat_filt_sym', tooltip=tip),
                     sg.Text(' Max $:', tooltip="calculate stats limiting trades to max $"), 
                     sg.Input(key=f'stat_max_trade_val', tooltip="calculate stats limiting trades to max $ amount"),
                     sg.Text(' Max quantity:', tooltip="calculate stats limiting trades to max quantity"), 
                     sg.Input(key=f'stat_max_qty', tooltip="calculate stats limiting trades to max quantity"),
                     sg.Text(' DTE: min', tooltip="Days To Expiration min"), 
                     sg.Input(key=f'stat_dte_min', tooltip="Days To Expiration min"),
                     sg.Text(' max', tooltip="Days To Expiration max"), 
                     sg.Input(key=f'stat_dte_max', tooltip="Days To Expiration max"),
                     
                     ],
                     [sg.Text("Exclude: "),
                      sg.Checkbox("Neg PnL", key="-stat-NegPnL", enable_events=True),
                      sg.Checkbox("Pos PnL", key="-stat-PosPnL", enable_events=True),                  
                      sg.Checkbox("Stocks", key="-stat-stocks", default=True, enable_events=True),
                      sg.Checkbox("Options", key="-stat-options", enable_events=True),
                      sg.Text('| Authors: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'stat_exc_author', tooltip=tip),
                      sg.Text('Symbols: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'stat_exc_sym',tooltip=tip),
                      sg.Text('Channels: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'stat_exc_chn',tooltip=tip),
                      ],
                     [sg.ReadButton("Update", button_color=('white', 'black'),bind_return_key=True, key="_upd-stat_")],
                     [sg.Text("PnL-actual = PnL from prices at the moment of alerted trade (as opposed to the prices claimed in the alert) \n" + \
                         "diff = difference between actual and alerted, high BTO and low STC diffs is bad, alerts are delayed"
                         )]])
                    ],
         [sg.Column([[sg.Table(values=values,
                        headings=data_n_headers[1],
                        display_row_numbers=True,
                        auto_size_columns=True,
                        header_font=font_header,
                        text_color='black',
                        font=font_body,
                        justification='left',
                        alternating_row_color='grey',
                        # num_rows=30, #len(data_n_headers[0]),
                        key='_stat_'), sg.Stretch()]])]
         ]
    return layout

def layout_chan_msg(chn, data_n_headers, font_body, font_header):    
    # Handle empy chan history
    if data_n_headers[0] == []: 
        values = [[""*len(data_n_headers[1])] ]
    else:
        values=data_n_headers[0]

    layout = [
        [sg.Text('Filter:  Authors: '), sg.Input(key=f'{chn}_filt_author'),
           # sg.Text(' '*2),
         sg.Text('Date from: ', tooltip=tlp_date), 
         sg.Input(key=f'{chn}_filt_date_frm', default_text='week', tooltip=tlp_date),
         sg.Text(' To: ', tooltip=tlp_date), sg.Input(key=f'{chn}_filt_date_to', tooltip=tlp_date),
          # sg.Text(' '*1),
         sg.Text('Message contains: '), sg.Input(key=f'{chn}_filt_cont'),
         ],
        [sg.ReadFormButton("Update", button_color=('white', 'black'), key=f'{chn}_UPD', bind_return_key=True)],
        [sg.Column([[sg.Table(values=values,
                  headings=data_n_headers[1],
                  justification='left',
                  display_row_numbers=False,
                  text_color='black',
                  font=font_body,
                  # col_widths=[30,200, 300],
                  header_font=font_header,
                  auto_size_columns =True, max_col_width=30,
                  # auto_size_columns=True,
                  # vertical_scroll_only=False,
                   alternating_row_color='grey',
                  # col_widths=[30,300, 1300],
                  # row_height=20,
                  # num_rows=30,
                  # enable_events = False,
                  # bind_return_key = True,
                #   tooltip = "Selecting row and pressing enter will parse message",
                  key=f"{chn}_table")]])]
        ]
    return layout


def tt_acnt(text, fsize=12, bold=True, underline=True, font_name="Arial", size=None, k=None):
    font = [font_name, fsize]
    if bold: font += ['bold']
    if underline: font += ["underline"]
    if size is None:
        size = (len(text) *2, 1)
    if k is not None:
        return sg.T(text,font=font,size=size, key=k)
    else:
        return sg.T(text,font=font,size=size)


def layout_account(bksession, font_body, font_header):
    if bksession is None:
        return [[sg.T("No brokerage API provided in config.ini")]]
    acc_inf, ainf = gg.get_acc_bals(bksession)
    pos_tab, pos_headings = gg.get_pos(acc_inf)
    if not len(pos_tab):
        pos_tab = ["No post"]
    ord_tab, ord_headings, _= gg.get_orders(acc_inf)

    layout = [[sg.Column([
        [tt_acnt("Account ID:", font_body[1]), tt_acnt(ainf["id"], font_body[1], 0, 0, font_body[0]),
         tt_acnt("Balance:", font_body[1]), tt_acnt("$" + str(ainf["balance"]), font_body[1], 0, 0, font_body[0], k="acc_b"),
         tt_acnt("Cash:", font_body[1]), tt_acnt("$" + str(ainf["cash"]), font_body[1], 0, 0, font_body[0], k="acc_c"),
         tt_acnt("Funds:", font_body[1]), tt_acnt("$" + str(ainf["funds"]), font_body[1], 0, 0, font_body[0], k="acc_f")
         ],[sg.ReadFormButton("Update", button_color=('white', 'black'), key='acc_updt', bind_return_key=True)]
             ])],
        [sg.Column(
            [
             [sg.T("Positions", font=(font_body[0], font_body[1], 'bold', "underline"),size=(20,1.5))],
             [sg.Table(values=pos_tab, headings=pos_headings,justification='left',
              display_row_numbers=False, text_color='black', font=font_body,
               auto_size_columns=True,
               header_font=font_header,
              alternating_row_color='grey',
               max_col_width=30,
              key='_positions_')]]),
        sg.Column(
            [
             [sg.T("Orders",font=(font_header[0], font_header[1], 'bold', "underline"),size=(20,1.5))],
             [sg.Table(values=ord_tab, headings=ord_headings,justification='left',
              display_row_numbers=False, text_color='black', font=font_body,
              auto_size_columns=True, 
              header_font=font_header,
              key='_orders_')]])
            ]]
    return layout


def update_acct_ly(bksession, window):

    acc_inf, ainf = gg.get_acc_bals(bksession)
    pos_tab, _ = gg.get_pos(acc_inf)
    ord_tab, _, _= gg.get_orders(acc_inf)

    window.Element("acc_b").update(ainf["balance"])
    window.Element("acc_c").update(ainf["cash"])
    window.Element("acc_f").update(ainf["funds"])

    window.Element("_positions_").update(pos_tab)
    window.Element("_orders_").update(ord_tab)
    
    for el in ["_positions_", "_orders_"]:
        window.Element(el).Widget.resizeRowsToContents()
        window.Element(el).Widget.resizeColumnsToContents()


def layout_config(fnt_h, cfg):
    
    frame1 =[[sg.Checkbox("Notify alerts to discord", default=cfg['discord'].getboolean('notify_alerts_to_discord'),
                        key="cfg_discord.notify_alerts_to_discord", text_color='black',
                        tooltip='Option to send an your trade alerts to a channel using webhook specified in config.ini')],
            [sg.Text("off market hours:"), 
                sg.Input(cfg['general']['off_hours'],key="cfg_general.off_hours", 
                    tooltip='set your local hours where market is closed, e.g. 16,9 means from 4pm to 9am [eastern time],\nused for sampling quotes and shorting'),
                sg.Stretch()],

            ]
        
    frame2 = [
        [sg.Checkbox('Do BTO trades', cfg['general'].getboolean('Do_BTO_trades'), text_color='black',
                    key="cfg_general.do_BTO_trades", tooltip='Accept Buy alerts and open trades', enable_events=True)],
        [sg.Checkbox('Do STC trades', cfg['general'].getboolean('Do_STC_trades'), text_color='black',
                    key="cfg_general.do_STC_trades", tooltip='Accept Sell alerts and close trade', enable_events=True)],
        # [sg.Checkbox('Sell @ current price', cfg['order_configs'].getboolean('sell_current_price'), 
        #             key="cfg_order_configs.sell_current_price", 
        #             tooltip='When BTO alerts, sell current rather than alerted,\nif alerted is too low it will not fill', enable_events=True)],
        [sg.Text("Authors subscribed:",
                tooltip='list of authors to follow, e.g. me_long,trader#1234'), 
        sg.Input(cfg['discord']['authors_subscribed'],key="cfg_discord.authors_subscribed",
                tooltip='list of authors to follow, e.g. me_long,trader#1234', enable_events=True)],
        [sg.Text("Channelwise subscription:",
                tooltip='Specify a channel to follow allerts from ALL the authors, useful for challenge accounts'), 
        sg.Input(cfg['discord']['channelwise_subscription'], key="cfg_discord.channelwise_subscription",
                tooltip='Specify a channel to follow allerts from ALL the authors, useful for challenge accounts', enable_events=True)],
        [sg.Text("Authorwise subscription:",
                tooltip='The app will capture messages for this user, add it to authors substribed for following the alerts'), 
        sg.Input(cfg['discord']['auhtorwise_subscription'], key="cfg_discord.auhtorwise_subscription", enable_events=True,
                tooltip='The app will capture messages for this user, add it to authors substribed for following the alerts')],
        [sg.Text("Max price diff:",
                tooltip='For stocks and options max value diff to accept current price,\nif not will lim to alerted price'), 
        sg.Input(cfg['order_configs']['max_price_diff'],key="cfg_order_configs.max_price_diff", enable_events=True,
                tooltip='For stocks and options max value diff to accept current price,\nif not will lim to alerted price')],
        [sg.Text("Default exits (in quotes if not a number, eg. '20%', '50%TS20%'):",
                tooltip='If not None, it will set up profit taking (up to 3) and stoploss if exit not provided in alert.\n' +\
                ' can be value=1.1, percentage "30%", for PT can be "%" and a Trailing stop: "30%TS5%"\n' +\
                'SL (stop loss) can be percentage: "30%" or trailing stop "TS30%"\n' +\
                'add quotes to the exits values e.g. "10%"')], 
        [sg.Input(cfg['order_configs']['default_exits'], key="cfg_order_configs.default_exits",
                tooltip='If not None, it will set up profit taking (up to 3) and stoploss if exit not provided in alert.\n' +\
                ' can be $ value: 1.1, percentage: "30%", for PT can be "%" and a Trailing stop: "30%TS5%"\n' +\
                'SL (stop loss) can be percentage: "30%" or trailing stop "TS30%"\n' +\
                'add quotes to the exits values e.g. "10%"', enable_events=True,)],
        [sg.Text("Default quantity:",
                tooltip='If no quantity specified in the alert either "buy_one" or use "trade_capital"'), 
        sg.Drop(values=['buy_one', 'trade_capital'] ,default_value=cfg['order_configs']['default_bto_qty'],
                key="cfg_order_configs.default_bto_qty",
                tooltip='if no quantity specified in the alert either "buy_one" or use "trade_capital"'),
        sg.Stretch()],
        [sg.Text("Trade capital: $",
                tooltip='if default qty == trade_capital, specify the $ amount per trade, qty will be price/capital'), 
        sg.Input(cfg['order_configs']['trade_capital'], key="cfg_order_configs.trade_capital", enable_events=True,
                tooltip='if default qty == trade_capital, specify the $ amount per trade, qty will be price/capital'),
        sg.Stretch()],
        [sg.Text("Max capital per trade: $",
                tooltip='Max investment per trade, if alert qty is higher than this, it will only buy max_trade_capital/price'), 
        sg.Input(cfg['order_configs']['max_trade_capital'], key="cfg_order_configs.max_trade_capital", enable_events=True,
                tooltip='Max investment per trade, if alert qty is higher than this, it will only buy max_trade_capital/price'),
        sg.Stretch()],
        ]
    
    frame3 = [
    [sg.Checkbox('Do STO trades, sell to open', cfg['shorting'].getboolean('DO_STO_TRADES'), text_color='black',
                key="cfg_shorting.DO_STO_TRADES", tooltip='Accept Shorting Trades, \b bypassed if user manually triggers alert')],
    
    [sg.Checkbox("Do BTO trades (buy to open, close trade)",
                cfg['shorting'].getboolean('DO_BTC_TRADES'), key="cfg_shorting.DO_BTC_TRADES",text_color='black',
                tooltip='If True, a close alert with BTO\b bypassed if user manually triggers alert')], 
         
    [sg.Checkbox("BTC at end of day (EOD)", default=cfg['shorting'].getboolean('BTC_EOD'), key="cfg_shorting.BTC_EOD",text_color='black',
                tooltip="Close at end of day, if not overnight there might be big losses"), sg.Stretch()],
    
    [sg.Text('Max price diff', 
             tooltip='Max difference allowed between alerted price and current price, if not will lim to alerted price'),
    sg.Input(cfg['shorting']['max_price_diff'], key="cfg_shorting.max_price_diff",  enable_events=True,
            tooltip='Max difference allowed between alerted price and current price, if not will lim to alerted price'), sg.Stretch()],
    
    [sg.Text("STO Tailing Stop: %",
            tooltip="Trail the price until it drops a %, can be empty so no trailing stop"),
    sg.Input(cfg['shorting']['STO_trailingstop'], key="cfg_shorting.STO_trailingstop", enable_events=True,
            tooltip="Trail the price until it drops a %, can be empty so no trailing stop"), sg.Stretch()],
    
    [sg.Text("BTC PT (profit target) %", tooltip="The percentage to trigger BTC at a profit, can be empty so no PT"),
    sg.Input(cfg['shorting']['BTC_PT'], key="cfg_shorting.BTC_PT",  enable_events=True,
             tooltip="The percentage to trigger BTC at a profit, can be empty so no PT"), sg.Stretch()],
    
    [sg.Text("BTC SL (stop loss) %", tooltip="The percentage to trigger BTC at a profit, can be empty so no PT"),
    sg.Input(cfg['shorting']['BTC_SL'], key="cfg_shorting.BTC_SL",  enable_events=True,
             tooltip="The percentage to trigger BTC at a stoploss, can be empty so no SL"), sg.Stretch()],
    
    [sg.Text("EOF PT and SL %", 
            tooltip="Before close, at 3:45 narrow the SL to 5% and PT to 10% of current price, can be empty"),
    sg.Input(cfg['shorting']['BTC_EOD_PT_SL'], key="cfg_shorting.BTC_EOD_PT_SL", enable_events=True,
            tooltip="Before close, at 3:45 narrow the SL to 5% and PT to 10% of current price, can be empty"), sg.Stretch()],
    
    [sg.Text("Qty based on", tooltip="Either 'buy_one' or use 'underlying_capital' to calculate quantity"),
    sg.Drop(values=['buy_one', 'underlying_capital'], default_value=cfg['shorting']['default_sto_qty'], key="cfg_shorting.default_sto_qty",
            tooltip=" Either 'buy_one' or use 'underlying_capital' to calculate quantity", size=(30,1), enable_events=True), sg.Stretch()],

    [sg.Text("Undelying capital $",
            tooltip="Specify the $ amount per underlying, if 400 and option underlying is 100, it will buy 4 contracts"),
    sg.Input(cfg['shorting']['underlying_capital'], key="cfg_shorting.underlying_capital", enable_events=True,
            tooltip=" Either 'buy_one' or use 'underlying_capital' to calculate quantity"), sg.Stretch()],
    
    [sg.Text("Max days to expiration", 
            tooltip="0 means expiring same day (more volatile and theta decay), 1 means next day, etc"),
    sg.Input(cfg['shorting']['max_dte'], key="cfg_shorting.max_dte", enable_events=True,
            tooltip="0 means expiring same day (more volatile and theta decay), 1 means next day, etc"), sg.Stretch()],
    
    [sg.Text("Max underlying value", 
             tooltip= "Max value of the underlying, margin is usually 100 * strike * 0.20, so SPX 4400 requires about $8k maring"),
    sg.Input(cfg['shorting']['max_strike'], key="cfg_shorting.max_strike", enable_events=True,
             tooltip= "Max value of the underlying, margin is usually 100 * strike * 0.20, so SPX 4400 requires about $8k maring"), sg.Stretch()],
    
    [sg.Text("Min price contract", tooltip="Min price contract, an option at 0.5 price is $50"),
    sg.Input(cfg['shorting']['min_price'], key="cfg_shorting.min_price",  enable_events=True,
            tooltip="Min price contract, an option at 0.5 price is $50"), sg.Stretch()],
    
    [sg.Text("Maximum $ per trade", tooltip="If the quantity is higher than this, it will only buy the max_trade_capital. If one contract is higher than this, it will not buy"),
    sg.Input(cfg['shorting']['max_trade_capital'], key="cfg_shorting.max_trade_capital", enable_events=True,
            tooltip="If the quantity is higher than this, it will only buy the max_trade_capital. If one contract is higher than this, it will not buy"), sg.Stretch()],
    
    [sg.Text("Authors subscribed:", tooltip="Traders to short, do not put the same names as in [order_configs (long)]. Me_short for GUI alert trigger")],
    [sg.Input(cfg['shorting']['authors_subscribed'], key="cfg_shorting.authors_subscribed",  enable_events=True,
            tooltip="Traders to short, do not put the same names as in [order_configs (long)]. Me_short for GUI alert trigger")],
    ]
    lay = [[sg.Text("Session Configuration (change config.ini for permanent changes)", font=(fnt_h+ ' bold'), text_color='black', justification='center')],
        [sg.Frame('General', frame1, title_color='lightred', tooltip='General configurations')],
        [sg.Frame('Long Trading', frame2, title_color='lightred', tooltip='Config for long trading'), 
        sg.Frame('Short Trading', frame3, title_color='lightred', tooltip='Config for long trading')],
        [sg.ReadButton("Save", button_color=('white', 'black'),  bind_return_key=True, key="cfg_button")]
        ]
    
    return lay



