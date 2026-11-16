"""Async client for the GNG customer portal."""

import json
import logging
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://myaccount.gng.com"


class GNGError(Exception):
    """Base exception for GNG API errors."""


class GNGAuthenticationError(GNGError):
    """Authentication failed or session expired."""


class GNGConnectionError(GNGError):
    """Communication failure with the GNG portal."""


class TokenParser(HTMLParser):
    """Extract hidden portal configuration fields."""

    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "input":
            return

        attrs = dict(attrs)
        field_id = attrs.get("id")

        if field_id in ("Token", "SitePrefix"):
            self.values[field_id] = attrs.get("value", "")


class GeorgiaNaturalGasClient:
    """Asynchronous client for the GNG customer portal."""

    def __init__(self, session, username, password):
        self.session = session
        self.username = username
        self.password = password
        self.token = None
        self.site_prefix = ""
        self.authenticated = False

    async def initialize(self):
        """Retrieve the login page and initial security token."""

        if not self.session or self.session.closed:
            raise GNGConnectionError("HTTP session is not available.")

        url = urljoin(BASE_URL, "/Login")

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise GNGConnectionError(
                        f"GNG login page returned HTTP {response.status}."
                    )

                html = await response.text()

        except TimeoutError:
            raise GNGConnectionError("GNG login page request timed out.") from None

        except aiohttp.ClientError as err:
            raise GNGConnectionError(
                f"Unable to retrieve GNG login page: {type(err).__name__}."
            ) from None

        parser = TokenParser()
        parser.feed(html)

        self.token = parser.values.get("Token")
        self.site_prefix = parser.values.get("SitePrefix", "")

        if not self.token:
            raise GNGError(
                "Unable to locate the initial security token on /Login."
            )

        _LOGGER.debug("GNG login page initialized.")

    async def login(self):
        """Authenticate with GNG."""

        self.authenticated = False

        if not self.session or self.session.closed:
            raise GNGConnectionError("HTTP session is not available.")

        await self.initialize()

        result = await self.request_broker({
            "Actions": "Login",
            "UserName": self.username,
            "Password": self.password,
        })

        login = result.get("Login", {})

        if not isinstance(login, dict):
            raise GNGError("GNG returned an invalid login response.")

        if not login.get("Success", False):
            if login.get("ProfileDisabled"):
                raise GNGAuthenticationError("GNG profile is disabled.")

            if login.get("Restricted"):
                seconds = login.get("RestrictedTimeRemainingSeconds", 0)
                raise GNGAuthenticationError(
                    f"GNG login temporarily restricted ({seconds}s)."
                )

            if login.get("PasswordChangeRequired"):
                raise GNGAuthenticationError(
                    "GNG requires a password change."
                )

            raise GNGAuthenticationError(
                "GNG rejected the supplied credentials."
            )

        if login.get("PasswordChangeRequired"):
            raise GNGAuthenticationError(
                "GNG requires a password change."
            )

        self.authenticated = True

        _LOGGER.info("Successfully authenticated with GNG.")

        return login

    async def request_broker(self, request):
        """Submit an operation through the GNG request broker."""

        if not self.session or self.session.closed:
            raise GNGConnectionError("HTTP session is not available.")

        if not self.token:
            raise GNGAuthenticationError("No security token available.")

        request = {
            **request,
            "Token": self.token,
            "ViewName": request.get("ViewName") or "/Login",
            "SitePrefix": self.site_prefix,
        }

        url = urljoin(BASE_URL, "/api/WebApi/RequestBroker")

        try:
            async with self.session.post(
                url,
                json={"Request": json.dumps(request)},
                headers={
                    "Content-Type": "application/json;charset=utf-8",
                    "Referer": urljoin(BASE_URL, "/Login"),
                },
            ) as response:
                if response.status in (401, 403):
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        f"GNG rejected the request (HTTP {response.status})."
                    )

                if response.status != 200:
                    raise GNGConnectionError(
                        f"GNG request failed (HTTP {response.status})."
                    )

                try:
                    result = await response.json(content_type=None)
                except ValueError:
                    raise GNGError(
                        "GNG returned an invalid broker response."
                    ) from None

        except TimeoutError:
            raise GNGConnectionError("GNG request timed out.") from None

        except aiohttp.ClientError as err:
            raise GNGConnectionError(
                f"Unable to communicate with GNG: {type(err).__name__}."
            ) from None

        if not isinstance(result, dict):
            raise GNGError("GNG returned an unexpected broker response.")

        # Preserve token rotation even when the operation itself fails.
        new_token = result.get("Token")
        if new_token:
            self.token = new_token

        if result.get("SessionExpired") is True:
            self.authenticated = False
            raise GNGAuthenticationError("GNG session expired.")

        if not result.get("Validated", False):
            # Avoid logging raw portal validation details, which may contain
            # account-specific information.
            raise GNGError("GNG request validation failed.")

        return result

    async def download_authlink_file(self, path, *, referer):
        """Download a portal authlink spreadsheet (GET path?Token=...&nr=1)."""

        if not self.authenticated:
            raise GNGAuthenticationError("Not authenticated with GNG.")

        if not self.token:
            raise GNGAuthenticationError("No security token available.")

        if not self.session or self.session.closed:
            raise GNGConnectionError("HTTP session is not available.")

        query = urlencode({"Token": self.token, "nr": "1"})
        url = urljoin(BASE_URL, f"{path}?{query}")

        try:
            async with self.session.get(
                url,
                headers={"Referer": urljoin(BASE_URL, referer)},
            ) as response:
                if response.status in (401, 403):
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        f"GNG rejected the spreadsheet download "
                        f"(HTTP {response.status})."
                    )

                if response.status != 200:
                    raise GNGConnectionError(
                        f"GNG spreadsheet download failed "
                        f"(HTTP {response.status})."
                    )

                if response.url.path.rstrip("/").lower() == "/login":
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        "GNG redirected the spreadsheet download to its "
                        "login page."
                    )

                content_type = response.headers.get("Content-Type", "")

                if "text/csv" not in content_type.lower():
                    raise GNGError(
                        "Expected CSV but received unexpected content type: "
                        f"{content_type or 'unspecified'}."
                    )

                try:
                    body = await response.text()
                except UnicodeDecodeError:
                    raise GNGError(
                        "GNG returned spreadsheet data with an invalid "
                        "text encoding."
                    ) from None

        except TimeoutError:
            raise GNGConnectionError(
                "GNG spreadsheet download timed out."
            ) from None

        except aiohttp.ClientError as err:
            raise GNGConnectionError(
                "Unable to download GNG spreadsheet: "
                f"{type(err).__name__}."
            ) from None

        if not body.strip():
            raise GNGError("GNG returned an empty spreadsheet export.")

        _LOGGER.info("Successfully downloaded GNG spreadsheet %s.", path)

        return body, content_type

    async def _get_portal_page(self, path: str) -> str:
        """GET a portal HTML page and refresh Token/SitePrefix when present.

        AuthLink spreadsheet exports (e.g. /EppHistorySpreadsheet) return an
        HTML error page unless their portal page has been loaded first in the
        same session.
        """

        if not self.authenticated:
            raise GNGAuthenticationError("Not authenticated with GNG.")

        if not self.session or self.session.closed:
            raise GNGConnectionError("HTTP session is not available.")

        url = urljoin(BASE_URL, path)

        try:
            async with self.session.get(url) as response:
                if response.status in (401, 403):
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        f"GNG rejected portal page {path} "
                        f"(HTTP {response.status})."
                    )

                if response.status != 200:
                    raise GNGConnectionError(
                        f"GNG portal page {path} failed "
                        f"(HTTP {response.status})."
                    )

                if response.url.path.rstrip("/").lower() == "/login":
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        f"GNG redirected portal page {path} to login."
                    )

                try:
                    html = await response.text()
                except UnicodeDecodeError:
                    raise GNGError(
                        f"GNG portal page {path} returned invalid text "
                        "encoding."
                    ) from None

        except TimeoutError:
            raise GNGConnectionError(
                f"GNG portal page {path} timed out."
            ) from None

        except aiohttp.ClientError as err:
            raise GNGConnectionError(
                f"Unable to load GNG portal page {path}: "
                f"{type(err).__name__}."
            ) from None

        parser = TokenParser()
        parser.feed(html)
        page_token = parser.values.get("Token")
        if page_token:
            self.token = page_token
        if "SitePrefix" in parser.values:
            self.site_prefix = parser.values.get("SitePrefix", "")

        return html

    async def download_price_plan_history(self):
        """Download Price Plan / budget-billing history CSV.

        Portal page: /BudgetBillingPlan
        Export: GET /EppHistorySpreadsheet?Token=&nr=1

        The portal requires loading /BudgetBillingPlan in-session before the
        spreadsheet export succeeds.
        """

        await self._get_portal_page("/BudgetBillingPlan")
        csv_data, _content_type = await self.download_authlink_file(
            "/EppHistorySpreadsheet",
            referer="/BudgetBillingPlan",
        )
        return csv_data

    async def download_billing_data(
        self,
        account_numbers,
        start_date,
        end_date,
        *,
        is_current_bill_selected=False,
    ):
        """Request and download detailed billing data as CSV."""

        if not self.authenticated:
            raise GNGAuthenticationError("Not authenticated with GNG.")

        result = await self.request_broker({
            "Actions": "GetDownloadData",
            "AccountNumbers": account_numbers,
            "StartDate": start_date,
            "EndDate": end_date,
            "IsCurrentBillSelected": is_current_bill_selected,
            "DownloadType": "BillingData",
            "BillingDataType": "Detailed",
            "BillingSummary": True,
            "PaymentSummary": True,
            "UsageSummary": True,
            "ViewName": "/DownloadData",
        })

        export = result.get("GetDownloadData")

        if not isinstance(export, dict) or not export.get("Success"):
            error_message = (
                export.get("ErrorMessage")
                if isinstance(export, dict)
                else None
            )
            raise GNGError(
                f"GNG export request failed: {error_message or 'Unknown error'}"
            )

        if not self.session or self.session.closed:
            raise GNGConnectionError("HTTP session is not available.")

        url = urljoin(BASE_URL, "/DownloadDataFile")

        try:
            async with self.session.post(
                url,
                data={
                    "Token": self.token,
                    "SitePrefix": self.site_prefix,
                },
                headers={
                    "Referer": urljoin(BASE_URL, "/DownloadData"),
                },
            ) as response:
                if response.status in (401, 403):
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        f"GNG rejected the CSV download (HTTP {response.status})."
                    )

                if response.status != 200:
                    raise GNGConnectionError(
                        f"GNG CSV download failed (HTTP {response.status})."
                    )

                if response.url.path.rstrip("/").lower() == "/login":
                    self.authenticated = False
                    raise GNGAuthenticationError(
                        "GNG redirected the CSV download to its login page."
                    )

                content_type = response.headers.get("Content-Type", "")

                if "text/csv" not in content_type.lower():
                    raise GNGError(
                        "Expected CSV but received unexpected content type: "
                        f"{content_type or 'unspecified'}."
                    )

                try:
                    csv_data = await response.text()
                except UnicodeDecodeError:
                    raise GNGError(
                        "GNG returned CSV data with an invalid text encoding."
                    ) from None

        except TimeoutError:
            raise GNGConnectionError("GNG CSV download timed out.") from None

        except aiohttp.ClientError as err:
            raise GNGConnectionError(
                f"Unable to download GNG billing data: {type(err).__name__}."
            ) from None

        if not csv_data.strip():
            raise GNGError("GNG returned an empty billing export.")

        _LOGGER.info(
            "Successfully downloaded GNG billing data "
            "(current_bill=%s).",
            is_current_bill_selected,
        )

        return csv_data


