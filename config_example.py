#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 11 12:16:45 2021

@author: adonay
"""



path_dll = "DiscordExtractor/DiscordChatExporter.Cli.dll"
data_dir = "data/"

discord_token = "token0Y03e..."

channel_IDS = {"stock_alerts": 6666,
               "option_alerts": 4444,
               "options_chat": 5555}


CHN_NAMES = ["stock_alerts","option_alerts"] 

UPDATE_PERIOD = 20  # how often will check for new Discord messages


SIMULATE = False

if not SIMULATE:
    portfolio_fname = data_dir + "/trader_portfolio.csv"
    alerts_log_fname = data_dir + "/trader_logger.csv"

else:
    portfolio_fname = "./tests/trader_portfolio_simulated.csv"
    alerts_log_fname = "./tests/trader_logger_simulated.csv"

# authors_subscribed = ['Xtrades Option Guru#8905', "ScaredShirtless#0001", "Kevin (Momentum)#8888"]
authors_subscribed = ["ScaredShirtless#0001"]

not_subscribed = []
# ORDER DEFAULS
do_BTO = False

#order set to current price if +- 5% for stock and 10% for option
sell_current_price = True
price_as_mark = True
max_price_diff = {"stock": 5, "option":6} # percent

# All stop loss have a % stop lim
default_stop_lim = 3 # percent

#
auto_trade = True
trade_capital = 300
trade_capital_max = 800

## Rules

# Create STC lim with extended hours
STC_anytime = True

# @everyone STC PLTR 32.5c 2/19 @ 0.20. I broke my rule. If you average down and get break even, take it. Now I have to pay for breaking my own rule.
