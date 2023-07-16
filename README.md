# DiscordAlertsTrader: *Discord Alerts Trader Bot*
________________________
![GitHub commit activity (branch)](https://img.shields.io/github/commit-activity/t/AdoNunes/DiscordAlertsTrader?color=red)
![PyPI](https://img.shields.io/pypi/v/DiscordAlertsTrader)
![PyPI - Downloads](https://img.shields.io/pypi/dm/DiscordAlertsTrader)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/DiscordAlertsTrader)
![GitHub](https://img.shields.io/github/license/AdoNunes/DiscordAlertsTrader)
[![Discord](https://img.shields.io/discord/1123242366980075570.svg?label=&logo=discord&logoColor=ffffff&color=7389D8&labelColor=6A7EC2)](https://discord.gg/Zb4ymtF "realtime support / chat with the community and the team.")


A Python package to automate trades from alerts shared in a Discord channel by analysts.
The package parses these messages and executes trades from traders specified in the configuration file. 
It tracks messages from all the channels, generates a portfolio from analysts and from trades executed, 
provides live quotes to see actual alert profits (rather than prices stated in the alert), and can trigger
an alert to open long or short a position, close it or update exits (target profit, stop loss).

Trades are done through APIs of TDAmeritrade (full functionality), eTrade (long positions for now) or webull (long, no OCO, live quotes).
If no brokerage API key is provided, it will just print the discord messages and track the 
analysts portfolio. With an API key, it will track the current price of the alerts, besides executing trades.

If in `config.ini`, `DO_BTO_TRADES = false`, no trades will be executed. 


## GUI capabilities ##

- Parsing trading signals from messages (e.g., BTO, STC, SL, PT).
- Tracking trading signals with a message history tab for the channel
- Tracking performance with real-time actual prices and returns.
- Opening, closing, and updating trades through the GUI.
- Calculate analysts' stats and provide options to test stats with maximum capital 
- Checking order and account status, and accessing current ticker prices.
- Supporting manual trade execution through prompts if `auto_trade` is set to False in `config.ini`.


**Current Discord servers being used**:
- TradeProElite (good timing, profitable strategies): [invite link](https://tradeproelite.memberful.com/referral/vedpmz8)
- BullTrades (good for shorting, see historical trades in the package): [invite link](https://bulltrades.net/?ref=ndrjogi)

Supports any Discord channel with structured BTP/STC alerts as message contents (not embedded, yet)


Let me know if you find the package useful or need support by dropping me a DM @MinkysTradus or visiting the [discord server](https://discord.gg/9ejghcjpar)

 ________________________
<img src="media/GUI_analysts_portfolio.PNG" alt="Analysts Portfolio" width="500" height="300">
<img src="media/GUI_messages.PNG" alt="Channel message history" width="500" height="300">
(older version shots)
<img src="media/xtrader_console.png" alt="Console with discord messages" width="500" height="300">
<img src="media/xtrader_portfolio.png" alt="Portfolio" width="500" height="300">


 ## Discord user token and channel IDs
 ______________________________

It requires a user discord token, once installed the package saves the token in config.ini[discord], as well as the channel ID where alerts are posted.
To get the discord token follow the instructions: https://www.androidauthority.com/get-discord-token-3149920/
To get the channel ID, in Discord right click on the channel and click "Copy Channel ID"

**Automation of user accounts is against Discord ToS. This package only read alerts and Discord can not detect automation behavior,
however, if you want to follow Discords ToS, do not provide a user token and manually input the alerts at the bottom of the GUI to
manually trigger the alerts ;)**

## Installation and Setup
 ______________________________

1. Install Python:
   - For Windows, open PowerShell and run the following command, verify that it prints out "Hello World!":
     ```powershell
     if (-not (Test-Path $env:USERPROFILE\scoop)) {
         # Install Scoop
         Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
         irm get.scoop.sh | iex
     }
     scoop install git
     # Check if extras are included
     $extras = scoop bucket list | Select-String -Pattern '^extras$'
     if (-not $extras) {
         # Add the extras bucket    
         scoop bucket add extras
     }
     # Install Miniconda3
     scoop install miniconda3
     # Check python is installed
     python -c "print('Hello, World!')"
     ```

2. In the PowerShell terminal navigate to the directory where you want to clone the DiscordAlertsTrader package, e.g. type: `cd Desktop`.

3. Clone the package from the GitHub repository and install the package and its dependencies using pip:
   ```shell
   git clone https://github.com/AdoNunes/DiscordAlertsTrader.git
   cd DiscordAlertsTrader
   pip install -e .
   ```

5. Copy the example configuration file to `config.ini`:
   ```shell
   cp DiscordAlertsTrader/config_example.ini DiscordAlertsTrader/config.ini
   ```

6. Edit the `DiscordAlertsTrader/config.ini` file to add your Discord token and configure other settings:
   - Add your Discord token in the appropriate field.
   - (Optional) Modify other configurations as needed, such as authors to follow, trailing stop, etc.
   - (Optional) If you have a TDA/etrade API, add it to the configuration. See next sections.

**Running the DiscordAlertsTrader**

To run the DiscordAlertsTrader, execute the following command in the terminal:

```shell
DiscordAlertsTrader
```

This will launch the DiscordAlertsTrader application and start listening for alerts on Discord.

Make sure to keep the terminal or command prompt window open while the application is running to see any output or errors.

**Closing the Application**

To stop the DiscordAlertsTrader application, simply close the terminal or command prompt window where it is running.

## Etrade API
____________

Create a sandbox (mock) api key:
https://us.etrade.com/etx/ris/apikey

To get the production (real) keys, fill out the forms at the bottom of:
https://developer.etrade.com/getting-started

Make sure to select free real-time quote data:
https://us.etrade.com/etx/hw/subscriptioncenter#/subscription

Before running the package and send orders, in etrade make a trailing stop order and preview to sign an Advanced Order Disclosure, otherwise an error will rise when posting the order

## Webull API
____________

You will need to get a device ID, follow these steps to get DID, and then save it in the config.ini, along with credential details: 
https://github.com/tedchou12/webull/wiki/Workaround-for-Login-Method-2

Trading pin is the 6 digit code used to unlock webull

## TDAmeritrade
_______________

*CURRENTLY NO NEW DEVELOPER ACCOUNT ARE CREATED UNTIL THE MERGE*

To access the TDAmeritrade account for trading and info is necessary to install 
td-ameritrade-python-api from:

```pip install td-ameritrade-python-api```

Follow the instructions from the github repository to set up an API developer account and get a 
token:
https://github.com/areed1192/td-ameritrade-python-api

once you have your TDA client id, edit config.ini TDA section. There needs to be:

```
[TDA]
client_id = QBGUFGH...
redirect_url = https://127.0.0.1/
credentials_path = secrets_td.json
```

then, run the script:
```python setup_TDA.py```
it will prompt to:

```
$Go to URL provided authorize your account: https://auth.tdameritrade.com/auth?response_type=code&redirect_uri=.......OAUTHAP
$ Paste the full URL redirect here:
```

In your browser go to the link, accept TD ameritrade pop-up and copy the link you get re-directed. Once entered you will have your secrets_td.json

## Disclaimer
_________

This is still a Work in Progress project. I get good results using the package, If you plan to use it, **USE AT YOUR OWN RISK**. 

The code and package provided in this repository is provided "as is" and without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the author or contributors be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the code or package or the use or other dealings in the code or package.

Please use this code and package at your own risk. The author and contributors disclaim all liability and responsibility for any errors or issues that may arise from its use. It is your responsibility to test and validate the code and package for your particular use case.

