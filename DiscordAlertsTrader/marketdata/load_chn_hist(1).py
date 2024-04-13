import subprocess
import os.path as op
import os
import pandas as pd
from DiscordAlertsTrader.configurator import cfg
import pandas as pd
from datetime import datetime, timedelta
from thetadata import ThetaClient
from thetadata import DataType
from DiscordAlertsTrader.marketdata.thetadata_api import ThetaClientAPI
from DiscordAlertsTrader.message_parser import parse_trade_alert
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.alerts_tracker import AlertsTracker
from DiscordAlertsTrader.read_hist_msg import parse_hist_msg
from DiscordAlertsTrader.port_sim import get_hist_quotes
import re

# parameters
use_theta_rest_api = True
is_mac = False
after, date_after = "", ""
get_date_after_from_port = True
re_download = False
delete_port = False
author = "moneymotiveA+"


def get_timestamp(row):
    date_time = row[DataType.DATE] + timedelta(milliseconds=row[DataType.MS_OF_DAY])
    return date_time.timestamp()


def add_past_year(alert, year):

    pattern = r"([0-1]?[0-9]\/[0-3]?[0-9])"
    matches = re.findall(pattern, alert)
    current_date = datetime.now()

    modified_dates = []
    for match in matches:
        try:
            date_obj = datetime.strptime(match + f"/{year}", "%m/%d/%Y")
        except ValueError:
            continue

        # Check if the date is within one year from now
        if date_obj <= current_date:
            modified_dates.append(date_obj)
            alert = alert.replace(match, date_obj.strftime("%m/%d/%Y"))

    return alert


def save_or_append_quote(quotes, symbol, path_quotes, overwrite=False):
    fname = f"{path_quotes}/{symbol}.csv"
    if overwrite:
        quotes.to_csv(fname, index=False)
        return
    try:
        df = pd.read_csv(fname)
        df = pd.concat([df, quotes], ignore_index=True)
        df = df.sort_values(by=["timestamp"]).drop_duplicates(subset=["timestamp"])
    except FileNotFoundError:
        df = quotes
    df.to_csv(fname, index=False)


chan_ids = {
    "theta_warrior_elite": 897625103020490773,
    "demon": 904396043498709072,
    "eclipse": 1213995695237763145,
    "moneymotive": 1012144319282556928,
    "moneymotiveA+": 1214378575554150440,
    "bishop": 1195073059770605568,
    "makeplays": 1164747583638491156,
    "kingmaker": 1152082112032292896,
    "oculus": 1005221780941709312,
    'diesel': 1107395495460081754,
    'ddking': 1139700590339969036,
    "crimson": 1102753361566122064,
    "HHscanner": 1095786767514341507,
    "vader": 1207716385346822245,
    "gianni": 1209992523083415603,
    "og-alerts": 1207717868716826645,
    "EM": 1126325195301462117,
    "vader-swings":1223379548675117088,
    }
chan_id = chan_ids[author]
if not use_theta_rest_api:
    client = ThetaClient(
        username=cfg["thetadata"]["username"], passwd=cfg["thetadata"]["passwd"]
    )
    client.connect()
else:
    client = ThetaClientAPI()

token = cfg["discord"]["discord_token"]
path_exp = cfg["general"]["data_dir"] + "/../../DiscordChatExporter.Cli"
path_out_exp = cfg["general"]["data_dir"] + "/exported"
path_parsed = cfg["general"]["data_dir"] + "/parsed"

os.makedirs(path_out_exp, exist_ok=True)
os.makedirs(path_parsed, exist_ok=True)

port_fname = f"{cfg['general']['data_dir']}/{author}_port.csv"

if delete_port and op.exists(port_fname):
    # ask for confirmation
    response = input(f"Delete {port_fname}? (y/n)")
    if response.lower() == "y":
        os.remove(port_fname)

if op.exists(port_fname) and get_date_after_from_port:
    port = pd.read_csv(port_fname)
    max_date_stc = port["STC-Date"].dropna().max()
    max_date_bto = port["Date"].max()
    # Find the maximum date between the two
    if pd.isna(max_date_stc):
        max_date = max_date_bto
    else:
        max_date = max(max_date_stc, max_date_bto)

    # add 1 second to the max date
    max_date = datetime.strptime(max_date, "%Y-%m-%d %H:%M:%S.%f") + timedelta(
        seconds=1
    )
    after = "--after " + str(max_date).replace(" ", "T")
    date_after = str(max_date).replace(" ", "_").replace(":", "_")

if date_after == "nan":
    date_after = ""

input(f"Getting messages after {date_after}. Press Enter to continue.")

