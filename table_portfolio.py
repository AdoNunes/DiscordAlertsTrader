#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr  3 18:18:43 2021

@author: adonay
"""
import PySimpleGUI as sg
import pandas as pd
from datetime import datetime
from gui_generator import (get_portf_data, get_hist_msgs)
from place_order import get_TDsession
import gui_generator as gg

TDSession = get_TDsession()

# sg.SetOptions(font=("Courier New", -13))#, background_color="whitesmoke",
               # element_padding=(0, 0), margins=(1, 1))
sg.theme('Dark Blue 3')
gui_data = {}
gui_data['port'] = get_portf_data()

ly_port = [
     [sg.Column([[sg.Button("Update", button_color=('white', 'black'), key="UPD-port"),
                  sg.Slider((6, 50), default_value=12, size=(14, 20),
                     orientation='h', key='-slider-', change_submits=True)]])],
     [sg.Table(values=gui_data['port'][0],
                          headings=gui_data['port'][1],
                          display_row_numbers=True, vertical_scroll_only=False,
                          auto_size_columns=True,  pad=(0,0),
                          header_font=("Helvitica", 10), text_color='black',
                          font=("Helvitica", 15), justification='left',
                          alternating_row_color='grey',
                          num_rows=len(gui_data['port'][0]), key='_PORT_'),]
           ]


chn = "option_alerts"
gui_data[chn] = get_hist_msgs(chan_name=chn)

layout_msg = [
    [sg.Text('Filter: Author '), sg.Input(key='filt_author', size=(20, 1)),
     sg.Text(' '*10),
     sg.Text('Date from: '), sg.Input(key='filt_date_frm', size=(10, 1)),
     sg.Text(' To: '), sg.Input(key='filt_date_to', size=(10, 1)),
     sg.Text(' '*10),
     sg.Text('Message contains: '), sg.Input(key='filt_cont', size=(20, 1)),
     ],
    [sg.ReadFormButton("Update", button_color=('white', 'black'), key="UPD-chn")],
    [sg.Table(values=gui_data[chn] [0],
               headings=gui_data[chn] [1],
               justification='left',
              display_row_numbers=False,
              max_col_width=200, text_color='black',
              font=("courier", 15),
              # auto_size_columns=True,
              vertical_scroll_only=False,
               alternating_row_color='grey',
              # col_widths=[30,300, 1300],
              row_height=20,
              num_rows=30, key='_HIST_')],
]

acc_inf, ainf = gg.get_acc_bals(TDSession)
pos_tab, pos_headings = gg.get_pos(acc_inf)
ord_tab, ord_headings, cols= gg.get_orders(acc_inf)

def tt_acnt(text, fsize=12):
    return sg.T(text,font=('Arial', fsize, 'bold', "underline"),size=(20, 1))
def tv_acnt(text, fsize=12):
    return sg.T(text,font=('Arial', fsize),size=(20, 1))

def row_cols(cols, vals=("Grey", "Brown")):
    # cols = bool x n rows
    return list(map(lambda a: (a[0], vals[0]) if a[1] else (a[0], vals[1]), enumerate(cols)))



layout_account = [[sg.Column([
    [tt_acnt("Account ID"), tt_acnt("Balance"),
     tt_acnt("Cash"), tt_acnt("Funds")],
    [tv_acnt(ainf["id"]), tv_acnt("$" + str(ainf["balance"])),
     tv_acnt("$" + str(ainf["cash"])), tv_acnt("$" + str(ainf["funds"]))]
    ])],
    [sg.Column(
        [[sg.T("Positions", font=('Arial', 15, 'bold', "underline"))],
         [sg.Table(values=pos_tab, headings=pos_headings,justification='left',
          display_row_numbers=False, text_color='black', font=("courier", 15),
          # auto_size_columns=True,
          vertical_scroll_only=False, alternating_row_color='grey',
          # col_widths=[30,300, 1300],
          row_height=20, key='_positions_')]])],
    [sg.Column(
        [[sg.T("Orders",font=('Arial', 15, 'bold', "underline"))],
         [sg.Table(values=ord_tab, headings=ord_headings,justification='left',
          display_row_numbers=False, text_color='black', font=("courier", 15),
          selected_row_colors= cols,
          vertical_scroll_only=False,
          row_colors=row_cols(cols),
          row_height=20,  key='_orders_')]])
        ]]



layout = [[sg.Column([[sg.TabGroup([[sg.Tab('Portfolio', ly_port),
                                    sg.Tab(chn, layout_msg, k="kk"),
                                    sg.Tab("Account", layout_account)]])]])
           ],]
          # [sg.Output(key='-OUTPUT-', size=(54, 3))]]

window = sg.Window('Xtrader', layout,# force_toplevel=True,
                   size=(2590, 1500), auto_size_text=False, resizable=True, finalize=True)

window['_HIST_'].set_vscroll_position(1)

# window.TKroot.tk.call('tk', 'scaling', 2)

# window['_orders_'].Widget.config(width=8)

# sg.Print('This text is white on a green background', text_color='white', background_color='green', font='Courier 10')
# sg.Print('The first call sets some window settings like font that cannot be changed')
# sg.Print('This is plain text just like a print would display')
# sg.Print('White on Red', background_color='red', text_color='white')
# sg.Print('The other print', 'parms work', 'such as sep', sep=',')
# sg.Print('To not extend a colored line use the "end" parm', background_color='blue', text_color='white', end='')
# sg.Print('\nThis line has no color.')

#sg.popup_scrolled('your_table = [ ', ',\n'.join([str(table[i]) for i in range(MAX_ROWS)]) + '  ]', title='Copy your data from here', font='fixedsys', keep_on_top=True)

#force_toplevel=True,

while True:

    event, values = window.read()
    if event == sg.WINDOW_CLOSED:
        break

    if event == '-slider-':
        font_string = 'Helvitica '
        font_string += str(int(values['-slider-']))
        window.Element('_PORT_').Update(font=font_string)

    elif event == "UPD-port":
        print("Updateing!")
        # gui_data['port'] = get_portf_data()
        dt, hdr = get_portf_data()
        # window.Element('_HIST_').expand(expand_x=True)
        window.Element('_PORT_').Update(values=dt, num_rows=len(dt))

    elif event == "UPD-chn":
        print("Updating!")
        print(values)

        window['_HIST_'].AutoSizeText=True
        del values[0]
        dt, _  =  get_hist_msgs(**values)
        window.Element('_HIST_').Update(values=dt, num_rows=len(dt))
        window['_HIST_'].set_vscroll_position(1)

#  window['-TABLE-'].set_vscroll_position(.5)
# wraplen = window['_HIST_'].Widget.winfo_reqwidth()  # width tkinter says widget will be
#             window['-OUT-'].Widget.configure(wraplen=wraplen)

window.close()


# borderwidth
# colormap
