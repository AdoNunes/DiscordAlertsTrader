import unittest
from unittest.mock import MagicMock
import pandas as pd
import os
from datetime import datetime, timedelta
from DiscordAlertsTrader.discord_bot import DiscordBot
from mock_discord_message import make_message
from DiscordAlertsTrader.configurator import cfg

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestDiscordBot(unittest.TestCase):
    def test_new_msg_acts_from_discord_msg(self):
        
        self.tracker_portfolio_fname=root_dir+"/data/test_tracker_portfolio.csv"

        queue_prints = MagicMock()
        bot = DiscordBot(queue_prints=queue_prints, live_quotes=False, brokerage=None,
                         tracker_portfolio_fname=self.tracker_portfolio_fname,
                         cfg=cfg)
        
        message = make_message()
        bot.new_msg_acts(message, from_disc=True)
        print("portfolio after:", bot.tracker.portfolio)
        port = bot.tracker.portfolio.loc[0]
        self.assertEqual(port['isOpen'], 1)
        self.assertEqual(port['Price'], 1.0)
        self.assertEqual(port['Symbol'], 'AI_120923C25')
        self.assertEqual(port['Trader'], f"{message.author.name}#{message.author.discriminator}")
        self.assertEqual(port['Amount'], 5)
        # sell
        message.content = 'STC 5 AI 25c 12/09 @ 2 <@&940418825235619910> swinging'
        bot.new_msg_acts(message, from_disc=True)
        port = bot.tracker.portfolio.loc[0]
        self.assertEqual(port['isOpen'], 0)
        self.assertEqual(port['STC-Amount'], 5)
        self.assertEqual(port['STC-Price'], 2.0)
        self.assertEqual(port['STC-Price'], 2.0)
        self.assertEqual(port['STC-PnL'], 100.0)
        
        # Delete the generated file
        os.remove(self.tracker_portfolio_fname)

    def test_new_msg_acts(self):
        self.tracker_portfolio_fname=root_dir+"/data/test_tracker_portfolio.csv"
        queue_prints = MagicMock()
        bot = DiscordBot(queue_prints=queue_prints, live_quotes=False, brokerage=None,
                         tracker_portfolio_fname=self.tracker_portfolio_fname)
        expdate = datetime.now().strftime("%m/%d")
        message = pd.Series({'AuthorID': None,
                            'Author': "JonP",
                            'Date': "2022-01-01 10:00:00.000000", 
                            'Content': f'BTO 5 AI 25c {expdate} @ 1 <@&940418825235619910> swinging',
                            'Channel': "channel 1"
                            })
        bot.new_msg_acts(message, from_disc=False)

        # Example assertions for queue_prints
        print("here:", queue_prints.put.call_args_list)
        self.assertEqual(queue_prints.put.call_count, 3)
        self.assertEqual(queue_prints.put.call_args_list[0][0][0],
                         [f'\n2022-01-01 10:00:00 channel 1: \n\tJonP: BTO 5 AI 25c {expdate} @ 1 <@&940418825235619910> swinging ', 'blue'])
        self.assertEqual(queue_prints.put.call_args_list[1][0][0],
                         [f'\t BTO 5 AI 25c {expdate} 1 ', 'green'])

        # Delete the generated file
        os.remove(self.tracker_portfolio_fname)

    def test_new_msg_acts_wrong_date(self):
        self.tracker_portfolio_fname=root_dir+"/data/test_tracker_portfolio.csv"
        queue_prints = MagicMock()
        bot = DiscordBot(queue_prints=queue_prints, live_quotes=False, brokerage=None,
                         tracker_portfolio_fname=self.tracker_portfolio_fname)
        expdate = datetime.now() - timedelta(days=1)
        expdate = expdate.strftime("%m/%d")
        
        message = pd.Series({'AuthorID': None,
                            'Author': "JonP",
                            'Date': "2022-01-01 10:00:00.000000", 
                            'Content': f'BTO 5 AI 25c {expdate} @ 1 <@&940418825235619910> swinging',
                            'Channel': "channel 1"
                            })
        bot.new_msg_acts(message, from_disc=False)

        # Example assertions for queue_prints
        print("here:", queue_prints.put.call_args_list)
        self.assertEqual(queue_prints.put.call_count, 2)
        self.assertEqual(queue_prints.put.call_args_list[0][0][0],
                         [f'\n2022-01-01 10:00:00 {message["Channel"]}: \n\tJonP: BTO 5 AI 25c {expdate} @ 1 <@&940418825235619910> swinging ', 'blue'])
        self.assertEqual(queue_prints.put.call_args_list[1][0][0],
                         [f'\t Option date in the past: {expdate}', 'green'])

        # Delete the generated file
        os.remove(self.tracker_portfolio_fname)

if __name__ == '__main__':
    unittest.main()
