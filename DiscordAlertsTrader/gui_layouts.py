#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 27 11:54:36 2021

@author: adonay
"""

import PySimpleGUIQt as sg
from . import gui_generator as gg



def layout_console():
    MLINE_KEY = '-MLINE-__WRITE ONLY__'
    layout = [[sg.Text('Real Time Discord Alert Trader', size=(50,1))],
              [sg.Multiline(size=(1500,800), key=MLINE_KEY)]]
     # [sg.Column([[sg.Multiline(key=MLINE_KEY),sg.Stretch()]])]]
    return layout, MLINE_KEY


def layout_portfolio(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
         [sg.Column([[sg.Text('Filter:  Author: ', size=(20, 1)), sg.Input(key=f'port_filt_author', size=(20, 1)),
                      sg.Text('Date from: ', size=(15, 1)), sg.Input(key=f'port_filt_date_frm', size=(18, 1), default_text='05/10/2023'),
                      sg.Text(' To: ', size=(5, 1)), sg.Input(key=f'port_filt_date_to', size=(15, 1)),
                      sg.Text('   Contains symbol: ', size=(20, 1)), sg.Input(key=f'port_filt_sym', size=(20, 1)),
                      ],
                     [sg.Text("Exclude: "),
                      sg.Checkbox("Closed", key="-port-Closed", enable_events=True),
                      sg.Checkbox("Open", key="-port-Open", enable_events=True),
                      sg.Checkbox("Cancelled", key="-port-Cancelled", default=True, enable_events=True),
                      sg.Checkbox("Neg PnL", key="-port-NegPnL", enable_events=True),
                      sg.Checkbox("Pos PnL", key="-port-PosPnL", enable_events=True),
                      sg.Checkbox("Live PnL", key="-port-live PnL", enable_events=True),
                      sg.Checkbox("Stocks", key="-port-stocks", default=True, enable_events=True),
                      sg.Checkbox("Options", key="-port-options", enable_events=True),
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
                        key='_portfolio_'), sg.Stretch()]])]
         ]
    return layout


def layout_traders(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
        [sg.Column([[sg.Text('Filter:  Author: ', size=(20, 1)), sg.Input(key=f'track_filt_author', size=(20, 1)),
                     sg.Text('Date from: ', size=(15, 1)), sg.Input(key=f'track_filt_date_frm', size=(18, 1), default_text='05/10/2023'),
                     sg.Text(' To: ', size=(5, 1)), sg.Input(key=f'track_filt_date_to', size=(18, 1)),
                     sg.Text('   Contains symbol: ', size=(20, 1)), sg.Input(key=f'track_filt_sym', size=(20, 1)),
                     ],
                     [sg.Text("Exclude: "),
                      sg.Checkbox("Closed", key="-track-Closed", enable_events=True),
                      sg.Checkbox("Open", key="-track-Open", enable_events=True),
                      sg.Checkbox("Neg PnL", key="-track-NegPnL", enable_events=True),
                      sg.Checkbox("Pos PnL", key="-track-PosPnL", enable_events=True),
                      sg.Checkbox("Live PnL", key="-track-live PnL", enable_events=True),                   
                      sg.Checkbox("Stocks", key="-track-stocks", default=True, enable_events=True),
                      sg.Checkbox("Options", key="-track-options", enable_events=True)
                      ],
                     [sg.ReadButton("Update", button_color=('white', 'black'), key="_upd-track_")]])
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
                        key='_track_'), sg.Stretch()]])]
         ]
    return layout


def layout_stats(data_n_headers, font_body, font_header):
    
    if data_n_headers[0] == []: 
        values = [""*21 ]
    else:
        values=data_n_headers[0]
    
    layout = [
        [sg.Column([[sg.Text('Filter:  Author: ', size=(20, 1)), sg.Input(key=f'stat_filt_author', size=(20, 1)),
                     sg.Text('Date from: ', size=(15, 1)), sg.Input(key=f'stat_filt_date_frm', size=(18, 1), default_text='05/10/2023'),
                     sg.Text(' To: ', size=(5, 1)), sg.Input(key=f'stat_filt_date_to', size=(18, 1)),
                     sg.Text('  Contains symbol: ', size=(20, 1)), sg.Input(key=f'stat_filt_sym', size=(20, 1)),
                     sg.Text(' Max $: ', size=(10, 1)), sg.Input(key=f'stat_max_trade_cap', size=(10, 1)),
                     sg.Text(' Max quantity: ', size=(10, 1)), sg.Input(key=f'stat_max_qty', size=(10, 1)),
                     ],
                     [sg.Text("Exclude: "),
                      sg.Checkbox("Closed", key="-stat-Closed", enable_events=True),
                      sg.Checkbox("Open", key="-stat-Open", enable_events=True),
                      sg.Checkbox("Neg PnL", key="-stat-NegPnL", enable_events=True),
                      sg.Checkbox("Pos PnL", key="-stat-PosPnL", enable_events=True),
                      sg.Checkbox("Live PnL", key="-stat-live PnL", enable_events=True),                   
                      sg.Checkbox("Stocks", key="-stat-stocks", default=True, enable_events=True),
                      sg.Checkbox("Options", key="-stat-options", enable_events=True)
                      ],
                     [sg.ReadButton("Update", button_color=('white', 'black'), key="_upd-stat_")]])
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
        [sg.Text('Filter:  Author: ', size=(20, 1)), sg.Input(key=f'{chn}_filt_author', size=(20, 1)),
           # sg.Text(' '*2),
         sg.Text('Date from: ', size=(15, 1)), sg.Input(key=f'{chn}_filt_date_frm', size=(10, 1), default_text='05/09'),
         sg.Text(' To: ', size=(5, 1)), sg.Input(key=f'{chn}_filt_date_to', size=(10, 1)),
          # sg.Text(' '*1),
         sg.Text('Message contains: ', size=(25, 1)), sg.Input(key=f'{chn}_filt_cont', size=(20, 1)),
         sg.Text('Num. rows display: '), sg.Input(key=f'{chn}_n_rows', size=(5, 1)),
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
                  auto_size_columns =True, max_col_width=50,
                  # auto_size_columns=True,
                  # vertical_scroll_only=False,
                   alternating_row_color='grey',
                  # col_widths=[30,300, 1300],
                  # row_height=20,
                  # num_rows=30,
                  # enable_events = False,
                  # bind_return_key = True,
                  tooltip = "Selecting row and pressing enter will parse message",
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


