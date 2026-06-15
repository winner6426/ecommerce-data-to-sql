from __future__ import annotations
from typing import Any
import requests

from .config import DEFAULT_TIMEOUT_SECONDS, HEADERS


class ChototClient:

    def __init__(
        self,
        session: requests.Session | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.session = session or requests.Session()
        self.headers = headers or HEADERS
        self.timeout = timeout

    def get_ad_ids(
        self,
        category_id: int,
        page: int,
        region: int | None,
        limit: int,
    ) -> list[int]:
        offset = page * limit
        params = {"cg": category_id, "o": offset, "limit": limit}
        if region is not None:
            params["region"] = region
        response = self.session.get(
            "https://gateway.chotot.com/v1/public/ad-listing",
            params=params,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status() #Nếu bị lỗi thì báo về
        return [ad["list_id"] for ad in response.json().get("ads", []) if "list_id" in ad] 

    def crawl_detail(self, ad_id: str | int) -> dict[str, Any]:
        url = f"https://gateway.chotot.com/v1/public/ad-listing/{ad_id}"
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


_DEFAULT_CLIENT = ChototClient()


def get_ad_ids(category_id: int, page: int, region: int | None, limit: int) -> list[int]:
    return _DEFAULT_CLIENT.get_ad_ids(category_id, page, region, limit)


def crawl_detail(ad_id: str | int) -> dict[str, Any]:
    return _DEFAULT_CLIENT.crawl_detail(ad_id)
