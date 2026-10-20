"""Makes the pytest-html report readable: human-friendly titles, groups and known-issue notes."""

from __future__ import annotations

import html
import re

import pytest
from pytest_metadata.plugin import metadata_key

from adapty_client import BASE_URL, PROFILE_PATH


def humanize(name: str) -> str:
    """test_key_longer_than_limit_is_rejected -> Key longer than limit is rejected"""
    name = re.sub(r"^test_?", "", name).replace("_", " ").strip()
    return name[:1].upper() + name[1:]


def humanize_class(name: str) -> str:
    """TestKeyValidation -> Key validation"""
    words = re.findall(r"[A-Z][a-z]*|[a-z]+", re.sub(r"^Test", "", name))
    return humanize(" ".join(words).lower())


def pytest_configure(config: pytest.Config) -> None:
    metadata = config.stash[metadata_key]
    metadata["Endpoint"] = f"PATCH {BASE_URL}{PROFILE_PATH}"
    metadata["Docs"] = "https://adapty.io/docs/api-adapty/operations/updateProfile"


def pytest_html_report_title(report) -> None:
    report.title = "Adapty Server-side API: custom attributes"


def pytest_html_results_summary(prefix, summary, postfix) -> None:
    prefix.append(
        "<p><b>How to read:</b> "
        "<b>Passed</b> - API behaves as expected. "
        "<b>Expected failures</b> - known API bugs, see the <i>Known issue</i> column. "
        "<b>Failed</b> or <b>Unexpected passes</b> - API behaviour changed: a regression, "
        "or a known bug was fixed.</p>"
    )


def pytest_html_results_table_header(cells: list[str]) -> None:
    cells.pop()  # drop the empty "Links" column
    cells.insert(1, "<th>Group</th>")
    cells.insert(2, "<th>Check</th>")
    cells.insert(3, "<th>Known issue</th>")


def pytest_html_results_table_row(report, cells: list[str]) -> None:
    cells.pop()
    cells.insert(1, f"<td>{html.escape(getattr(report, 'group', ''))}</td>")
    cells.insert(2, f"<td>{html.escape(getattr(report, 'check', ''))}</td>")
    cells.insert(3, f"<td>{html.escape(getattr(report, 'known_issue', ''))}</td>")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()

    report.group = humanize_class(item.cls.__name__) if item.cls else ""
    check = humanize(item.originalname)
    if hasattr(item, "callspec"):
        check += f" [{item.callspec.id}]"
    report.check = check

    xfail = item.get_closest_marker("xfail")
    report.known_issue = xfail.kwargs.get("reason", "") if xfail else ""
