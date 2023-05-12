# DiscordAlertsTrader: *Discord Alerts Trader Bot*
________________________

DiscordAlertsTrader is a python package to get messages from a subscribed discord channel where buy
 and sell stock and options signals are messaged. The package will parse the messages and execute
 the trades for traders specified in the config file. 

Trades are done through TDAmeritrade API.  

What this package does:

- Read messages and parse trading singals, e.g. BTO (Buy to Open), STC (Sell to Close), partial STC, SL (Stop Limits), PT (Profit Taking)
- Track trading signals and performance of traders using message history and realtime price
- Execute and cancel orders, check order status, account status and current ticker prices

**Currently, the package is for parsing signals of the discord group Xtrades.** 

Invite link to Xtrades: https://discord.gg/fMANuG8tR9


 ## DiscordChatExporter dependency
 ______________________________

It requires discord.py-self. Get a user discord token, then change config_example.py to config.py. There needs to be:

Discord token to access discord message chats:
```
discord_token = "token0Y03e..."
```
to get discord token and channels IDs follow the instructions in: https://github.com/Tyrrrz/DiscordChatExporter/blob/master/.docs/Token-and-IDs.md

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

## TDAmeritrade
_______________

*CURRENTLY NO NEW DEVELOPER ACCOUNT UNTIL THE MERGE*

To access the TDAmeritrade account for trading and info is necessary to install 
td-ameritrade-python-api from:

```pip install td-ameritrade-python-api```

Follow the instructions from the github repository to set up an API developer account and get a 
tocken:
https://github.com/areed1192/td-ameritrade-python-api

once you have your TDA client id, edit secrets_api_example.py and save it as secrets_api.py. There needs to be:

```
auth = {
'client_id':'AADDAD',
'redirect_url':'https://127.0.0.1',
'credentials_path':'secrets_td.json',
}
```

then, run the script:
```python setup.py```
it will prompt to:

```
$ Please go to URL provided authorize your account: https://auth.tdameritrade.com/auth?response_type=code&redirect_uri=.......OAUTHAP
$ Paste the full URL redirect here:
```

In your browser go to the link, accept TD ameritrade pop-up and copy the link you get re-directed. Once entered you will have your secrets_td.json


## Setup and Run
______

First of all **install python**. For windows you can run this in the PowerShell, if you see the output print "Hellow, World!" python with conda is installed:
```# Check if Scoop is installed
if (-not (Test-Path $env:USERPROFILE\scoop)) {
    # Install Scoop
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
    iex (new-object net.webclient).downloadstring('https://get.scoop.sh')
}

# Check if extras are included
$extras = scoop bucket list | Select-String -Pattern '^extras$'
if (-not $extras) {
    # Add the extras bucket
    scoop bucket add extras
}

# Install Miniconda3
scoop install miniconda3

# Run Python script
python -c "print('Hello, World!')"
```

Once downloaded the package, install the dependencies listed in requirements.txt. Then open a terminal, cd to the folder directory of the package and type:

```python setup.py```

This will provide an URL link where to login into TD ameritrade developer API in order to get the credentials:

Run the Command Line Interface:

```python real_time_exporter.py```

Currently, the GUI is available I have to change the name... for now is table_portfolio_qt.py.


## Disclaimer
_________

This is still a Work in Progress project. I get good results using the package, If you plan to use it, **USE AT YOUR OWN RISK**. 

The code and package provided in this repository is provided "as is" and without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the author or contributors be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the code or package or the use or other dealings in the code or package.

Please use this code and package at your own risk. The author and contributors disclaim all liability and responsibility for any errors or issues that may arise from its use. It is your responsibility to test and validate the code and package for your particular use case.

