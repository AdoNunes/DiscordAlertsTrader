#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr  3 18:18:43 2021

@author: adonay
"""
import PySimpleGUIQt as sg
import pandas as pd
from datetime import datetime
from place_order import get_TDsession
import gui_generator as gg
import gui_layouts as gl
from PySide2.QtGui import QPainter, QPixmap, QPen, QColor
from PySide2.QtWidgets import QHeaderView
from real_time_exporter import AlertsListner
import queue

TDSession = get_TDsession()

# sg.SetOptions(font=("Courier New", -13))#, background_color="whitesmoke",
               # element_padding=(0, 0), margins=(1, 1))

fnt_b = ("Helvitica", "11")
fnt_h = ("Helvitica", "10")

ly_cons, MLINE_KEY = gl.layout_console()

def mprint(*args, **kwargs):
    window[MLINE_KEY].print(*args, **kwargs)


gui_data = {}
gui_data['port'] = gg.get_portf_data()
ly_port = gl.layout_portfolio(gui_data['port'], fnt_b, fnt_h)

chns = ["stock_alerts", "option_alerts"]
# chns = ["option_alerts"]#, ""]
ly_chns = []
for chn in chns:
    gui_data[chn] = gg.get_hist_msgs(chan_name=chn)
    ly_ch = gl.layout_chan_msg(chn, gui_data[chn], fnt_b, fnt_h)
    ly_chns.append(ly_ch)

ly_accnt = gl.layout_account(TDSession, fnt_b, fnt_h)

layout = [[sg.TabGroup([[sg.Tab("Console", ly_cons)],
                        [sg.Tab('Portfolio', ly_port)],
                        [sg.Tab(c, h) for c, h in zip(chns, ly_chns)],
                        [sg.Tab("Account", ly_accnt)]
                        ])]]

window = sg.Window('Xtrader', layout,size=(1000, 500), # force_toplevel=True,
                    auto_size_text=False, resizable=True, finalize=True)

window[MLINE_KEY].update(readonly=True)

def mprint_queue(queue_item_list):
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


def fit_table_elms(Widget_element):
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()

# event, values = window.read(.1)
# window.GetScreenDimensions()
els = ['_portfolio_', '_orders_', '_positions_'] + [f"{chn}_table" for chn in chns]
for el in els:
    fit_table_elms(window.Element(el).Widget)

for chn in chns:
    table = window[f"{chn}_table"].Widget.horizontalHeader()
    table.setSectionResizeMode(2, QHeaderView.Stretch)
    # table.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    window[f"{chn}_table"].Widget.scrollToBottom()


trade_events = queue.Queue(maxsize=20)
alistner = AlertsListner(trade_events)
# alistner = AlertsListner()


# event, values = window.read(.5)
while True:
    event, values = window.read(.1)

    if event == sg.WINDOW_CLOSED:
        break
    # print(event)

    if event == "_upd-portfolio_":
        print("Updateing!")
        dt, hdr = gg.get_portf_data()
        # window.Element('_portfolio_').expand(expand_x=True)
        window.Element('_portfolio_').Update(values=dt)

    elif event[-3:] == "UPD":
        chn = event[:-4]
        print(f"Updating {chn}!", values)
        # window[f"{chn}_table"].AutoSizeText=True

        args = {}
        for k, v in values.items():
            if k[:len(chn)] == chn:
                args[k[len(chn)+1:]] = v
        dt, _  = gg.get_hist_msgs(chan_name=chn, **args)
        if args['n_rows'] != "":
            n_rows = eval(args['n_rows'])
            n_rows = max(1, n_rows)
            window.Element(f"{chn}_table").Update(values=dt,  num_rows=n_rows)
        else:
            window.Element(f"{chn}_table").Update(values=dt)

        fit_table_elms(window.Element(f"{chn}_table").Widget)

    elif event == 'acc_updt':
        gl.update_acct_ly(TDSession, window)


    try:
        event_feedb = trade_events.get(False)
        mprint_queue(event_feedb)

    except queue.Empty:
       pass


window.close()
alistner.close()

