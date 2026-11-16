"""Tests for Price Plan (EppHistory) portal download prerequisites."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from custom_components.gng.api import (
    GeorgiaNaturalGasClient,
    GNGError,
)


PRICE_PLAN_CSV = (
    "Bill Date,Budget Billing Installment Amount,Actual Bill Charges,"
    "Monthly Budget Billing Variance,"
    "Total Budget Billing Variance after this Bill is Paid\n"
    "2026/11/03,155.58,85.21,-70.37,653.01\n"
)

BUDGET_PAGE_HTML = (
    "<html><body>"
    '<form method="post" id="TokenForm">'
    '<input type="hidden" name="Token" id="Token" value="page-token-abc" />'
    '<input type="hidden" name="SitePrefix" id="SitePrefix" value="" />'
    "</form>"
    "</body></html>"
)

ERROR_HTML = (
    "<!DOCTYPE html><html><head><title>Error</title></head>"
    "<body><strong>An error has occurred.</strong></body></html>"
)


class FakeResponse:
    """Minimal aiohttp response stand-in."""

    def __init__(
        self,
        *,
        status: int,
        body: str,
        content_type: str,
        path: str,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = {"Content-Type": content_type}
        self.url = SimpleNamespace(path=path)

    async def text(self) -> str:
        return self._body

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args) -> bool:
        return False


class FakeSession:
    """Records GETs and returns scripted responses by URL path."""

    def __init__(self, responses: dict[str, FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict | None]] = []
        self.closed = False

    def get(self, url: str, headers=None):
        path = urlparse(url).path
        self.calls.append((path, headers))
        try:
            return self.responses[path]
        except KeyError as err:
            raise AssertionError(f"Unexpected GET {path}") from err


def test_download_price_plan_visits_budget_page_first() -> None:
    """EppHistory requires warming /BudgetBillingPlan before the CSV export."""

    session = FakeSession(
        {
            "/BudgetBillingPlan": FakeResponse(
                status=200,
                body=BUDGET_PAGE_HTML,
                content_type="text/html; charset=utf-8",
                path="/BudgetBillingPlan",
            ),
            "/EppHistorySpreadsheet": FakeResponse(
                status=200,
                body=PRICE_PLAN_CSV,
                content_type="text/csv; charset=utf-8",
                path="/EppHistorySpreadsheet",
            ),
        }
    )
    client = GeorgiaNaturalGasClient(session, "user", "pass")
    client.authenticated = True
    client.token = "login-token"

    csv_data = asyncio.run(client.download_price_plan_history())

    assert [path for path, _ in session.calls] == [
        "/BudgetBillingPlan",
        "/EppHistorySpreadsheet",
    ]
    assert client.token == "page-token-abc"
    assert csv_data.startswith("Bill Date,")


def test_download_authlink_rejects_html_error_page() -> None:
    """HTML error bodies must not be treated as spreadsheet CSV."""

    session = FakeSession(
        {
            "/EppHistorySpreadsheet": FakeResponse(
                status=200,
                body=ERROR_HTML,
                content_type="text/html; charset=utf-8",
                path="/EppHistorySpreadsheet",
            ),
        }
    )
    client = GeorgiaNaturalGasClient(session, "user", "pass")
    client.authenticated = True
    client.token = "login-token"

    with pytest.raises(GNGError, match="unexpected content type"):
        asyncio.run(
            client.download_authlink_file(
                "/EppHistorySpreadsheet",
                referer="/BudgetBillingPlan",
            )
        )
