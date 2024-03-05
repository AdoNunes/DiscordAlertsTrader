"""
This module provides a set of utilities for handling authentication with the TradeStation API.

It includes both synchronous and asynchronous client creation functions and token management utilities.

Functions:
- easy_client(): Easy client initialization either from a token file or by manual flow.
- client_from_access_functions(): Initialize a client using access functions.
- client_from_manual_flow(): Initialize a client by manually completing the OAuth2 flow.
- client_from_token_file(): Initialize a client by reading in a token file.

Example:
```python
from auth import easy_client

client = easy_client("client_key", "client_secret", "http://localhost/callback")
"""

import json
import logging
import os
import secrets
from typing import Any, Callable, Dict, Union
from urllib.parse import parse_qs, urlparse

import httpx

from DiscordAlertsTrader.brokerages.tradestation.client.asynchronous import AsyncClient
from DiscordAlertsTrader.brokerages.tradestation.client.synchronous import Client

AUTH_ENDPOINT = "https://signin.tradestation.com/authorize"
TOKEN_ENDPOINT = "https://signin.tradestation.com/oauth/token"  # nosec - This isn't a hardcoded password
AUDIENCE_ENDPOINT = "https://api.tradestation.com"


def get_logger() -> logging.Logger:
    """Get the logger."""
    return logging.getLogger(__name__)


def __update_token(token_path: str) -> Callable:
    """
    Return a function to update the token information and save it to a file.

    Parameters:
    - token_path (str): The path where the token information will be saved.

    Returns:
    - Callable: A function that takes a token dictionary and saves it to a file.

    Example Usage:
    ```
    update_func = __update_token("path/to/token.json")
    update_func(token_dict)
    ```

    Notes:
    - The returned function will save the token in JSON format.
    """

    def update_token(t: Any) -> None:
        """
        Update the token information and saves it to a file.

        Parameters:
        - t (Any): The token information to be saved. Could be a dictionary, list, or any serializable type.

        Returns:
        - None

        Example Usage:
        ```
        update_token(token_dict)
        ```

        Notes:
        - The function saves the token in JSON format to a file specified by `token_path`.
        - The function uses a logger to log the path to which the token is saved.

        Warnings:
        - The `token_path` and `get_logger()` are assumed to be available in the function's scope.
        """
        get_logger().info("Updating token to file %s", token_path)

        with open(token_path, "w") as f:
            json.dump(t, f, indent=4)

    return update_token


def __token_loader(token_path: str) -> Callable[[], Dict[str, Any]]:
    """
    Return a function to load the token information from a file.

    Parameters:
    - token_path (str): The path from where the token information will be loaded.

    Returns:
    - Callable: A function that loads and returns a token dictionary.

    Example Usage:
    ```
    load_func = __token_loader("path/to/token.json")
    token_dict = load_func()
    ```

    Notes:
    - The returned function will read the token from a JSON file.
    """

    def load_token() -> Any:
        """
        Load the token information from a file and returns it.

        Returns:
        - Any: The token information, typically a dictionary or list, or any deserializable type.

        Example Usage:
        ```
        token_data = load_token()
        ```

        Notes:
        - The function reads the token from a JSON file specified by `token_path`.
        - The function uses a logger to log the path from which the token is loaded.

        Warnings:
        - The `token_path` and `get_logger()` are assumed to be available in the function's scope.

        Raises:
        - FileNotFoundError: If the specified `token_path` does not exist.
        - JSONDecodeError: If the file does not contain valid JSON data.
        """
        get_logger().info("Loading token from file %s", token_path)

        with open(token_path, "rb") as f:
            token_data = f.read()
            return json.loads(token_data.decode())

    return load_token


def easy_client(
    client_key: str, client_secret: str, redirect_uri: str, paper_trade: bool = True, asyncio: bool = False
) -> AsyncClient | Client:
    """
    Initialize and return a client object based on existing token or manual flow.

    Parameters:
    - client_key (str): The client key for authentication.
    - client_secret (str): The client secret for authentication.
    - redirect_uri (str): The redirect URI for OAuth2.
    - paper_trade (bool, optional): Flag to indicate if the client should operate in paper trade mode. Default is True.
    - asyncio (bool, optional): Flag to indicate if the client should be asynchronous. Default is False.

    Returns:
    - AsyncClient | Client: An instance of either the AsyncClient or Client class,
        initialized with the provided tokens and settings.

    Example Usage:
    ```
    client = easy_client("client_key", "client_secret", "http://localhost/callback", paper_trade=True, asyncio=False)
    ```

    Notes:
    - The function will first try to initialize the client using an existing token file.
    - If the token file does not exist, it will proceed with the manual flow.
    """
    logger = get_logger()

    if os.path.isfile("ts_state.json"):
        c = client_from_token_file(client_key, client_secret, paper_trade, asyncio)
        logger.info("Returning client loaded from token file 'ts_state.json'")
    else:
        logger.warning("Failed to find token file 'ts_state.json'")
        c = client_from_manual_flow(client_key, client_secret, redirect_uri, paper_trade, asyncio)
    return c


