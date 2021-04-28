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

TDSession = get_TDsession()

# sg.SetOptions(font=("Courier New", -13))#, background_color="whitesmoke",
               # element_padding=(0, 0), margins=(1, 1))


fnt_b = ("Helvitica", "11")
fnt_h = ("Helvitica", "10")

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


layout = [[sg.Column([[sg.TabGroup([[sg.Tab('Portfolio', ly_port)],
                                    [sg.Tab(c, h) for c, h in zip(chns, ly_chns)],
                                    [sg.Tab("Account", ly_accnt)]])]])]]


window = sg.Window('Xtrader', layout,# force_toplevel=True,
                   size=(3000, 50), auto_size_text=False, resizable=True, finalize=True)


def fit_table_elms(Widget_element):
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()
    Widget_element.resizeRowsToContents()
    Widget_element.resizeColumnsToContents()

# event, values = window.read(.1)

els = ['_portfolio_', '_orders_', '_positions_'] + [f"{chn}_table" for chn in chns]
for el in els:
    fit_table_elms(window.Element(el).Widget)

for chn in chns:
    table = window[f"{chn}_table"].Widget.horizontalHeader()
    table.setSectionResizeMode(2, QHeaderView.Stretch)
    # table.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    window[f"{chn}_table"].Widget.scrollToBottom()

# i = window.Element('_PORT_').Widget.item(1,1)
# i.setBackground(QColor('red'))
event, values = window.read(.5)
while True:
    event, values = window.read()
    print(event)
    if event == sg.WINDOW_CLOSED:
        break

    elif event == "_upd-portfolio_":
        print("Updateing!")
        dt, hdr = gg.get_portf_data()
        # window.Element('_portfolio_').expand(expand_x=True)
        window.Element('_portfolio_').Update(values=dt, num_rows=len(dt))

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




window.close()


