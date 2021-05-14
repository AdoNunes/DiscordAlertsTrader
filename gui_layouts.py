#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 27 11:54:36 2021

@author: adonay
"""

import PySimpleGUIQt as sg
import pandas as pd
from datetime import datetime
from gui_generator import (get_portf_data, get_hist_msgs)
from place_order import get_TDsession
import gui_generator as gg
from PySide2.QtGui import QPainter, QPixmap, QPen, QColor
from PySide2.QtWidgets import QHeaderView


def layout_console():
    MLINE_KEY = '-MLINE-__WRITE ONLY__'
    layout = [[sg.Text('Real Time Discord Alert Trader', size=(50,1))],
              [sg.Multiline(size=(1500,800), key=MLINE_KEY)]]
     # [sg.Column([[sg.Multiline(key=MLINE_KEY),sg.Stretch()]])]]
    return layout, MLINE_KEY


def layout_portfolio(data_n_headers, font_body, font_header):
    layout = [
         [sg.Column([[sg.Button("Update", button_color=('white', 'black'), key="_upd-portfolio_")]])],
         [sg.Column([[sg.Table(values=data_n_headers[0],
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


def layout_chan_msg(chn, data_n_headers, font_body, font_header):
    layout = [
        [sg.Text('Filter:  Author: ', size=(20, 1)), sg.Input(key=f'{chn}_filt_author', size=(20, 1)),
           # sg.Text(' '*2),
         sg.Text('Date from: ', size=(15, 1)), sg.Input(key=f'{chn}_filt_date_frm', size=(10, 1), default_text='02/09'),
         sg.Text(' To: ', size=(5, 1)), sg.Input(key=f'{chn}_filt_date_to', size=(10, 1)),
          # sg.Text(' '*1),
         sg.Text('Message contains: ', size=(25, 1)), sg.Input(key=f'{chn}_filt_cont', size=(20, 1)),
         sg.Text('Num. rows display: '), sg.Input(key=f'{chn}_n_rows', size=(5, 1)),
         ],
        [sg.ReadFormButton("Update", button_color=('white', 'black'), key=f'{chn}_UPD', bind_return_key=True)],
        [sg.Column([[sg.Table(values=data_n_headers[0],
                  headings=data_n_headers[1],
                  justification='left',
                  display_row_numbers=False,
                  max_col_width=300, text_color='black',
                  font=font_body,
                  # col_widths=[30,200, 300],
                  header_font=font_header,
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


def row_cols(cols, vals=("Grey", "Brown")):
    # cols = bool x n rows
    return list(map(lambda a: (a[0], vals[0]) if a[1] else (a[0], vals[1]), enumerate(cols)))


def layout_account(TDSession, font_body, font_header):

    acc_inf, ainf = gg.get_acc_bals(TDSession)
    pos_tab, pos_headings = gg.get_pos(acc_inf)
    ord_tab, ord_headings, cols= gg.get_orders(acc_inf)

    layout = [[sg.Column([
        [tt_acnt("Account ID:"), tt_acnt(ainf["id"], font_body[1], 0, 0, font_body[0]),
         tt_acnt("Balance:"), tt_acnt("$" + str(ainf["balance"]), font_body[1], 0, 0, font_body[0], k="acc_b"),
         tt_acnt("Cash:"), tt_acnt("$" + str(ainf["cash"]), font_body[1], 0, 0, font_body[0], k="acc_c"),
         tt_acnt("Funds:"), tt_acnt("$" + str(ainf["funds"]), font_body[1], 0, 0, font_body[0], k="acc_f")
         ],[sg.ReadFormButton("Update", button_color=('white', 'black'), key='acc_updt', bind_return_key=True)]
             ])],
        [sg.Column(
            [
             [sg.T("Positions", font=(font_header[0], font_header[1], 'bold', "underline"),size=(20,1.5))],
             [sg.Table(values=pos_tab, headings=pos_headings,justification='left',
              display_row_numbers=False, text_color='black', font=font_body,
               auto_size_columns=True,header_font=font_header,
              alternating_row_color='grey',
              # col_widths=[30,300, 1300],
              # row_height=20,
              key='_positions_')]]),
        sg.Column(
            [
             [sg.T("Orders",font=(font_header[0], font_header[1], 'bold', "underline"),size=(20,1.5))],
             [sg.Table(values=ord_tab, headings=ord_headings,justification='left',
              display_row_numbers=False, text_color='black', font=font_body,
              auto_size_columns=True, header_font=font_header,
              key='_orders_')]])
            ]]
    return layout


def update_acct_ly(TDSession, window):

    acc_inf, ainf = gg.get_acc_bals(TDSession)
    pos_tab, pos_headings = gg.get_pos(acc_inf)
    ord_tab, ord_headings, cols= gg.get_orders(acc_inf)

    window.Element("acc_b").update(ainf["balance"])
    window.Element("acc_c").update(ainf["cash"])
    window.Element("acc_f").update(ainf["funds"])

    window.Element("_positions_").update(pos_tab)
    window.Element("_orders_").update(ord_tab)



# window['_HIST_'].set_vscroll_position(1)

# window['_orders_'].Widget.config(width=8)

# sg.Print('This text is white on a green background', text_color='white', background_color='green', font='Courier 10')
# sg.Print('The first call sets some window settings like font that cannot be changed')


#sg.popup_scrolled('your_table = [ ', ',\n'.join([str(table[i]) for i in range(MAX_ROWS)]) + '  ]', title='Copy your data from here', font='fixedsys', keep_on_top=True)











