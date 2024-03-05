"""BaseClient class for the TradeStation API."""
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Coroutine, Mapping, Optional, Union
import requests
from httpx import Client, Response

AUTH_ENDPOINT = "https://signin.tradestation.com/authorize"
TOKEN_ENDPOINT = "https://signin.tradestation.com/oauth/token"  # nosec - This isn't a hardcoded password.
AUDIENCE_ENDPOINT = "https://api.tradestation.com/v3"
PAPER_ENDPOINT = "https://sim-api.tradestation.com/v3"


@dataclass
class BaseClient(ABC):
    """
    Tradestation API Client Class.

    Implements OAuth Authorization Code Grant workflow, handles configuration,
    and state management, adds token for authenticated calls, and performs requests
    to the TradeStation API.

    Attributes:
        client_id (str): The client ID for authentication.
        client_secret (str): The client secret for authentication.
        paper_trade (bool): Flag to determine if the instance is for paper trading. Default is True.
        _logged_in (bool): Internal flag to track login status. Automatically initialized to False.
        _auth_state (bool): Internal flag to track authentication state. Automatically initialized to False.
        _access_token (Optional[str]): The access token for authentication. Initialized to None.
        _refresh_token (Optional[str]): The refresh token for authentication. Initialized to None.
        _access_token_expires_in (int): Time in seconds until the access token expires. Initialized to 0.
        _access_token_expires_at (float): Timestamp when the access token will expire. Initialized to 0.0.
        _base_resource (str): The base API endpoint for requests.
    """

    client_id: str
    client_secret: str
    paper_trade: bool = field(default=True)
    _logged_in: bool = field(init=False, default=False)
    _auth_state: bool = field(init=False, default=False)
    _access_token: Optional[str] = field(default=None)
    _refresh_token: Optional[str] = field(default=None)
    _access_token_expires_in: int = field(default=0)
    _access_token_expires_at: float = field(default=0.0)
    _token_read_func: Optional[Callable] = field(default=None)
    _token_update_func: Optional[Callable] = field(default=None)

    def __post_init__(self) -> None:
        """Init the base resource field."""
        self._base_resource = PAPER_ENDPOINT if self.paper_trade else AUDIENCE_ENDPOINT
        self._token_read_func = self._token_read if self._token_read_func is None else self._token_read_func
        self._token_update_func = self._token_save if self._token_update_func is None else self._token_update_func

    @abstractmethod
    def _delete_request(
        self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Union[Response, Coroutine[Any, Any, Response]]:
        """Submit a delete request to TradeStation."""
        pass

    @abstractmethod
    def _get_request(
        self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> Union[Response, Coroutine[Any, Any, Response]]:
        """Submit a get request to TradeStation."""
        pass

    @abstractmethod
    def _post_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> Union[Response, Coroutine[Any, Any, Response]]:
        """Submit a post request to TradeStation."""
        pass

    @abstractmethod
    def _put_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> Union[Response, Coroutine[Any, Any, Response]]:
        """Submit a put request to TradeStation."""
        pass

    def __repr__(self) -> str:
        """Define the string representation of our TradeStation Class instance.

        Returns:
        ----
        (str): A string representation of the client.
        """
        return f"<TradeStation Client (logged_in={self._logged_in}, authorized={self._auth_state})>"

    def _api_endpoint(self, url: str) -> str:
        """Create an API URL.

        Overview:
        ----
        Convert relative endpoint (e.g., 'quotes') to full API endpoint.

        Arguments:
        ----
        url (str): The URL that needs conversion to a full endpoint URL.

        Returns:
        ---
        (str): A full URL.
        """
        # paper trading uses a different base url compared to regular trading.

        return f"{self._base_resource}/{url}"

    def _grab_refresh_token(self) -> bool:
        """Refresh the current access token if it's expired.

        Returns:
        ----
        (bool): `True` if grabbing the refresh token was successful. `False` otherwise.
        """
        # Build the parameters of our request.
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }

        # Make a post request to the token endpoint.
        with Client() as client:
            response: Response = client.post(
                url=TOKEN_ENDPOINT,
                data=data,
            )
        print('refreshed token')
        # Save the token if the response was okay.
        if response.status_code == 200:
            self._token_save(response=response.json())
            return True
        else:
            return False

    def _token_save(self, response: dict) -> bool:
        """Save an access token or refresh token.

        Overview:
        ----
        Parses an access token from the response of a POST request and saves it
        in the state dictionary for future use. Additionally, it will store the
        expiration time and the refresh token.

        Arguments:
        ----
        response (requests.Response): A response object recieved from the `token_refresh` or `_grab_access_token`
            methods.

        Returns:
        ----
        (bool): `True` if saving the token was successful. `False` otherwise.
        """
        if self._update_token_variables(response):
            filename = "ts_state.json"

            state = {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "access_token_expires_at": self._access_token_expires_at,
                "access_token_expires_in": self._access_token_expires_in,
            }

            with open(file=filename, mode="w+") as state_file:
                json.dump(obj=state, fp=state_file, indent=4)

            return True

        return False

    def _token_read(self) -> bool:
        """Read in a token from file.

        Returns:
            bool: Success / Failure
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))
        filename = "ts_state.json"
        file_path = os.path.join(dir_path, filename)
        state: Optional[dict] = None

        with open(file=file_path, mode="r") as state_file:
            state |= json.load(fp=state_file)

        if isinstance(state, dict):
            self._access_token = state.get("access_token")
            self._refresh_token = state.get("refresh_token")
            self._access_token_expires_in = state.get("access_token_expires_at", 0)
            self._access_token_expires_at = state.get("access_token_expires_in", 0)
            return True

        return False

    def _update_token_variables(self, response: dict) -> bool:
        """Update the local variable from a given token response.

        Args:
            response (dict): Token response message

        Returns:
            bool: Success / Failure
        """
        # Save the access token.
        if "access_token" in response:
            self._access_token = response["access_token"]
        else:
            return False

        # If there is a refresh token then grab it.
        if "refresh_token" in response:
            self._refresh_token = response["refresh_token"]

        # Set the login state.
        self._logged_in = True

        # Store token expiration time.
        self._access_token_expires_in = response["expires_in"]
        self._access_token_expires_at = time.time() + int(response["expires_in"])

        return True

    def _token_seconds(self) -> int:
        """Calculate when the token will expire.

        Overview:
        ----
        Return the number of seconds until the current access token or refresh token
        will expire. The default value is access token because this is the most commonly used
        token during requests.

        Returns:
        ----
        (int): The number of seconds till expiration
        """
        # Calculate the token expire time.
        token_exp = time.time() >= self._access_token_expires_at
        token_time = int(self._access_token_expires_at - time.time())
        # if the time to expiration is less than or equal to 0, return 0.
        return 0 if not self._refresh_token or token_exp else token_time

    def _token_validation(self, nseconds: int = 5) -> None:
        """Validate the Access Token.

        Overview:
        ----
        Verify the current access token is valid for at least N seconds, and
        if not then attempt to refresh it. Can be used to assure a valid token
        before making a call to the Tradestation API.

        Arguments:
        ----
        nseconds (int): The minimum number of seconds the token has to be valid for before
            attempting to get a refresh token.
        """
        if self._token_seconds() < nseconds:
            self._grab_refresh_token()

    #############
    # Brokerage #
    #############

    def get_accounts(self, user_id: str) -> Response | Awaitable[Response]:
        """Grabs all the accounts associated with the User.

        Arguments:
        ----
        user_id (str): The Username of the account holder.

        Returns:
        ----
        (dict): All the user accounts.
        """
        # validate the token.[]
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url="users/{username}/accounts".format(username=user_id))

        # define the arguments
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def get_wallets(self, account_id: str) -> Response | Awaitable[Response]:
        """Grabs a A valid crypto Account ID for the authenticated user.

        Arguments:
        ----
        user_id (str): The Username of the account holder.

        Returns:
        ----
        (dict): All the user accounts.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url=f"brokerage/accounts/{account_id}/wallets")

        # define the arguments
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def get_balances(self, account_keys: list[str | int]) -> Response | Awaitable[Response]:
        """Grabs all the balances for each account provided.

        Args:
        ----
        account_keys (List[str]): A list of account numbers. Can only be a max
            of 25 account numbers

        Raises:
        ----
        ValueError: If the list is more than 25 account numbers will raise an error.

        Returns:
        ----
        dict: A list of account balances for each of the accounts.
        """
        # validate the token.
        self._token_validation()

        # argument validation.
        account_keys_str = ""
        if not account_keys or not isinstance(account_keys, list):
            raise ValueError("You must pass a list with at least one account for account keys.")
        elif len(account_keys) > 0 and len(account_keys) <= 25:
            account_keys_str = ",".join(map(str, account_keys))
        elif len(account_keys) > 25:
            raise ValueError("You cannot pass through more than 25 account keys.")

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"brokerage/accounts/{account_keys_str}/balances")

        # define the arguments
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def get_balances_bod(self, account_keys: list[str | int]) -> Response | Awaitable[Response]:
        """Grabs the beginning of day balances for each account provided.

        Args:
        ----
        account_keys (List[str]): A list of account numbers. Can only be a max
            of 25 account numbers

        Raises:
        ----
        ValueError: If the list is more than 25 account numbers will raise an error.

        Returns:
        ----
        dict: A list of account balances for each of the accounts.
        """
        # validate the token.
        self._token_validation()

        # argument validation.
        account_keys_str = ""
        if not account_keys or not isinstance(account_keys, list):
            raise ValueError("You must pass a list with at least one account for account keys.")
        elif len(account_keys) > 0 and len(account_keys) <= 25:
            account_keys_str = ",".join(map(str, account_keys))
        elif len(account_keys) > 25:
            raise ValueError("You cannot pass through more than 25 account keys.")

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"brokerage/accounts/{account_keys_str}/bodbalances")

        # define the arguments
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def get_positions(
        self, account_keys: list[str | int], symbols: Optional[list[str]] = None
    ) -> Response | Awaitable[Response]:
        """Grabs all the account positions.

        Arguments:
        ----
        account_keys (List[str]): A list of account numbers..

        symbols (List[str]): A list of ticker symbols, you want to return.

        Raises:
        ----
        ValueError: If the list is more than 25 account numbers will raise an error.

        Returns:
        ----
        dict: A list of account balances for each of the accounts.
        """
        # validate the token.
        self._token_validation()

        # argument validation, account keys.
        account_keys_str = ""
        if not account_keys or not isinstance(account_keys, list):
            raise ValueError("You must pass a list with at least one account for account keys.")
        elif len(account_keys) > 0 and len(account_keys) <= 25:
            account_keys_str = ",".join(map(str, account_keys))
        elif len(account_keys) > 25:
            raise ValueError("You cannot pass through more than 25 account keys.")

        # argument validation, symbols.
        if symbols is None:
            params = {"access_token": self._access_token}

        elif not symbols:
            raise ValueError("You cannot pass through an empty symbols list for the filter.")
        else:
            symbols_formatted = [f"Symbol eq {symbol!r}" for symbol in symbols]
            symbols_str = "or ".join(symbols_formatted)
            params = {"access_token": self._access_token, "$filter": symbols_str}

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"brokerage/accounts/{account_keys_str}/positions")

        return self._get_request(url=url_endpoint, params=params)

    def get_orders(
        self, account_keys: list[str | int], page_size: int = 600, order_ids: Optional[list[str | int]] = None
    ) -> Response | Awaitable[Response]:
        """Grab all the account orders for a list of accounts.

        Overview:
        ----
        This endpoint is used to grab all the order from a list of accounts provided. Additionally,
        each account will only go back 14 days when searching for orders.

        Arguments:
        ----
        account_keys (List[str]): A list of account numbers.

        since (int): Number of days to look back, max is 14 days.

        page_size (int): The page size.

        page_number (int, optional): The page number to return if more than one. Defaults to 0.

        Raises:
        ----
        ValueError: If the list is more than 25 account numbers will raise an error.

        Returns:
        ----
        dict: A list of account balances for each of the accounts.
        """
        # validate the token.
        self._token_validation()

        # argument validation, account keys.
        account_keys_str = ""
        if not account_keys or not isinstance(account_keys, list):
            raise ValueError("You must pass a list with at least one account for account keys.")
        elif len(account_keys) > 0 and len(account_keys) <= 25:
            account_keys_str = ",".join(map(str, account_keys))
        elif len(account_keys) > 25:
            raise ValueError("You cannot pass through more than 25 account keys.")

        # Argument Validation, Order IDs
        if order_ids and len(order_ids) > 0 and len(order_ids) <= 50:
            order_ids_str = f'/{",".join(map(str, order_ids))}'
        elif order_ids and len(order_ids) > 50:
            raise ValueError("You cannot pass through more than 50 Orders.")
        else:
            order_ids_str = ""

        if 600 < page_size < 0 or not isinstance(page_size, int):
            raise ValueError("Page Size must be an integer, [1..600]")

        params = {
            "access_token": self._access_token,
            "pageSize": page_size,
        }

        # define the endpoint.
        url_endpoint = self._api_endpoint(url=f"brokerage/accounts/{account_keys_str}/orders{order_ids_str}")

        return self._get_request(url=url_endpoint, params=params)

    def get_historical_orders(
        self,
        account_keys: list[str | int],
        since: date,
        page_size: int = 600,
        order_ids: Optional[list[str | int]] = None,
    ) -> Response | Awaitable[Response]:
        """Grab all the account orders for a list of accounts.

        Overview:
        ----
        This endpoint is used to grab all the order from a list of accounts provided. Additionally,
        each account will only go back 14 days when searching for orders.

        Arguments:
        ----
        account_keys (List[str]): A list of account numbers.

        since (int): Number of days to look back, max is 14 days.

        page_size (int): The page size.

        page_number (int, optional): The page number to return if more than one. Defaults to 0.

        Raises:
        ----
        ValueError: If the list is more than 25 account numbers will raise an error.

        Returns:
        ----
        dict: A list of account balances for each of the accounts.
        """
        # Argument validation, account keys.
        if not since:
            since = date.today() - timedelta(days=90)

        if 600 < page_size < 0 or not isinstance(page_size, int):
            raise ValueError("Page Size must be an integer, [1..600]")

        account_keys_str = ""
        if not account_keys or not isinstance(account_keys, list):
            raise ValueError("You must pass a list with at least one account for account keys.")
        elif len(account_keys) > 0 and len(account_keys) <= 25:
            account_keys_str = ",".join(map(str, account_keys))
        elif len(account_keys) > 25:
            raise ValueError("You cannot pass through more than 25 account keys.")

        # Argument Validation, Order IDs
        if order_ids and len(order_ids) > 0 and len(order_ids) <= 50:
            order_ids_str = f'/{",".join(map(str, order_ids))}'
        elif order_ids and len(order_ids) > 50:
            raise ValueError("You cannot pass through more than 50 Orders.")
        else:
            order_ids_str = ""

        # Argument Validation, Since
        if since < date.today() - timedelta(days=90):
            raise ValueError("Limited to 90 days prior to the current date.")

        # validate the token.
        self._token_validation()

        params = {
            "access_token": self._access_token,
            "since": since,
            "pageSize": page_size,
        }

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"brokerage/accounts/{account_keys_str}/historicalorders{order_ids_str}")

        return self._get_request(url=url_endpoint, params=params)

    ###############
    # Market Data #
    ###############

    def get_bars(
        self,
        symbol: str,
        interval: int,
        unit: str,
        barsback: int,
        firstdate: datetime,
        lastdate: datetime,
        sessiontemplate: str,
    ) -> Response | Awaitable[Response]:
        """Grabs all the accounts associated with the User.

        Arguments:
        ----
        user_id (str): The Username of the account holder.

        Returns:
        ----
        (dict): All the user accounts.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"marketdata/barcharts/{symbol}")

        # define the arguments
        params = {
            "access_token": self._access_token,
            "interval": interval,
            "unit": unit,
            "barsback": barsback,
            "firstdate": firstdate,
            "lastdate": lastdate,
            "sessiontemplate": sessiontemplate,
        }

        return self._get_request(url=url_endpoint, params=params)

    def get_crypto_symbol_names(self) -> Response | Awaitable[Response]:
        """Fetch all crypto Symbol Names information."""
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url='marketdata/symbollists/cryptopairs/symbolnames"')

        # define the arguments
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def get_symbol_details(self, symbols: list[str]) -> Response | Awaitable[Response]:
        """Grabs the info for a particular symbol.

        Arguments:
        ----
        symbol (str): A ticker symbol.

        Raises:
        ----
        ValueError: If no symbol is provided will raise an error.

        Returns:
        ----
        dict: A dictionary containing the symbol info.
        """
        # validate the token.
        self._token_validation()

        if symbols is None:
            raise ValueError("You must pass through a symbol.")
        elif 0 > len(symbols) > 50:
            raise ValueError("You may only send [1..50] symbols per request.")

        # define the endpoint.
        url_endpoint = self._api_endpoint(f'marketdata/symbols/{",".join(symbols)}')

        # define the arguments.
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def get_option_expirations(
        self, underlying: str, strike_price: Optional[float] = None
    ) -> Response | Awaitable[Response]:
        """Get the available option contract expiration dates for the underlying symbol.

        Args:
            underlying (str): The symbol for the underlying security on which the option contracts are based.
                The underlying symbol must be an equity or index.
            strike_price (Optional[float], optional): Strike price. If provided,
                only expirations for that strike price will be returned. Defaults to None.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"marketdata/options/expirations/{underlying}")

        # define the arguments
        params = {"access_token": self._access_token, "strikePrice": strike_price}

        return self._get_request(url=url_endpoint, params=params)

    def get_option_risk_reward(self, price: float, legs: list[dict[str, Any]]) -> Response | Awaitable[Response]:
        """Analyze the risk vs. reward of a potential option trade.

        This endpoint is not applicable for option spread types with different expirations,
        such as Calendar and Diagonal.

        Args:
            price (float): The quoted price for the option spread trade.
            legs (list[dict[str, Any]]): The legs of the option spread trade.
                If more than one leg is specified, the expiration dates must all be the same.
                In addition, leg symbols must be of type stock, stock option, or index option.

        Example Usage:
        ```
        legs = [
                {
                    "Symbol": "string",
                    "Quantity": 0,
                    "TradeAction": "BUY"
                }
            ]

        client = get_option_risk_reward(4.20, legs)
        ```
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint("marketdata/options/riskreward")

        # define the arguments
        params = {
            "access_token": self._access_token,
        }

        payload = {"SpreadPrice": price, "Legs": legs}

        return self._post_request(url=url_endpoint, params=params, data=payload)

    def get_option_spread_types(self) -> Response | Awaitable[Response]:
        """Get the available spread types for option chains."""
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint("marketdata/options/spreadtypes")

        # define the arguments
        params = {
            "access_token": self._access_token,
        }

        return self._get_request(url=url_endpoint, params=params)

    def get_option_strikes(
        self,
        underlying: str,
        spreadType: Optional[str] = None,
        strikeInterval: Optional[int] = None,
        expiration: Optional[datetime] = None,
        expiration2: Optional[datetime] = None,
    ) -> Response | Awaitable[Response]:
        """Get the available strike prices for a spread type and expiration date.

        Args:
            underlying (str): The symbol for the underlying security on which the option contracts are based.
                The underlying symbol must be an equity or index.
            spreadType (Optional[str], optional): The name of the spread type to get the strikes for.
                This value can be obtained from the Get Option Spread Types endpoint.. Defaults to None.
            strikeInterval (Optional[int], optional): Specifies the desired interval between the strike prices in a spread.
                It must be greater than or equal to 1. A value of 1 uses consecutive strikes;
                a value of 2 skips one between strikes; and so on. Defaults to None.
            expiration (Optional[datetime], optional): Date on which the option contract expires; must be a valid expiration date.
                Defaults to the next contract expiration date.. Defaults to None.
            expiration2 (Optional[datetime], optional): Second contract expiration date required for
                Calendar and Diagonal spreads. Defaults to None.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint("marketdata/options/strikes/{underlying}")

        # define the arguments
        params = {
            "access_token": self._access_token,
        }

        if spreadType:
            params["spreadType"] = spreadType
        if strikeInterval:
            params["strikeInterval"] = str(strikeInterval)
        if expiration:
            params["expiration"] = expiration.strftime("%m-%d-%Y")
        if expiration2:
            params["expiration2"] = expiration2.strftime("%m-%d-%Y")

        return self._get_request(url=url_endpoint, params=params)

    def get_quote_snapshots(self, symbols: list[str]) -> Response | Awaitable[Response]:
        """Fetch a full snapshot of the latest Quote for the given Symbols.

        For realtime Quote updates, users should use the Quote Stream endpoint.

        Args:
            symbols (list[str]): List of valid symbols. No more than 100 symbols per request.

        Raises:
            ValueError: A minimum of 1 and no more than 100 symbols per request.
        """
        # validate parameters
        if 0 > len(symbols) > 100:
            raise ValueError("A minimum of 1 and no more than 100 symbols per request.")
        else:
            symbols_str = ",".join(symbols)

        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"marketdata/quotes/{symbols_str}")

        # define the arguments
        params = {
            "access_token": self._access_token,
        }

        return self._get_request(url=url_endpoint, params=params)

    
    def stream_option_chain(self, ticker: str, expdate: str=None) -> Response | Awaitable[Response]:
        """Submit a list of orders.

        Arguments:
        ----
        orders (List[dict]): A list of orders to submit.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url=f"marketdata/stream/options/chains/{ticker}")

        # define the arguments.
        params = {
             "content-type": "application/json",
             "Authorization": 'Bearer '+ self._access_token}
        if expdate:
            data = {"expdate": expdate}
            return requests.request("GET", url_endpoint, json=data, headers=params, stream=True)
        else:            
            return requests.request("GET", url_endpoint, headers=params, stream=True)
    
    ###################
    # Order Execution #
    ###################

    def confirm_order(self, order_request: dict) -> Response | Awaitable[Response]:
        """Return estimated cost and commission information for an order without the order actually being placed.

        Request valid for Market, Limit, Stop Market, Stop Limit, Options, and Order Sends Order (OSO) order types.
        All Crypto market orders, excluding USDCUSD, must have Day duration (TimeInForce).
        The fields that are returned in the response depend on the order type.
        https://api.tradestation.com/docs/specification#tag/Order-Execution/operation/ConfirmOrder.

        Args:
            order_request (dict): Order Request
        """
        # Validate inputs.
        if isinstance(order_request, dict):
            payload = order_request
        else:
            raise ValueError("Invalid order request type.")

        # Validate the token.
        self._token_validation()

        # Define the endpoint.
        url_endpoint = self._api_endpoint(url="orderexecution/orderconfirm")

        # Define the arguments.
        params = {"access_token": self._access_token}

        return self._post_request(url=url_endpoint, params=params, data=payload)

    def confirm_group_order(self, orders: list[dict], type: str) -> Response | Awaitable[Response]:
        """Create an Order Confirmation for a group order.

        Request valid for all account types. Request valid for Order Cancels Order (OCO)
        and Bracket (BRK) order types as well as grouped orders of other types (NORMAL).
        All Crypto market orders, excluding USDCUSD, must have Day duration (TimeInForce).

        Arguments:
        ----
        orders (List[dict]): A list of orders to confirm.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url="orderexecution/ordergroupconfirm")

        # define the arguments.
        params = {"access_token": self._access_token}

        data = {"Type": type, "Orders": orders}

        return self._post_request(url=url_endpoint, params=params, data=data)

    def place_group_order(self, orders: dict) -> Response | Awaitable[Response]:
        """Submit a list of orders.

        Arguments:
        ----
        orders (List[dict]): A list of orders to submit.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url="orderexecution/ordergroups")

        # define the arguments.
        params = {
             "content-type": "application/json",
             "Authorization": 'Bearer '+ self._access_token}

        return requests.request("POST", url_endpoint, json=orders, headers=params)

    def place_order(self, order: dict) -> Response | Awaitable[Response]:
        """Submit an order.

        Arguments:
        ----
        order (dict): A dictionary for order.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(url="orderexecution/orders")

        # define the arguments.
        params = {
             "content-type": "application/json",
             "Authorization": 'Bearer '+ self._access_token}

        return requests.request("POST", url_endpoint, json=order, headers=params)

    def replace_order(self, order_id: str | int, new_order: dict) -> Response | Awaitable[Response]:
        """Replace an order.

        Arguments:
        ----
        order_id (str): An order id.

        order (dict): A dictionary for order.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"orderexecution/orders/{order_id}")

        # define the arguments.
        params = {"access_token": self._access_token}

        return self._put_request(url=url_endpoint, params=params, data=new_order)

    def cancel_order(self, order_id: str) -> Response | Awaitable[Response]:
        """Cancel an active order. Request valid for all account types.

        Args:
            order_id (str): Order ID to cancel. Equity, option or future orderIDs should not include dashes
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint(f"orderexecution/orders/{order_id}")

        # define the arguments.
        params = {"access_token": self._access_token}

        return self._delete_request(url=url_endpoint, params=params)

    def get_activation_triggers(self) -> Response | Awaitable[Response]:
        """
        To place orders with activation triggers, a valid TriggerKey must be sent with the order.

        This resource provides the available trigger methods with their corresponding key.
        """
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint("orderexecution/activationtriggers")

        # define the arguments.
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    def available_routes(self) -> Response | Awaitable[Response]:
        """Return a list of valid routes that a client can specify when posting an order."""
        # validate the token.
        self._token_validation()

        # define the endpoint.
        url_endpoint = self._api_endpoint("orderexecution/routes")

        # define the arguments.
        params = {"access_token": self._access_token}

        return self._get_request(url=url_endpoint, params=params)

    # def stream_quotes_changes(self, symbols=None):
    #     """Streams quote changes for a list of symbols.

    #     Arguments:
    #     ----
    #     symbol (List[str]): A list of ticker symbols.

    #     Raises:
    #     ----
    #     ValueError: If no symbol is provided will raise an error.

    #     Returns:
    #     ----
    #     (dict): A dictionary containing the symbol quotes.
    #     """

    #     # validate the token.
    #     self._token_validation()

    #     if symbols is None:
    #         raise ValueError("You must pass through at least one symbol.")

    #     symbols = ','.join(symbols)

    #     # define the endpoint.
    #     url_endpoint = self._api_endpoint(
    #         url='stream/quote/changes/{symbols}'.format(symbols=symbols))

    #     # define the headers
    #     headers = {
    #         'Accept': 'application/vnd.tradestation.streams+json'
    #     }

    #     # define the arguments.
    #     params = {
    #         'access_token': self._access_token
    #     }

    #     return self._handle_requests(
    #         url=url_endpoint,
    #         method='get',
    #         headers=headers,
    #         params=params,
    #         stream=True,
    #     )

    # def stream_bars_start_date(self, symbol: str, interval: int, unit: str, start_date: str, session: str) -> Response:
    #     """Stream bars for a certain data range.

    #     Arguments:
    #     ----
    #     symbol (str): A ticker symbol to stream bars.

    #     interval (int): The size of the bar.

    #     unit (str): The frequency of the bar.

    #     start_date (str): The start point of the streaming.

    #     session (str): Defines whether you want bars from post, pre, or current market.

    #     Raises:
    #     ----
    #     ValueError:

    #     Returns:
    #     ----
    #     (dict): A dictionary of quotes.
    #     """

    #     # ['USEQPre','USEQPost','USEQPreAndPost','Default']

    #     # validate the token.
    #     self._token_validation()

    #     if symbol is None:
    #         raise ValueError("You must pass through one symbol.")

    #     if unit not in ["Minute", "Daily", "Weekly", "Monthly"]:
    #         raise ValueError(
    #             'The value you passed through for `unit` is incorrect,
    # it must be one of the following: ["Minute", "Daily", "Weekly", "Monthly"]')

    #     if interval != 1 and unit in {"Daily", "Weekly", "Monthly"}:
    #         raise ValueError(
    #             "The interval must be one for daily, weekly or monthly.")
    #     elif interval > 1440:
    #         raise ValueError("Interval must be less than or equal to 1440")

    #     # define the endpoint.
    #     url_endpoint = self._api_endpoint(
    #         url='stream/barchart/{symbol}/{interval}/{unit}/{start_date}'.format(
    #             symbol=symbol,
    #             interval=interval,
    #             unit=unit,
    #             start_date=start_date
    #         )
    #     )

    #     # define the arguments.
    #     params = {
    #         'access_token': self._access_token,
    #         'sessionTemplate': session
    #     }

    #     return self._handle_requests(
    #         url=url_endpoint, method='get', params=params, stream=True
    #     )

    # def stream_bars_date_range(self, symbol: str, interval: int, unit: str, start_date: str,
    # end_date: str, session: str) -> Response:
    #     """Stream bars for a certain data range.

    #     Arguments:
    #     ----
    #     symbol (str): A ticker symbol to stream bars.

    #     interval (int): The size of the bar.

    #     unit (str): The frequency of the bar.

    #     start_date (str): The start point of the streaming.

    #     end_date (str): The end point of the streaming.

    #     session (str): Defines whether you want bars from post, pre, or current market.

    #     Raises:
    #     ----
    #     ValueError:

    #     Returns:
    #     ----
    #     (dict): A dictionary of quotes.
    #     """

    #     # validate the token.
    #     self._token_validation()

    #     # validate the symbol
    #     if symbol is None:
    #         raise ValueError("You must pass through one symbol.")

    #     # validate the unit
    #     if unit not in ["Minute", "Daily", "Weekly", "Monthly"]:
    #         raise ValueError(
    #             'The value you passed through for `unit` is incorrect,
    # it must be one of the following: ["Minute", "Daily", "Weekly", "Monthly"]')

    #     # validate the interval.
    #     if interval != 1 and unit in {"Daily", "Weekly", "Monthly"}:
    #         raise ValueError(
    #             "The interval must be one for daily, weekly or monthly.")
    #     elif interval > 1440:
    #         raise ValueError("Interval must be less than or equal to 1440")

    #     # validate the session.
    #     if session is not None and session not in ['USEQPre', 'USEQPost', 'USEQPreAndPost', 'Default']:
    #         raise ValueError(
    #             'The value you passed through for `session` is incorrect, it must be one of the following:
    # ["USEQPre","USEQPost","USEQPreAndPost","Default"]')

    #     # validate the START DATE.
    #     if isinstance(start_date, (datetime.datetime, datetime.date)):
    #         start_date_iso = start_date.isoformat()
    #     elif isinstance(start_date, str):
    #         datetime_parsed = parse(start_date)
    #         start_date_iso = datetime_parsed.isoformat()

    #     # validate the END DATE.
    #     if isinstance(end_date, datetime.datetime) or isinstance(start_date, datetime.date):
    #         end_date_iso = end_date.isoformat()

    #     elif isinstance(end_date, str):
    #         datetime_parsed = parse(end_date)
    #         end_date_iso = datetime_parsed.isoformat()

    #     # define the endpoint.
    #     url_endpoint = self._api_endpoint(url='stream/barchart/{symbol}/{interval}/{unit}/{start}/{end}'.format(
    #         symbol=symbol,
    #         interval=interval,
    #         unit=unit,
    #         start=start_date_iso,
    #         end=end_date_iso
    #     )
    #     )

    #     # define the arguments.
    #     params = {
    #         'access_token': self._access_token,
    #         'sessionTemplate': session
    #     }

    #     return self._handle_requests(
    #         url=url_endpoint, method='get', params=params, stream=True
    #     )

    # def stream_bars_back(self, symbol: str, interval: int, unit: str, bar_back: int, last_date: str, session: str):
    #     """Stream bars for a certain number of bars back.

    #     Arguments:
    #     ----
    #     symbol (str): A ticker symbol to stream bars.

    #     interval (int): The size of the bar.

    #     unit (str): The frequency of the bar.

    #     bar_back (str): The number of bars back.

    #     last_date (str): The date from which to start going back.

    #     session (str): Defines whether you want bars from post, pre, or current market.

    #     Raises:
    #     ----
    #     ValueError:

    #     Returns:
    #     ----
    #     (dict): A dictionary of quotes.
    #     """

    #     # validate the token.
    #     self._token_validation()

    #     # validate the symbol
    #     if symbol is None:
    #         raise ValueError("You must pass through one symbol.")

    #     # validate the unit
    #     if unit not in ["Minute", "Daily", "Weekly", "Monthly"]:
    #         raise ValueError(
    #             'The value you passed through for `unit` is incorrect,
    # it must be one of the following: ["Minute", "Daily", "Weekly", "Monthly"]')

    #     # validate the interval.
    #     if interval != 1 and unit in {"Daily", "Weekly", "Monthly"}:
    #         raise ValueError(
    #             "The interval must be one for daily, weekly or monthly.")
    #     elif interval > 1440:
    #         raise ValueError("Interval must be less than or equal to 1440")

    #     # validate the session.
    #     if session is not None and session not in ['USEQPre', 'USEQPost', 'USEQPreAndPost', 'Default']:
    #         raise ValueError(
    #             'The value you passed through for `session` is incorrect, it must be one of the following:
    # ["USEQPre","USEQPost","USEQPreAndPost","Default"]')

    #     if bar_back > 157600:
    #         raise ValueError("`bar_back` must be less than or equal to 157600")

    #     if isinstance(last_date, datetime.datetime):
    #         last_date_iso = last_date.isoformat()

    #     elif isinstance(last_date, str):
    #         datetime_parsed = parse(last_date)
    #         last_date_iso = datetime_parsed.isoformat()

    #     # Define the endpoint.
    #     url_endpoint = self._api_endpoint(
    #         url='stream/barchart/{symbol}/{interval}/{unit}/{bar_back}/{last_date}'.format(
    #             symbol=symbol,
    #             interval=interval,
    #             unit=unit,
    #             bar_back=bar_back,
    #             last_date=last_date_iso
    #         )
    #     )

    #     # define the arguments.
    #     params = {
    #         'access_token': self._access_token,
    #         'sessionTemplate': session
    #     }

    #     return self._handle_requests(
    #         url=url_endpoint, method='get', params=params, stream=True
    #     )

    # def stream_bars_days_back(self, symbol: str, interval: int, unit: str, bar_back: int, last_date: str, session: str):
    #     """Stream bars for a certain number of days back.

    #     Arguments:
    #     ----
    #     symbol (str): A ticker symbol to stream bars.

    #     interval (int): The size of the bar.

    #     unit (str): The frequency of the bar.

    #     bar_back (str): The number of bars back.

    #     last_date (str): The date from which to start going back.

    #     session (str): Defines whether you want bars from post, pre, or current market.

    #     Raises:
    #     ----
    #     ValueError:

    #     Returns:
    #     ----
    #     (dict): A dictionary of quotes.
    #     """

    #     # validate the token.
    #     self._token_validation()

    #     # validate the symbol
    #     if symbol is None:
    #         raise ValueError("You must pass through one symbol.")

    #     # validate the unit
    #     if unit not in ["Minute", "Daily", "Weekly", "Monthly"]:
    #         raise ValueError(
    #             'The value you passed through for `unit` is incorrect, it must be one of the following:
    # ["Minute", "Daily", "Weekly", "Monthly"]')

    #     # validate the interval.
    #     if interval != 1 and unit in {"Daily", "Weekly", "Monthly"}:
    #         raise ValueError(
    #             "The interval must be one for daily, weekly or monthly.")
    #     elif interval > 1440:
    #         raise ValueError("Interval must be less than or equal to 1440")

    #     # validate the session.
    #     if session is not None and session not in ['USEQPre', 'USEQPost', 'USEQPreAndPost', 'Default']:
    #         raise ValueError(
    #             'The value you passed through for `session` is incorrect, it must be one of the following:
    # ["USEQPre","USEQPost","USEQPreAndPost","Default"]')

    #     if bar_back > 157600:
    #         raise ValueError("`bar_back` must be less than or equal to 157600")

    #     if isinstance(last_date, datetime.datetime):
    #         last_date_iso = last_date.isoformat()

    #     elif isinstance(last_date, str):
    #         datetime_parsed = parse(last_date)
    #         last_date_iso = datetime_parsed.isoformat()

    #     # define the endpoint.
    #     url_endpoint = self._api_endpoint(
    #         url='stream/barchart/{symbol}/{interval}/{unit}/{bar_back}/{last_date}'.format(
    #             symbol=symbol,
    #             interval=interval,
    #             unit=unit,
    #             bar_back=bar_back,
    #             last_date=last_date_iso
    #         )
    #     )

    #     # Define the arguments.
    #     params = {
    #         'access_token': self._access_token,
    #         'sessionTemplate': session
    #     }

    #     return self._handle_requests(
    #         url=url_endpoint, method='get', params=params, stream=True
    #     )

    # def stream_bars(self, symbol: str, interval: int, bar_back: int):
    #     """Stream bars for a certain symbol.

    #     Arguments:
    #     ----
    #     symbol (str): A ticker symbol to stream bars.

    #     interval (int): The size of the bar.

    #     unit (str): The frequency of the bar.

    #     Raises:
    #     ----
    #     ValueError:

    #     Returns:
    #     ----
    #     (dict): A dictionary of quotes.
    #     """

    #     # validate the token.
    #     self._token_validation()

    #     # validate the symbol
    #     if symbol is None:
    #         raise ValueError("You must pass through one symbol.")

    #     if interval > 64999:
    #         raise ValueError("Interval must be less than or equal to 64999")

    #     if bar_back > 10:
    #         raise ValueError("`bar_back` must be less than or equal to 10")

    #     # define the endpoint.
    #     url_endpoint = self._api_endpoint(
    #         url='stream/tickbars/{symbol}/{interval}/{bar_back}'.format(
    #             symbol=symbol,
    #             interval=interval,
    #             bar_back=bar_back
    #         )
    #     )

    #     # define the arguments.
    #     params = {
    #         'access_token': self._access_token
    #     }

    #     return self._handle_requests(
    #         url=url_endpoint, method='get', params=params, stream=True
    #     )
