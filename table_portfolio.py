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

gui_data = {}
gui_data['port'] = get_portf_data()

ly_port = [
     [sg.Column([[sg.Button("Update", button_color=('white', 'black'), key="UPD-port")]])],
     [sg.Table(values=gui_data['port'][0],
                          headings=gui_data['port'][1],
                          display_row_numbers=True, vertical_scroll_only=False,
                          auto_size_columns=True,  pad=(0,0),
                          header_font=("courier", 10), text_color='black',
                          font=("courier", 15), justification='left',
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


layout_account = [[sg.Column([
    [sg.T("Account ID",font=('Arial', 12, 'bold', "underline"),size=(20, 1)),
     sg.T("Balance",font=('Arial', 12, 'bold', "underline"),size=(20, 1)),
     sg.T("Cash",font=('Arial', 12, 'bold', "underline"),size=(20, 1)),
     sg.T("Funds",font=('Arial', 12, 'bold', "underline"), size=(20, 1)),
     ]])],[
    sg.Column([[sg.T("Positions",font=('Arial', 15, 'bold', "underline"))]])],
    [sg.Column([[sg.T("Orders",font=('Arial', 15, 'bold', "underline"))]])]
     ]


layout = [[sg.Column([[sg.TabGroup([[sg.Tab('Portfolio', ly_port),
                                    sg.Tab(chn, layout_msg, k="kk"),
                                    sg.Tab("Account", layout_account)]])]])
           ],
          [sg.Output(key='-OUTPUT-', size=(54, 3))]]

window = sg.Window('Xtrader', layout,# force_toplevel=True,
                   size=(1090, 500), auto_size_text=False, resizable=True, finalize=True)

window['_HIST_'].set_vscroll_position(1)

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
