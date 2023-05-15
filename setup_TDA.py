from DiscordAlertsTrader.brokerages.TDA_api import TDA


# TD access and refresh tokens will be generated
tda = TDA()
tda.get_session()