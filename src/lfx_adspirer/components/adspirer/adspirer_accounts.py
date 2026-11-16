"""List the ad accounts connected to Adspirer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, Output, SecretStrInput
from lfx.log.logger import logger

from lfx_adspirer.components.adspirer.adspirer_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    PLATFORM_FILTER,
    PLATFORMS,
    AdspirerAPIError,
    adspirer_request,
    clean_text,
    error_data,
    result_data,
)

if TYPE_CHECKING:
    from lfx.schema.data import Data

TOOL = "list_connected_accounts"
ALL_PLATFORMS = "All platforms"


class AdspirerAccountsComponent(Component):
    """List the ad accounts the user has connected to Adspirer, with their IDs."""

    display_name = "Adspirer Accounts"
    description = "List the ad accounts connected to Adspirer, with the account IDs the other components take."
    documentation = DOCUMENTATION_URL
    icon = "megaphone"
    name = "AdspirerAccounts"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Adspirer API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        DropdownInput(
            name="platform",
            display_name="Platform",
            info="List accounts on one platform, or on all of them.",
            options=[ALL_PLATFORMS, *PLATFORMS],
            value=ALL_PLATFORMS,
            tool_mode=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for Adspirer to answer.",
            value=DEFAULT_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Accounts", name="accounts", method="adspirer_accounts"),
    ]

    def adspirer_accounts(self) -> Data:
        """Return the connected accounts. This call does not use the tool-call allowance."""
        platform = clean_text(self.platform)
        arguments = {"platform": PLATFORM_FILTER[platform]} if platform in PLATFORM_FILTER else {}
        try:
            data = adspirer_request(
                TOOL,
                arguments,
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
            )
        except AdspirerAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return error_data(TOOL, str(exc))
        result = result_data(TOOL, data)
        self.status = result
        return result
