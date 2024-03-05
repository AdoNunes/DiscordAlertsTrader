"""
This module defines the AsyncClient class to make asynchronous HTTP requests using the httpx library.

Classes:
    - AsyncClient: Manages asynchronous HTTP requests.
"""
from typing import Any, Mapping, Optional

import httpx

from .base import BaseClient


class AsyncClient(BaseClient):
    """
    AsyncClient Class for making asynchronous HTTP requests.

    This class inherits from the BaseClient class and implements its abstract methods
    for making HTTP DELETE, GET, POST, and PUT requests.
    """

    async def _delete_request(
        self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> httpx.Response:
        if headers is None:
            headers = {}

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=headers, params=params)

        return response

    async def _get_request(
        self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None
    ) -> httpx.Response:
        if headers is None:
            headers = {}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)

        return response

    async def _post_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        if headers is None:
            headers = {}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, params=params, data=data)

        return response

    async def _put_request(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        data: Optional[Mapping[str, Any]] = None,
    ) -> httpx.Response:
        if headers is None:
            headers = {}

        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, params=params, data=data)

        return response

    async def get_accounts(self, user_id: str) -> httpx.Response:
        url, params = self._get_accounts(user_id)
        
        return await self._get_request(url, params)