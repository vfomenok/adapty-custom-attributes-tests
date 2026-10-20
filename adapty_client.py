
"""Thin HTTP client for the Adapty Server-side API v2 (profile endpoints only)."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.adapty.io/api/v2/server-side-api"
PROFILE_PATH = "/profile/"

# Sentinel that lets tests send a body without the "custom_attributes" key at all.
OMIT = object()


class AdaptyClient:
    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
        )
        # Retry only on rate limiting and network errors. 5xx responses are NOT retried,
        # so that server errors stay visible to the tests instead of being hidden.
        retry = Retry(
            total=5,
            status_forcelist=[429],
            allowed_methods=None,
            backoff_factor=1,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    @property
    def profile_url(self) -> str:
        return self.base_url + PROFILE_PATH

    @staticmethod
    def identity_headers(
        customer_user_id: str | None = None, profile_id: str | None = None
    ) -> dict[str, str]:
        headers = {}
        if customer_user_id is not None:
            headers["adapty-customer-user-id"] = customer_user_id
        if profile_id is not None:
            headers["adapty-profile-id"] = profile_id
        return headers

    def create_profile(self, customer_user_id: str, device_id: str) -> requests.Response:
        return self.session.post(
            self.profile_url,
            headers=self.identity_headers(customer_user_id=customer_user_id),
            json={"installation_meta": {"device_id": device_id}},
            timeout=self.timeout,
        )

    def get_profile(self, **identity: str) -> requests.Response:
        return self.session.get(
            self.profile_url, headers=self.identity_headers(**identity), timeout=self.timeout
        )

    def delete_profile(self, **identity: str) -> requests.Response:
        return self.session.delete(
            self.profile_url, headers=self.identity_headers(**identity), timeout=self.timeout
        )

    def update_profile(
        self, body: Any, headers: dict[str, str] | None = None, **identity: str
    ) -> requests.Response:
        """Send PATCH /profile/ with an arbitrary JSON body (also used for invalid payloads)."""
        return self.session.patch(
            self.profile_url,
            headers={**self.identity_headers(**identity), **(headers or {})},
            json=body,
            timeout=self.timeout,
        )

    def set_custom_attributes(self, attributes: Any = OMIT, **identity: str) -> requests.Response:
        body = {} if attributes is OMIT else {"custom_attributes": attributes}
        return self.update_profile(body, **identity)
