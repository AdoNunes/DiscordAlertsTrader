import unittest
from unittest.mock import MagicMock
import pandas as pd
import os
from DiscordAlertsTrader.discord_bot import DiscordBot


class TestDiscordBot(unittest.TestCase):
    def test_new_msg_acts(self):
        self.tracker_portfolio_fname="tracker_portfolio_name"
        queue_prints = MagicMock()
        bot = DiscordBot(queue_prints=queue_prints, live_quotes=False, brokerage=None,
                         tracker_portfolio_fname=self.tracker_portfolio_fname)

        message = pd.Series({'AuthorID': None,
                            'Author': "JonP",
                            'Date': "2022-01-01 10:00:00.000000", 
                            'Content': 'BTO 5 AI 25c 5/19 @ 1 <@&940418825235619910> swinging',
                            'Channel': "channel 1"
                            })
        bot.new_msg_acts(message, from_disc=False)

        # Example assertions for queue_prints
        print("here:", queue_prints.put.call_args_list)
        self.assertEqual(queue_prints.put.call_count, 3)
        self.assertEqual(queue_prints.put.call_args_list[0][0][0],
                         ['2022-01-01 10:00:00 \t JonP: BTO 5 AI 25c 5/19 @ 1 <@&940418825235619910> swinging ', 'blue'])
        self.assertEqual(queue_prints.put.call_args_list[1][0][0],
                         ['\t \t BTO A 5/19 25C @1.0 amount: 5', 'green'])

        # Delete the generated file
        os.remove(self.tracker_portfolio_fname)

if __name__ == '__main__':
    unittest.main()