def validate_billing_records(records):
    """Validate billing history for duplicates and period continuity."""

    issues = []
    seen_periods = set()
    ordered = sorted(
        records,
        key=lambda record: (
            record.account_number,
            record.bill_date,
        ),
    )

    previous_by_account = {}

    for record in ordered:
        account = record.account_number

        period_key = (
            account,
            record.bill_from_date,
            record.bill_to_date,
        )

        if period_key in seen_periods:
            issues.append(
                f"Duplicate billing period: "
                f"{record.bill_from_date} through {record.bill_to_date}"
            )
        else:
            seen_periods.add(period_key)

        expected_days = (
            record.bill_to_date - record.bill_from_date
        ).days

        if record.days_of_service != expected_days:
            issues.append(
                f"{record.bill_date}: reported {record.days_of_service} "
                f"service days, expected {expected_days}"
            )

        previous_end = previous_by_account.get(account)

        if previous_end is not None:
            if record.bill_from_date > previous_end:
                issues.append(
                    f"Gap in billing periods: "
                    f"{previous_end} to {record.bill_from_date}"
                )
            elif record.bill_from_date < previous_end:
                issues.append(
                    f"Overlapping billing periods: "
                    f"previous ends {previous_end}, "
                    f"next starts {record.bill_from_date}"
                )

        previous_by_account[account] = record.bill_to_date

    return issues