fname_out = op.join(path_out_exp, f"{author}_export_{date_after}.json")
if re_download or not op.exists(fname_out):
    command = f"cd {path_exp} && .\DiscordChatExporter.Cli.exe export  -t {token} -f Json -c {chan_id} -o {fname_out} {after}"
    if is_mac:
        command = f"docker run --rm -it -v ~/Documents/code/stocks/DiscordAlertsTrader/data/exported:/out tyrrrz/discordchatexporter:stable export -f Json --channel {chan_id} -t {token} {after} -o {author}_export_{date_after}.json"
    try:
        print("Executing command:", command)
        # input("Press Enter to continue.")
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            print("Command executed successfully:")
            print(result.stdout)
        else:
            print("Command failed with error:")
            print(result.stderr)
            input("Press Enter to continue.")
    except Exception as e:
        print("An error occurred:", str(e))
        input("Press Enter to continue.")

msg_hist = parse_hist_msg(fname_out, author)
msg_hist.to_csv(op.join(path_parsed, f"{author}_parsed_{date_after}.csv"), index=False)

tracker = AlertsTracker(
    brokerage=None,
    portfolio_fname=port_fname,
    dir_quotes=cfg["general"]["data_dir"] + "/hist_quotes",
    cfg=cfg,
)

dt = None
for ix, row in msg_hist.iterrows():  # .loc[ix:].iterrows(): #
    print(ix)
    alert = row["Content"]
    if pd.isnull(alert) or not len(alert) or alert in ["@everyone", "@Elite Options"]:
        continue

    year = datetime.strptime(row["Date"][:26], "%m/%d/%Y %H:%M:%S.%f").year
    if year != datetime.now().year:
        alert = add_past_year(alert, year)
    pars, order = parse_trade_alert(alert)

    if order is None or order.get("expDate") is None:
        continue

    order["Trader"] = row["Author"]
    dt = datetime.strptime(row["Date"], "%m/%d/%Y %H:%M:%S.%f")  # + timedelta(hours=2)
    order["Date"] = dt.strftime("%Y-%m-%d %H:%M:%S.%f")

    tsm = round(pd.to_datetime(order["Date"]).tz_localize('America/New_York').tz_convert('UTC').timestamp())

    full_date = (
        order["expDate"] + f"/{year}"
        if len(order["expDate"].split("/")) == 2
        else order["expDate"]
    )
    dt_fm = (
        "%m/%d/%y"
        if len(full_date.split("/")) == 2
        else "%m/%d/%Y" if len(full_date.split("/")[2]) == 4 else "%m/%d/%y"
    )
    if datetime.strptime(full_date, dt_fm).date() < dt.date():
        print("Order date in the past, skipping", order["expDate"], order["Date"])
        resp = tracker.trade_alert(order, live_alert=False, channel=author)
        continue

    try:
        if use_theta_rest_api:
            out = client.get_hist_quotes(order["Symbol"], [dt.date()])
        else:
            out = get_hist_quotes(order["Symbol"], [dt.date()], client)
        # save_or_append_quote(out, order['Symbol'], 'data/hist_quotes')
        out = out.reset_index(drop=True)
    except Exception as e:
        print(f"row {ix}, No data for", order["Symbol"], order["Date"], e)
        resp = tracker.trade_alert(order, live_alert=False, channel=author)
        continue
    if not len(out):
        print("0 data for", order["Symbol"], order["Date"])
        resp = tracker.trade_alert(order, live_alert=False, channel=author)
        continue

    if tsm > out.iloc[-1]["timestamp"]:
        print(
            "Order time outside of market hours",
            order["action"],
            order["expDate"],
            order["Date"],
            order["Symbol"],
            ix,
        )
        resp = tracker.trade_alert(order, live_alert=False, channel=author)
        continue

    try:
        order["price_actual"] = out.iloc[out[out["timestamp"] == tsm].index[0] + 1]["ask"]
        order["price_actual_bid"] = out.iloc[out[out["timestamp"] == tsm].index[0] + 1]["bid"]
    except IndexError:
        print("No time match for", order["Symbol"], order["Date"])

    bto_date = tracker.portfolio[
        (tracker.portfolio["Symbol"] == order["Symbol"]) & (tracker.portfolio["isOpen"])
    ]
    if len(bto_date):
        bto_date = bto_date["Date"]

    try:
        resp = tracker.trade_alert(order, live_alert=False, channel=author)
        tracker.portfolio.loc[(tracker.portfolio['Symbol'] == order['Symbol']) & (tracker.portfolio['isOpen']==1), 'bid'] = order['price_actual_bid']
    except:
        print("No date match for", order["Symbol"], order["Date"])
        continue

    if order["action"] == "STC":
        if resp == "STCwithout BTO":
            print("STC without BTO", order["Symbol"], order["Date"])

tracker.portfolio['spread'] = 100*(tracker.portfolio['price_actual_bid']-tracker.portfolio['Price-actual'])/tracker.portfolio['Price-actual']
# tracker.portfolio = tracker.portfolio[tracker.portfolio['spread'].abs()<15]
# tracker.portfolio['ask'] = tracker.portfolio['Price-actual']
# tracker.portfolio['Price-actual']  = tracker.portfolio['bid']
tracker.portfolio.to_csv(tracker.portfolio_fname, index=False)



