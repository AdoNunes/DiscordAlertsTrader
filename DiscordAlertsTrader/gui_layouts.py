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
    lay = [sg.Stretch(), sg.Text('to portfolio:', tooltip=tp_chan),
           sg.Combo(['both', 'user', 'analysts'], default_value='analysts', key="_chan_trigg_",tooltip=tp_chan, readonly=True, size=(15,1.2)),
            sg.Input(default_text="Author#1234, STC 1 AAA 115C 05/30 @2.5 [click portfolio row number to prefill]",
                    size= (100,1.3), key="-subm-msg",
                    tooltip=tp_trig),
           sg.Button("Trigger alert", key="-subm-alert", 
                     tooltip="Will generate alert in user or/and analysts portfolio, useful to close or open a position", size= (20,1.2))]
    return lay

def layout_portfolio(data_n_headers, font_body, font_header):
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
         [sg.Column([[
            sg.Text('Include:  Authors: ', auto_size_text=True,tooltip=tip), sg.Input(key=f'port_filt_author',tooltip=tip),
            sg.Text('Date from: ', tooltip=tlp_date), sg.Input(key=f'port_filt_date_frm', size=(16, 1), default_text='week', tooltip=tlp_date),
            sg.Text(' To: ', tooltip=tlp_date), sg.Input(key=f'port_filt_date_to', size=(16, 1), tooltip=tlp_date),
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
            [sg.ReadButton("Update", button_color=('white', 'black'), key="_upd-portfolio_")]])],
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
            sg.Input(key=f'track_filt_date_frm', default_text='week', size=(16, 1), tooltip=tlp_date),
            sg.Text(' To: ', tooltip=tlp_date), sg.Input(key=f'track_filt_date_to', size=(16, 1), tooltip=tlp_date),
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
            ],[sg.ReadButton("Update", button_color=('white', 'black'), key="_upd-track_")]
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
                     sg.Input(key=f'stat_filt_date_frm', size=(16, 1), default_text='week', tooltip=tlp_date),
                     sg.Text(' To:', size=(5, 1), tooltip=tlp_date), 
                     sg.Input(key=f'stat_filt_date_to', size=(16, 1), tooltip=tlp_date),
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
                     [sg.ReadButton("Update", button_color=('white', 'black'), key="_upd-stat_")],
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


