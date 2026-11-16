"""Shared HTTP plumbing for the Adspirer components.

Adspirer connects AI agents to advertising accounts on Google Ads, Meta Ads, LinkedIn Ads and
TikTok Ads. Every component calls the fixed host ``https://api.adspirer.ai`` with the user's own
API key as a Bearer token; one endpoint per tool, ``POST /api/v1/tools/<tool>/execute``.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from lfx.schema.data import Data

API_BASE_URL = "https://api.adspirer.ai"
DOCUMENTATION_URL = "https://www.adspirer.com/docs/api-reference/introduction"
API_KEYS_URL = "https://adspirer.ai/keys"
CONNECTIONS_URL = "https://adspirer.ai/connections"
DEFAULT_TIMEOUT_SECONDS = 120.0
USER_AGENT = "langflow-adspirer-bundle"

API_KEY_INFO = f"Your Adspirer API key (starts with sk_live_). Create one at {API_KEYS_URL}."
ACCOUNT_ID_INFO = (
    "The ad account to use. Leave empty when only one account is connected on this platform. "
    "Get IDs from the Adspirer Accounts component."
)

PLATFORM_GOOGLE = "Google Ads"
PLATFORM_META = "Meta Ads"
PLATFORM_LINKEDIN = "LinkedIn Ads"
PLATFORM_TIKTOK = "TikTok Ads"
PLATFORMS = [PLATFORM_GOOGLE, PLATFORM_META, PLATFORM_LINKEDIN, PLATFORM_TIKTOK]

# The argument each platform's tools use to pick the ad account.
ACCOUNT_ID_ARGUMENT = {
    PLATFORM_GOOGLE: "customer_id",
    PLATFORM_META: "ad_account_id",
    PLATFORM_LINKEDIN: "ad_account_id",
    PLATFORM_TIKTOK: "advertiser_id",
}
# The ``platform`` filter value the account tools take.
PLATFORM_FILTER = {
    PLATFORM_GOOGLE: "google_ads",
    PLATFORM_META: "meta_ads",
    PLATFORM_LINKEDIN: "linkedin_ads",
    PLATFORM_TIKTOK: "tiktok_ads",
}

MIN_LOOKBACK_DAYS = 1
MAX_LOOKBACK_DAYS = 120

_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{1,80}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Upper bound on the response text echoed into an error message.
ERROR_DETAIL_LIMIT = 600
_STATUS_LABELS = {
    401: "Adspirer rejected the API key (401)",
    402: "Adspirer tool-call allowance reached (402)",
    404: "Adspirer does not have this tool (404)",
    409: "Adspirer rejected a reused idempotency key (409)",
    429: "The ad platform rate limit was reached (429); try again shortly",
}
_NOT_SIGNED_IN = (
    f"Adspirer did not recognize the API key. Create a key at {API_KEYS_URL} and connect your ad "
    f"accounts at {CONNECTIONS_URL}."
)


class AdspirerAPIError(Exception):
    """An Adspirer request failed; the message is safe to show in the component output."""


def secret_value(value: Any) -> str:
    """Unwrap a ``SecretStr``-like value into a stripped plain string (empty when unset)."""
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return str(value or "").strip()


def clean_text(value: Any) -> str:
    """Return an input as a stripped string; ``Message``-like inputs contribute their text."""
    if hasattr(value, "text") and not isinstance(value, str):
        value = value.text
    return str(value or "").strip()


def split_list(value: Any) -> list[str]:
    """Split a comma- or newline-separated input into a list of non-empty strings."""
    if isinstance(value, (list, tuple)):
        items = [clean_text(item) for item in value]
    else:
        items = clean_text(value).replace("\n", ",").split(",")
    return [item.strip() for item in items if item.strip()]


def require_tool_name(value: Any) -> str:
    """Return a tool name that is safe to place in the request path."""
    tool = clean_text(value)
    if not _TOOL_NAME.match(tool):
        msg = f"Enter an Adspirer tool name such as get_campaign_performance; got {tool!r}."
        raise AdspirerAPIError(msg)
    return tool


def require_platform(value: Any) -> str:
    """Return one of the supported platform labels."""
    platform = clean_text(value)
    if platform not in ACCOUNT_ID_ARGUMENT:
        msg = f"Choose a platform from {', '.join(PLATFORMS)}; got {platform!r}."
        raise AdspirerAPIError(msg)
    return platform


def reporting_arguments(
    platform: str, *, account_id: Any, lookback_days: Any, start_date: Any, end_date: Any
) -> dict[str, Any]:
    """Build the account and date arguments the reporting tools share."""
    arguments: dict[str, Any] = {}
    account = clean_text(account_id)
    if account:
        arguments[ACCOUNT_ID_ARGUMENT[platform]] = account

    start, end = clean_text(start_date), clean_text(end_date)
    if start or end:
        if not (_ISO_DATE.match(start) and _ISO_DATE.match(end)):
            msg = "Enter both a start date and an end date as YYYY-MM-DD, or leave both empty."
            raise AdspirerAPIError(msg)
        arguments["start_date"], arguments["end_date"] = start, end
    else:
        try:
            days = int(lookback_days or 30)
        except (TypeError, ValueError) as exc:
            msg = f"Lookback Days must be a whole number; got {lookback_days!r}."
            raise AdspirerAPIError(msg) from exc
        arguments["lookback_days"] = min(max(days, MIN_LOOKBACK_DAYS), MAX_LOOKBACK_DAYS)
    return arguments


def _redact(text: str, api_key: str) -> str:
    """Replace the API key in text with ***."""
    return text.replace(api_key, "***") if api_key else text


def _error_message(response: httpx.Response, api_key: str) -> str:
    """Build a short, key-free error message from a failed API response."""
    try:
        body = response.json()
        detail = str(body.get("error") or body.get("detail") or "") if isinstance(body, dict) else ""
    except ValueError:
        detail = response.text.strip()
    # Redact before truncating, so a key cut at the limit cannot leak in part.
    detail = _redact(detail, api_key)[:ERROR_DETAIL_LIMIT]
    if "not authenticated" in detail.lower():
        return _NOT_SIGNED_IN
    label = _STATUS_LABELS.get(response.status_code, f"Adspirer API error ({response.status_code})")
    return f"{label}: {detail}" if detail else label


def adspirer_request(
    tool: str,
    arguments: dict[str, Any] | None = None,
    *,
    api_key: Any,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run one Adspirer tool and return the ``data`` object of the response.

    Raises:
        AdspirerAPIError: On a missing or unrecognized key, a transport error, a non-2xx status, a
            tool-level error, or a body that is not the documented JSON envelope.
    """
    key = secret_value(api_key)
    if not key:
        msg = f"Enter an Adspirer API key. Create one at {API_KEYS_URL}."
        raise AdspirerAPIError(msg)
    tool = require_tool_name(tool)
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": USER_AGENT}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    url = f"{API_BASE_URL}/api/v1/tools/{tool}/execute"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request("POST", url, json={"arguments": arguments or {}}, headers=headers)
    except httpx.TimeoutException as exc:
        msg = f"Adspirer request timed out after {timeout:g} seconds."
        raise AdspirerAPIError(msg) from exc
    except httpx.RequestError as exc:
        msg = f"Could not reach the Adspirer API: {type(exc).__name__}: {_redact(str(exc), key)}"
        raise AdspirerAPIError(msg) from exc
    if not response.is_success:
        raise AdspirerAPIError(_error_message(response, key))
    try:
        body = response.json()
    except ValueError as exc:
        msg = "Adspirer API returned a response that is not JSON."
        raise AdspirerAPIError(msg) from exc
    if not isinstance(body, dict):
        msg = "Adspirer API returned an unexpected response shape."
        raise AdspirerAPIError(msg)
    if body.get("success") is False or body.get("is_error"):
        raise AdspirerAPIError(_error_message(response, key))
    data = body.get("data")
    if not isinstance(data, dict):
        msg = "Adspirer API returned a response without a data object."
        raise AdspirerAPIError(msg)
    # An unrecognized key is answered as an anonymous visitor with HTTP 200, not with 401.
    structured = data.get("structured")
    if isinstance(structured, dict) and structured.get("auth_required"):
        raise AdspirerAPIError(_NOT_SIGNED_IN)
    return data


def result_data(tool: str, data: dict[str, Any]) -> Data:
    """Wrap a tool result: the readable report as ``text``, the full payload as ``data``."""
    payload = {"tool": tool, **{key: value for key, value in data.items() if value is not None}}
    return Data(text=str(data.get("text") or ""), data=payload)


def error_data(tool: str, message: str) -> Data:
    """Wrap a failure so a flow or an agent can read it instead of crashing."""
    return Data(text=message, data={"tool": tool, "error": message})
