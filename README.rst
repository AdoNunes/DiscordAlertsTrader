Discord Alerts Trader Bot
________________________

DiscordAlertsTrader is a python package to get messages from a subscribed discord channel where buy
 and sell stock and options signals are messaged. The package will parse the messages and execute
 the trades for traders specified in the config file. 

Trades are done through TDAmeritrade API.  

What this package does:

- Read messages and parse trading singals, e.g. BTO (Buy to Open), STC (Sell to Close), partial STC
- Track trading signals and performance of traders using message history and realtime price
- Execute and cancel orders, check order status, account status and current ticker prices

Currently, the package is for parsing signals of the discord group Xtrades. 
Invite link to Xtrades: https://discord.gg/fMANuG8tR9


 DiscordChatExporter dependency
 ______________________________

 It requires DiscordChatExporter CLI version (tested in Linux and Windows). 
 https://github.com/Tyrrrz/DiscordChatExporter
 For Linux, first intall .NET Core v3.1, as indicated in the DiscordChatExporter exporter.

Once installed, edit config_example.py and save it as config.py. There needs to be:

Path to the  DiscordChatExporter dll:
```
path_dll = "DiscordExtractor/DiscordChatExporter.Cli.dll"
```

Discord token to access discord message chats:
```
discord_token = "token0Y03e..."
```

Channel ID of the channel were trading alers are messaged:
```
channel_IDS = {"stock_alerts": 6666,
               "option_alerts": 4444,
               "options_chat": 5555}

```

Channels from wich actually get trading alerts:
```
CHN_NAMES = ["stock_alerts","option_alerts"] 
```

TDAmeritrade
_______________

To access the TDAmeritrade account for trading and info is necessary to install 
td-ameritrade-python-api from:

```pip install td-ameritrade-python-api```

Follow the instructions from the github repository to set up an API developer account and get a 
tocken:
https://github.com/areed1192/td-ameritrade-python-api

Once installed, edit secrets_api_example.py and save it as secrets_api.py. There needs to be:

```
auth = {
'client_id':'AADDAD',
'redirect_url':'https://127.0.0.1',
'access_token' : 'XRhfXRhf...',
'refresh_token' : 'avXRhfPjEhO'
}
```

