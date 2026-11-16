"""Find ad spend that is not converting on one ad platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger

from lfx_adspirer.components.adspirer.adspirer_common import (
    ACCOUNT_ID_INFO,
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    MAX_LOOKBACK_DAYS,
    PLATFORM_GOOGLE,
    PLATFORM_LINKEDIN,
    PLATFORM_META,
    PLATFORM_TIKTOK,
    PLATFORMS,
    AdspirerAPIError,
    adspirer_request,
    error_data,
    reporting_arguments,
    require_platform,
    result_data,
)

if TYPE_CHECKING:
    from lfx.schema.data import Data

WASTED_SPEND_TOOLS = {
    PLATFORM_GOOGLE: "analyze_wasted_spend",
    PLATFORM_META: "analyze_meta_wasted_spend",
    PLATFORM_LINKEDIN: "analyze_linkedin_wasted_spend",
    PLATFORM_TIKTOK: "analyze_tiktok_wasted_spend",
}


class AdspirerWastedSpendComponent(Component):
    """Find campaigns that lose money or underperform, with the spend at stake."""

    display_name = "Adspirer Wasted Spend"
    description = "Find campaigns that lose money or underperform on Google, Meta, LinkedIn or TikTok Ads."
    documentation = DOCUMENTATION_URL
    icon = "megaphone"
    name = "AdspirerWastedSpend"

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
            info="The ad platform to analyze.",
            options=PLATFORMS,
            value=PLATFORM_GOOGLE,
            tool_mode=True,
        ),
        MessageTextInput(
            name="account_id",
            display_name="Account ID",
            info=ACCOUNT_ID_INFO,
            tool_mode=True,
        ),
        IntInput(
            name="lookback_days",
            display_name="Lookback Days",
            info=f"How many days back to analyze, up to {MAX_LOOKBACK_DAYS}. Ignored when dates are set.",
            value=30,
            tool_mode=True,
        ),
        FloatInput(
            name="target_roas",
            display_name="Target ROAS",
            info="Optional. The return on ad spend to judge campaigns against, such as 3 for 3x. "
            "0 uses the account's own goal or history.",
            value=0.0,
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="start_date",
            display_name="Start Date",
            info="Optional. First day of a custom range, as YYYY-MM-DD. Set End Date as well.",
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="end_date",
            display_name="End Date",
            info="Optional. Last day of a custom range, as YYYY-MM-DD. Set Start Date as well.",
            advanced=True,
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
        Output(display_name="Analysis", name="analysis", method="adspirer_wasted_spend"),
    ]

    def adspirer_wasted_spend(self) -> Data:
        """Return the wasted-spend analysis. Read-only: it proposes fixes and applies none."""
        tool = "wasted_spend"
        try:
            platform = require_platform(self.platform)
            tool = WASTED_SPEND_TOOLS[platform]
            arguments = reporting_arguments(
                platform,
                account_id=self.account_id,
                lookback_days=self.lookback_days,
                start_date=self.start_date,
                end_date=self.end_date,
            )
            try:
                target = float(self.target_roas or 0)
            except (TypeError, ValueError) as exc:
                msg = f"Target ROAS must be a number; got {self.target_roas!r}."
                raise AdspirerAPIError(msg) from exc
            if target > 0:
                arguments["target_roas"] = target
            data = adspirer_request(
                tool,
                arguments,
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
            )
        except AdspirerAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return error_data(tool, str(exc))
        result = result_data(tool, data)
        self.status = result
        return result
