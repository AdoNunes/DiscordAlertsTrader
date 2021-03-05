#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb 11 12:16:45 2021

@author: adonay
"""



path_dll = "DiscordExtractor/DiscordChatExporter.Cli.dll"
data_dir = "data/"

discord_token = "token0Y03e..."
# token = "ODA5MjEzMzE3MjM0Njg4MDcy.YCR00Q.Zoab0QF6YLyB69b0tQWEVqfmgoc"

channel_IDS = {"stock_alerts": 6666,
               "option_alerts": 4444,
               "options_chat": 5555}


CHN_NAMES = ["stock_alerts","option_alerts"] 

UPDATE_PERIOD = 20  # how often will check for new Discord messages

