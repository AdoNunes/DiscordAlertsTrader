"""
This module defines the Client class, to make synchronous HTTP requests using the httpx library.

Classes:
    - Client: Manages synchronous HTTP requests.
"""

from typing import Any, Mapping, Optional

import httpx

from .base import BaseClient


class Client(BaseClient):
    """
    Client Class for making synchronous HTTP requests.

    This class inherits from the BaseClient class and implements its abstract methods
    for making HTTP DELETE, GET, POST, and PUT requests.
    """

    def _delete_request(
        self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> httpx.Response:
        """
        Submit a DELETE request to a given URL.

        Parameters:
        - url (str): The URL to which the request is sent.
        - params (Optional[dict]): Query parameters to append to the URL.
        - headers (Optional[dict]): Headers to include in the request.

        Returns:
        - httpx.Response: The response received from the server.
        """
        if headers is None:
            headers = {}

        with httpx.Client() as client:
            response = client.delete(url, headers=headers, params=params)

        return response

    def _get_request(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> httpx.Response:
        """
        Submit a GET request to a given URL.

        Parameters:
        - url (str): The URL to which the request is sent.
        - params (Optional[dict]): Query parameters to append to the URL.
        - headers (Optional[dict]): Headers to include in the request.

        Returns:
        - httpx.Response: The response received from the server.
        """
        if headers is None:
            headers = {}

        with httpx.Client() as client:
            response = client.get(url, headers=headers, params=params)

        return response

    def _post_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """
        Submit a POST request to a given URL.

        Parameters:
        - url (str): The URL to which the request is sent.
        - params (Optional[dict]): Query parameters to append to the URL.
        - headers (Optional[dict]): Headers to include in the request.
        - data (Optional[Mapping[str, Any]]): Data payload for the request.

        Returns:
        - httpx.Response: The response received from the server.
        """
        if headers is None:
            headers = {}

        with httpx.Client() as client:
            response = client.post(url, headers=headers, params=params, data=data)

        return response

    def _put_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        """
        Submit a PUT request to a given URL.

        Parameters:
        - url (str): The URL to which the request is sent.
        - params (Optional[dict]): Query parameters to append to the URL.
        - headers (Optional[dict]): Headers to include in the request.
        - data (Optional[Mapping[str, Any]]): Data payload for the request.

        Returns:
        - httpx.Response: The response received from the server.
        """
        if headers is None:
            headers = {}

        with httpx.Client() as client:
            response = client.put(url, headers=headers, params=params, data=data)

        return response
