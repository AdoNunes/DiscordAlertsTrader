#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 11 12:16:45 2021

@author: adonay
"""


path_dotnet = 'C:\\Program Files\\dotnet'
path_dll = "DiscordExtractor/DiscordChatExporter.Cli.dll"
data_dir = "data/"

discord_token = "NDMzM..."

channel_IDS = {"1k-group": 96110,
               "spx": 1089662076,
               "500_challenge": 105804}


CHN_NAMES = ["1k-group","spx", "500_challenge"] 

authors_subscribed = ["ScaredShirtless#0001"]

UPDATE_PERIOD = 20  # how often will check for new Discord messages in sec


SIMULATE = False

if not SIMULATE:
    portfolio_fname = data_dir + "/trader_portfolio.csv"
    alerts_log_fname = data_dir + "/trader_logger.csv"

else:
    portfolio_fname = "./tests/trader_portfolio_simulated.csv"
    alerts_log_fname = "./tests/trader_logger_simulated.csv"


not_subscribed = []
# ORDER DEFAULS
do_BTO = False

#order set to current price if +- 5% for stock and 10% for option
sell_current_price = True
price_as_mark = True
max_price_diff = {"stock": 5, "option":6} # percent

# All stop loss have a % stop lim
default_stop_lim = 10 # percent Not implemented

#
auto_trade = False
if_no_btc_qnty = "buy_one" # or "trade_capital"
trade_capital = 300
trade_capital_max = 1000  # max allowed per one trade


## Rules

# Create STC lim with extended hours
STC_anytime = True

