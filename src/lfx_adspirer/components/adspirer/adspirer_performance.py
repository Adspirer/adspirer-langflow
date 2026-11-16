"""Report campaign performance on one ad platform."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, FloatInput, IntInput, MessageTextInput, Output, SecretStrInput
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

PERFORMANCE_TOOLS = {
    PLATFORM_GOOGLE: "get_campaign_performance",
    PLATFORM_META: "get_meta_campaign_performance",
    PLATFORM_LINKEDIN: "get_linkedin_campaign_performance",
    PLATFORM_TIKTOK: "get_tiktok_campaign_performance",
}


class AdspirerCampaignPerformanceComponent(Component):
    """Report spend, conversions, CPA, ROAS and CTR for the campaigns on one ad platform."""

    display_name = "Adspirer Campaign Performance"
    description = "Report campaign spend, conversions, CPA, ROAS and CTR on Google, Meta, LinkedIn or TikTok Ads."
    documentation = DOCUMENTATION_URL
    icon = "megaphone"
    name = "AdspirerCampaignPerformance"

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
            info="The ad platform to report on.",
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
            info=f"How many days back to report on, up to {MAX_LOOKBACK_DAYS}. Ignored when dates are set.",
            value=30,
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
        BoolInput(
            name="raw_data",
            display_name="Raw Metrics Only",
            info="Return only the metrics as JSON, without the written analysis and recommendations.",
            value=False,
            advanced=True,
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
        Output(display_name="Report", name="report", method="adspirer_campaign_performance"),
    ]

    def adspirer_campaign_performance(self) -> Data:
        """Return the performance report. Read-only: it never changes an ad account."""
        tool = "campaign_performance"
        try:
            platform = require_platform(self.platform)
            tool = PERFORMANCE_TOOLS[platform]
            arguments = reporting_arguments(
                platform,
                account_id=self.account_id,
                lookback_days=self.lookback_days,
                start_date=self.start_date,
                end_date=self.end_date,
            )
            if self.raw_data:
                arguments["raw_data"] = True
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