def client_from_manual_flow(
    client_key: str, client_secret: str, redirect_uri: str, paper_trade: bool = True, asyncio: bool = False
) -> AsyncClient | Client:
    """
    Initialize and return a client object by manually completing the OAuth2 flow.

    Parameters:
    - client_key (str): The client key for authentication.
    - client_secret (str): The client secret for authentication.
    - redirect_uri (str): The redirect URI for OAuth.
    - paper_trade (bool, optional): Flag to indicate if the client should operate in paper trade mode. Default is True.
    - asyncio (bool, optional): Flag to indicate if the client should be asynchronous. Default is False.

    Returns:
    - AsyncClient | Client: An instance of either the AsyncClient or Client class,
        initialized with the provided tokens and settings.

    Example Usage:
    ```
    client = client_from_manual_flow("client_key", "client_secret", "http://localhost:80/", paper_trade=True, asyncio=False)
    ```

    Notes:
    - Follow the printed instructions to visit the authorization URL and paste the full redirect URL.
    - The function will automatically request tokens and initialize the client.
    """
    # Build the Authorization URL
    params = {
        "response_type": "code",
        "client_id": client_key,
        "redirect_uri": redirect_uri,
        "audience": AUDIENCE_ENDPOINT,
        "state": secrets.token_hex(16),  # Ideally, this should be dynamically generated for each request
        "scope": "MarketData ReadAccount Trade Crypto OptionSpreads Matrix openid offline_access profile email",
    }
    url = httpx.get(AUTH_ENDPOINT, params=params).url
    print(f"Please go to this URL to authorize the application: {url}")

    # Obtain Authorization Code from User
    auth_redirect = input("Please enter the full redirect URL you were returned to: ")
    parsed_url = urlparse(auth_redirect)
    query_params = parse_qs(parsed_url.query)
    authorization_code = query_params.get("code", [])[0].strip()

    # Request Tokens Using Authorization Code
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_key,
        "client_secret": client_secret,
        "code": authorization_code,
        "redirect_uri": redirect_uri,
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}
    response: httpx.Response = httpx.post(TOKEN_ENDPOINT, data=payload, headers=headers)

    if response.status_code == httpx._status_codes.codes.BAD_REQUEST:
        print(f"Failed to authorize token. {response.status_code}")
        raise ValueError(f"Failed to authorize token. {response.status_code}")  # Or raise an exception

    token: dict[str, Union[str, int]] = response.json()

    # Update Token State (this function should be defined elsewhere)
    update_token = __update_token("ts_state.json")
    update_token(token)

    # Initialize the Client
    client_object: type[AsyncClient] | type[Client] = AsyncClient if asyncio else Client

    return client_object(
        client_id=client_key,
        client_secret=client_secret,
        paper_trade=paper_trade,
        _access_token=str(token.get("access_token")),
        _refresh_token=str(token.get("refresh_token")),
        _access_token_expires_in=int(token.get("access_token_expires_in", 0)),
        _access_token_expires_at=int(token.get("access_token_expires_at", 0)),
    )


def client_from_token_file(
    client_key: str, client_secret: str, paper_trade: bool = True, asyncio: bool = False
) -> AsyncClient | Client:
    """
    Initialize and return a client object based on a given token file.

    Parameters:
    - client_id (str): The client ID for authentication.
    - client_secret (str): The client secret for authentication.
    - token_path (str): The file location for the token data.
    - paper_trade (bool, optional): Flag to indicate if the client should operate in paper trade mode. Default is True.
    - asyncio (bool, optional): Flag to indicate if the client should be asynchronous. Default is False.

    Returns:
    - AsyncClient | Client: An instance of either the AsyncClient or Client class,
        initialized with the provided tokens and settings.

    Example Usage:
    ```
    client = client_from_token_file("client_id", "client_secret", read_token, paper_trade=True, asyncio=False)
    ```

    Notes:
    - The 'token_read_func' should return a dictionary with the following keys:
        - "access_token": The access token for authentication.
        - "refresh_token": The refresh token for refreshing the access token. (optional)
        - "access_token_expires_in": The lifetime of the access token in seconds. (optional)
        - "access_token_expires_at": The expiration timestamp of the access token. (optional)
    """
    return client_from_access_functions(
        client_key,
        client_secret,
        __token_loader("ts_state.json"),
        __update_token("ts_state.json"),
        paper_trade,
        asyncio,
    )


def client_from_access_functions(
    client_key: str,
    client_secret: str,
    token_read_func: Callable,
    token_update_func: Callable,
    paper_trade: bool = True,
    asyncio: bool = False,
) -> AsyncClient | Client:
    """
    Initialize and return a client object based on the provided access functions and settings.

    Parameters:
    - client_id (str): The client ID for authentication.
    - client_secret (str): The client secret for authentication.
    - token_read_func (callable): A function that returns a dictionary containing token information.
    - token_update_func (callable): A function that takes token data and persists it.
    - paper_trade (bool, optional): Flag to indicate if the client should operate in paper trade mode. Default is True.
    - asyncio (bool, optional): Flag to indicate if the client should be asynchronous. Default is False.

    Returns:
    - AsyncClient | Client: An instance of either the AsyncClient or Client class,
        initialized with the provided tokens and settings.

    Example Usage:
    ```
    def read_token():
        return {
            "access_token": "some_access_token",
            "refresh_token": "some_refresh_token",
            "access_token_expires_in": 3600,
            "access_token_expires_at": 1678900000
        }

    client = client_from_access_functions("client_id", "client_secret", read_token, paper_trade=True, asyncio=False)
    ```

    Notes:
    - The 'token_read_func' should return a dictionary with the following keys:
        - "access_token": The access token for authentication.
        - "refresh_token": The refresh token for refreshing the access token. (optional)
        - "access_token_expires_in": The lifetime of the access token in seconds. (optional)
        - "access_token_expires_at": The expiration timestamp of the access token. (optional)
    """
    token: dict = token_read_func()

    client_object: type[AsyncClient] | type[Client] = AsyncClient if asyncio else Client

    return client_object(
        client_id=client_key,
        client_secret=client_secret,
        paper_trade=paper_trade,
        _access_token=token.get("access_token"),
        _refresh_token=token.get("refresh_token", ""),
        _access_token_expires_in=token.get("access_token_expires_in", 0),
        _access_token_expires_at=token.get("access_token_expires_at", 0),
        _token_read_func=token_read_func,
        _token_update_func=token_update_func,
    )
