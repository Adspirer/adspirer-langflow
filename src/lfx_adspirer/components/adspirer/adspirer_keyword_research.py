"""Research Google Ads keywords with Adspirer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger

from lfx_adspirer.components.adspirer.adspirer_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    AdspirerAPIError,
    adspirer_request,
    clean_text,
    error_data,
    result_data,
    split_list,
)

if TYPE_CHECKING:
    from lfx.schema.data import Data

TOOL = "research_keywords"
DEFAULT_LOCATION = "United States"


class AdspirerKeywordResearchComponent(Component):
    """Research keywords with real search volume, cost per click and competition."""

    display_name = "Adspirer Keyword Research"
    description = "Research Google Ads keywords with search volume, cost per click, competition and a budget estimate."
    documentation = DOCUMENTATION_URL
    icon = "megaphone"
    name = "AdspirerKeywordResearch"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Adspirer API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="business_description",
            display_name="Business Description",
            info="What the business sells and to whom. Enter this, seed keywords or a website.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="seed_keywords",
            display_name="Seed Keywords",
            info="Optional. Keywords to start from, comma-separated.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="website_url",
            display_name="Website URL",
            info="Optional. The site to find keywords for. Adspirer reads it on its own servers.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="target_location",
            display_name="Target Location",
            info="The country or region the ads will run in.",
            value=DEFAULT_LOCATION,
            advanced=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="account_id",
            display_name="Google Ads Customer ID",
            info="The Google Ads account to use. Leave empty when only one is connected.",
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
        Output(display_name="Keywords", name="keywords", method="adspirer_keyword_research"),
    ]

    def adspirer_keyword_research(self) -> Data:
        """Return the keyword research. Read-only: it never changes an ad account."""
        description = clean_text(self.business_description)
        seeds = split_list(self.seed_keywords)
        website = clean_text(self.website_url)
        if not (description or seeds or website):
            error = "Enter a business description, seed keywords or a website URL."
            self.status = error
            return error_data(TOOL, error)

        arguments: dict[str, object] = {"target_location": clean_text(self.target_location) or DEFAULT_LOCATION}
        if description:
            arguments["business_description"] = description
        if seeds:
            arguments["seed_keywords"] = seeds
        if website:
            arguments["website_url"] = website
        account = clean_text(self.account_id)
        if account:
            arguments["customer_id"] = account
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
