from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from adapty_client import AdaptyClient

pytest_plugins = ["report_hooks"]

API_KEY_ENV = "ADAPTY_SECRET_API_KEY"


@dataclass(frozen=True)
class Profile:
    customer_user_id: str
    profile_id: str


@pytest.fixture(scope="session")
def api_key() -> str:
    key = os.environ.get(API_KEY_ENV)
    if not key:
        pytest.fail(f"Environment variable {API_KEY_ENV} is not set", pytrace=False)
    return key


@pytest.fixture(scope="session")
def client(api_key: str) -> AdaptyClient:
    return AdaptyClient(api_key)


@pytest.fixture
def profile(client: AdaptyClient) -> Iterator[Profile]:
    """A fresh, empty profile per test; deleted afterwards so tests stay independent."""
    customer_user_id = f"autotest-{uuid.uuid4().hex}"
    response = client.create_profile(customer_user_id, device_id=str(uuid.uuid4()))
    assert response.status_code == 200, f"Failed to create profile: {response.text}"
    data = response.json()["data"]
    assert data["custom_attributes"] == []

    yield Profile(customer_user_id=customer_user_id, profile_id=data["profile_id"])

    client.delete_profile(customer_user_id=customer_user_id)
