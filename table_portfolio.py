#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr  3 18:18:43 2021

@author: adonay
"""

import PySimpleGUI as sg
import pandas as pd
from datetime import datetime
# Yet another example of showing CSV data in Table



def short_date(datestr, infrm="%Y-%m-%d %H:%M:%S.%f", outfrm="%m/%d %H:%M"):
    return datetime.strptime(datestr, infrm).strftime(outfrm)


def get_raw_data():
    data = pd.read_csv("data/trader_portfolio.csv")
    cols_out = ['Asset', 'Type', 'Avged', 'STC1-uQty', 'STC2-uQty', 'STC3-uQty',
                'STC1-Price', 'STC2-Price', 'STC3-Price','STC1-Date', 'STC2-Date',
                'STC3-Date', 'STC1-ordID', 'STC2-ordID', 'STC3-ordID', 'ordID']

    cols = [c for c in data.columns if c not in cols_out]
    
    data = data[cols]
    
    data.loc[14, 'Date'] = data.loc[14, 'Date'] + '.654773'
    data.loc[15, 'Date'] = data.loc[15, 'Date'] + '.654773'
    
    data['Date'] = data['Date'].apply(lambda x: short_date(x))
    
    cols_flt = ['STC1-PnL', 'STC2-PnL', 'STC3-PnL']
    for col in cols_flt:
        data[col] = data[col].apply(lambda x: "%.2f" % x)
    
    data['Trader'] = data['Trader'].apply(lambda x: x.split('(')[0].split('#')[0])
    
    ['Date', 'Symbol', 'Trader', 'isOpen', 'BTO-Status', 'Asset',
       'Price', 'Alert-Price', 'uQty', 'filledQty', 'exit_plan',
        'STC1-Alerted', 'STC2-Alerted', 'STC3-Alerted', 'STC1-Status',
       'STC2-Status', 'STC3-Status', 'STC1-xQty', 'STC2-xQty', 'STC3-xQty',
        'STC1-PnL', 'STC2-PnL', 'STC3-PnL'],
    
    header_list = data.columns.tolist()
    
    header_list = [d.replace('STC', '') for d in header_list]

    return data.values.tolist(), header_list


hists = ['option_alerts_message_history.csv']
def get_hist_msgs():
    data = pd.read_csv("data/option_alerts_message_history.csv")
    cols = ['Author', 'Date', 'Content']
    data = data[cols]
    header_list = data.columns.tolist()
    return data.values.tolist(), header_list


data, header_list = get_raw_data() 


layout_table = [
    [sg.Table(values=data,
               headings=header_list,
              display_row_numbers=True, vertical_scroll_only=False,
              auto_size_columns=True,
              # alternating_row_color='lightblue',
              num_rows=len(data), key='_TABLE_')],
    [sg.Button("Update", button_color=('white', 'black'), key="-UPDATE-")]
]

data, header_list = get_hist_msgs()
layout_msg = [
    [sg.Table(values=data,
               headings=header_list, justification='left',
              display_row_numbers=False,
              # auto_size_columns=True, 
              vertical_scroll_only=False,
              # alternating_row_color='lightblue',
              col_widths=[30,30, 1300],
              num_rows=10, key='_HIST_')],
    [sg.Button("Update", button_color=('white', 'black'), key="-UPDATE2-")]
]


layout = [[sg.TabGroup([[sg.Tab('Portfolio', layout_table), sg.Tab('Tab 2', layout_msg)]])],
              ]

window = sg.Window('Xtrader', layout, 
                   size=(1090, 500), resizable=True, finalize=True)



while True:

    event, values = window.read()
    if event == sg.WINDOW_CLOSED:
        break
    elif event == "-UPDATE-":
        print("Updateing!")
        dt, hdr = get_raw_data()
        # window.Element('_HIST_').expand(expand_x=True)
        window.Element('_TABLE_').Update(values=dt, num_rows=len(data))

    elif event == "-UPDATE2-":
        print("Updateing!")
        window.Element('_HIST_').expand(expand_x=True)

window.close()

