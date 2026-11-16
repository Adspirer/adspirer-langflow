"""Run any Adspirer tool by name."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, FloatInput, MessageTextInput, MultilineInput, Output, SecretStrInput
from lfx.log.logger import logger

from lfx_adspirer.components.adspirer.adspirer_catalog import DESTRUCTIVE_TOOLS, READ_ONLY_TOOLS
from lfx_adspirer.components.adspirer.adspirer_common import (
    API_KEY_INFO,
    DEFAULT_TIMEOUT_SECONDS,
    DOCUMENTATION_URL,
    AdspirerAPIError,
    adspirer_request,
    clean_text,
    error_data,
    require_tool_name,
    result_data,
)

if TYPE_CHECKING:
    from lfx.schema.data import Data

CHANGES_OFF = (
    "{tool} can change an ad account, so it was not run. To allow it, turn on Allow Changes in the "
    "Adspirer Run Tool component. New campaigns are still created paused."
)
DESTRUCTIVE_OFF = (
    "{tool} removes something from an ad account, so it was not run. To allow it, turn on both "
    "Allow Changes and Allow Removals in the Adspirer Run Tool component."
)


def parse_arguments(value: Any) -> dict[str, Any]:
    """Read the Arguments input: a JSON object, a dict, or empty for no arguments."""
    if isinstance(value, dict):
        return value
    text = clean_text(value)
    if not text:
        return {}
    try:
        arguments = json.loads(text)
    except ValueError as exc:
        msg = f'Arguments must be a JSON object, such as {{"lookback_days": 30}}: {exc}'
        raise AdspirerAPIError(msg) from exc
    if not isinstance(arguments, dict):
        msg = 'Arguments must be a JSON object, such as {"lookback_days": 30}.'
        raise AdspirerAPIError(msg)
    return arguments


class AdspirerRunToolComponent(Component):
    """Run any tool in the Adspirer API; changes to ad accounts stay off until the author allows them."""

    display_name = "Adspirer Run Tool"
    description = "Run any Adspirer tool by name. Read-only unless you turn on Allow Changes."
    documentation = DOCUMENTATION_URL
    icon = "megaphone"
    name = "AdspirerRunTool"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="Adspirer API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="tool_name",
            display_name="Tool Name",
            info="The Adspirer tool to run, such as list_campaigns or analyze_search_terms. "
            "The API reference lists every tool and its arguments.",
            required=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="tool_arguments",
            display_name="Arguments",
            info='The tool\'s arguments as a JSON object, such as {"lookback_days": 30}. Leave empty for none.',
            tool_mode=True,
        ),
        BoolInput(
            name="allow_changes",
            display_name="Allow Changes",
            info="Off: only read-only tools run. On: tools that create or update campaigns, budgets, "
            "keywords and ads also run. An agent cannot change this setting.",
            value=False,
        ),
        BoolInput(
            name="allow_removals",
            display_name="Allow Removals",
            info="Also run tools that remove keywords, creatives or monitors. Needs Allow Changes.",
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
        Output(display_name="Result", name="result", method="adspirer_run_tool"),
    ]

    def adspirer_run_tool(self) -> Data:
        """Run the tool and return its result, or an error when it is not allowed to run."""
        tool = clean_text(self.tool_name)
        try:
            tool = require_tool_name(tool)
            arguments = parse_arguments(self.tool_arguments)
            read_only = tool in READ_ONLY_TOOLS
            # A tool the catalog does not know is treated as one that changes an account.
            if not read_only and not self.allow_changes:
                raise AdspirerAPIError(CHANGES_OFF.format(tool=tool))
            if tool in DESTRUCTIVE_TOOLS and not self.allow_removals:
                raise AdspirerAPIError(DESTRUCTIVE_OFF.format(tool=tool))
            data = adspirer_request(
                tool,
                arguments,
                api_key=self.api_key,
                timeout=float(self.timeout or DEFAULT_TIMEOUT_SECONDS),
                # One key per run, so a retried request cannot create a second campaign.
                idempotency_key=None if read_only else str(uuid.uuid4()),
            )
        except AdspirerAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return error_data(tool, str(exc))
        result = result_data(tool, data)
        self.status = result
        return result
