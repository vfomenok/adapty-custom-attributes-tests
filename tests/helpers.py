from __future__ import annotations

from typing import Any

import requests

MAX_ATTRIBUTES = 30
MAX_KEY_LENGTH = 30
MAX_VALUE_LENGTH = 50


def attrs(**pairs: Any) -> list[dict[str, Any]]:
    """attrs(plan="gold", score=1.5) -> [{"key": "plan", "value": "gold"}, ...]"""
    return [{"key": key, "value": value} for key, value in pairs.items()]


def as_dict(attributes: list[dict[str, Any]]) -> dict[str, Any]:
    """The API does not guarantee ordering, so compare attributes as a key -> value map."""
    return {item["key"]: item["value"] for item in attributes}


def custom_attributes_of(response: requests.Response) -> dict[str, Any]:
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    return as_dict(response.json()["data"]["custom_attributes"])


def assert_validation_error(
    response: requests.Response, source: str, error_code: str | None = None
) -> None:
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["status_code"] == 400
    sources = [error["source"] for error in body["errors"]]
    assert source in sources, f"Expected error for {source!r}, got {body}"
    if error_code is not None:
        assert body["error_code"] == error_code, body
