"""Unit tests for the Adspirer bundle (``lfx-adspirer``).

Every request is intercepted at ``httpx.Client.request``, so no network access or API key is
needed. The fake returns real ``httpx.Response`` objects in the API's documented envelope.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest
from lfx.custom.custom_component.component import Component

from lfx_adspirer import (
    AdspirerAccountsComponent,
    AdspirerCampaignPerformanceComponent,
    AdspirerKeywordResearchComponent,
    AdspirerRunToolComponent,
    AdspirerWastedSpendComponent,
)
from lfx_adspirer.components.adspirer.adspirer_catalog import CHANGE_TOOLS, DESTRUCTIVE_TOOLS, READ_ONLY_TOOLS
from lfx_adspirer.components.adspirer.adspirer_common import ERROR_DETAIL_LIMIT, AdspirerAPIError, adspirer_request
from lfx_adspirer.components.adspirer.adspirer_run_tool import parse_arguments

API_KEY = "sk_live_test_key_0123456789abcdefghij"  # pragma: allowlist secret
ALL_COMPONENTS = [
    AdspirerAccountsComponent,
    AdspirerCampaignPerformanceComponent,
    AdspirerWastedSpendComponent,
    AdspirerKeywordResearchComponent,
    AdspirerRunToolComponent,
]
QUOTA = {"used": 42, "limit": 150, "tier": "plus", "period_end": "2026-12-01"}


class FakeAPI:
    """Stand in for ``httpx.Client.request`` and record every call."""

    def __init__(self):
        self.calls: list[dict] = []
        self.status = 200
        self.body: object = None
        self.raw: str | None = None
        self.error: Exception | None = None

    def success(self, text="report", **extra):
        self.status, self.body = 200, {"success": True, "tool": "t", "data": {"text": text, "quota": QUOTA, **extra}}

    def failure(self, status, error, **extra):
        self.status, self.body = status, {"success": False, "is_error": True, "error": error, **extra}

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.error:
            raise self.error
        request = httpx.Request(method, url)
        if self.raw is not None:
            return httpx.Response(self.status, request=request, text=self.raw)
        return httpx.Response(self.status, request=request, json=self.body)

    @property
    def last(self) -> dict:
        return self.calls[-1]

    @property
    def arguments(self) -> dict:
        return self.last["json"]["arguments"]

    @property
    def tool(self) -> str:
        return self.last["url"].removeprefix("https://api.adspirer.ai/api/v1/tools/").removesuffix("/execute")


@pytest.fixture
def api(monkeypatch) -> FakeAPI:
    fake = FakeAPI()
    fake.success()
    monkeypatch.setattr(httpx.Client, "request", lambda _client, method, url, **kwargs: fake(method, url, **kwargs))
    return fake


def build(component_class, **inputs):
    """Build a component the way a graph does: inputs as constructor keyword arguments."""
    return component_class(api_key=API_KEY, **inputs)


# --- Shared request plumbing -------------------------------------------------------------------


def test_request_targets_the_fixed_host_with_bearer_key(api):
    data = adspirer_request("list_campaigns", {"customer_id": "123"}, api_key=API_KEY)
    assert api.last["method"] == "POST"
    assert api.last["url"] == "https://api.adspirer.ai/api/v1/tools/list_campaigns/execute"
    assert api.last["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert api.last["headers"]["User-Agent"] == "langflow-adspirer-bundle"
    assert "Idempotency-Key" not in api.last["headers"]
    assert api.last["json"] == {"arguments": {"customer_id": "123"}}
    assert data["text"] == "report"


def test_request_without_arguments_sends_an_empty_object(api):
    adspirer_request("get_usage_status", api_key=API_KEY)
    assert api.last["json"] == {"arguments": {}}


@pytest.mark.parametrize("key", ["", "   ", None])
def test_missing_key_makes_no_request(api, key):
    with pytest.raises(AdspirerAPIError, match="Enter an Adspirer API key"):
        adspirer_request("list_campaigns", api_key=key)
    assert api.calls == []


def test_secret_str_key_is_unwrapped(api):
    class Secret:
        def get_secret_value(self):
            return f"  {API_KEY}  "

    adspirer_request("list_campaigns", api_key=Secret())
    assert api.last["headers"]["Authorization"] == f"Bearer {API_KEY}"


@pytest.mark.parametrize("tool", ["", "List_Campaigns", "list campaigns", "../admin", "a/b", "x" * 90, "1tool"])
def test_unsafe_tool_names_never_reach_the_url(api, tool):
    with pytest.raises(AdspirerAPIError, match="Enter an Adspirer tool name"):
        adspirer_request(tool, api_key=API_KEY)
    assert api.calls == []


def test_idempotency_key_is_sent_when_given(api):
    adspirer_request("pause_campaign", {}, api_key=API_KEY, idempotency_key="abc")
    assert api.last["headers"]["Idempotency-Key"] == "abc"


@pytest.mark.parametrize(
    ("status", "error", "expected"),
    [
        (401, "bad key", "Adspirer rejected the API key (401): bad key"),
        (402, "Monthly limit reached (150/150)", "Adspirer tool-call allowance reached (402): Monthly limit"),
        (404, "Tool not found: nope", "Adspirer does not have this tool (404): Tool not found: nope"),
        (429, "Meta throttle", "The ad platform rate limit was reached (429); try again shortly: Meta throttle"),
        (400, "ad_set_id is required", "Adspirer API error (400): ad_set_id is required"),
        (500, "Internal error", "Adspirer API error (500): Internal error"),
    ],
)
def test_http_errors_keep_the_api_reason(api, status, error, expected):
    api.failure(status, error)
    with pytest.raises(AdspirerAPIError) as caught:
        adspirer_request("list_campaigns", api_key=API_KEY)
    assert str(caught.value).startswith(expected)


def test_account_choice_error_is_passed_through(api):
    message = 'You have 2 meta_ads accounts connected. Pass ad_account_id:\n  - Acme (ad_account_id="act_1")'
    api.failure(400, message)
    with pytest.raises(AdspirerAPIError, match="act_1"):
        adspirer_request("get_meta_campaign_performance", api_key=API_KEY)


def test_unrecognized_key_answered_with_400_is_explained(api):
    api.failure(400, "Not authenticated. Please connect your Adspirer account first at https://adspirer.ai")
    with pytest.raises(AdspirerAPIError, match="did not recognize the API key") as caught:
        adspirer_request("list_connected_accounts", api_key=API_KEY)
    assert "https://adspirer.ai/keys" in str(caught.value)


def test_unrecognized_key_answered_with_200_is_an_error(api):
    """The API answers an unknown key as an anonymous visitor with HTTP 200."""
    api.success("Please connect your Adspirer account first.", structured={"connections": [], "auth_required": True})
    with pytest.raises(AdspirerAPIError, match="did not recognize the API key"):
        adspirer_request("get_connections_status", api_key=API_KEY)


def test_error_flag_in_a_200_body_is_an_error(api):
    api.failure(200, "campaign not found")
    with pytest.raises(AdspirerAPIError, match="campaign not found"):
        adspirer_request("list_campaigns", api_key=API_KEY)


def test_key_is_redacted_from_api_errors(api):
    api.failure(400, f"token {API_KEY} is not allowed")
    with pytest.raises(AdspirerAPIError) as caught:
        adspirer_request("list_campaigns", api_key=API_KEY)
    assert API_KEY not in str(caught.value)
    assert "***" in str(caught.value)


def test_key_is_redacted_before_the_detail_is_truncated(api):
    """A key that straddles the truncation limit must not leak in part."""
    padding = "x" * (ERROR_DETAIL_LIMIT - 10)
    api.failure(400, padding + API_KEY)
    with pytest.raises(AdspirerAPIError) as caught:
        adspirer_request("list_campaigns", api_key=API_KEY)
    assert API_KEY[:12] not in str(caught.value)


def test_key_is_redacted_from_transport_errors(api):
    api.error = httpx.ConnectError(f"cannot connect with {API_KEY}")
    with pytest.raises(AdspirerAPIError, match="Could not reach the Adspirer API") as caught:
        adspirer_request("list_campaigns", api_key=API_KEY)
    assert API_KEY not in str(caught.value)


def test_timeout_is_reported_with_its_length(api):
    api.error = httpx.ReadTimeout("slow")
    with pytest.raises(AdspirerAPIError, match="timed out after 5 seconds"):
        adspirer_request("list_campaigns", api_key=API_KEY, timeout=5)


def test_non_json_success_body_is_an_error(api):
    api.raw = "<html>gateway</html>"
    with pytest.raises(AdspirerAPIError, match="not JSON"):
        adspirer_request("list_campaigns", api_key=API_KEY)


def test_non_json_error_body_falls_back_to_the_text(api):
    api.status, api.raw = 502, "upstream down"
    with pytest.raises(AdspirerAPIError, match=r"Adspirer API error \(502\): upstream down"):
        adspirer_request("list_campaigns", api_key=API_KEY)


@pytest.mark.parametrize("body", [["unexpected"], "text", 7])
def test_non_object_body_is_an_error(api, body):
    api.body = body
    with pytest.raises(AdspirerAPIError, match="unexpected response shape"):
        adspirer_request("list_campaigns", api_key=API_KEY)


@pytest.mark.parametrize("data", [None, "text", []])
def test_missing_data_object_is_an_error(api, data):
    api.body = {"success": True, "data": data}
    with pytest.raises(AdspirerAPIError, match="without a data object"):
        adspirer_request("list_campaigns", api_key=API_KEY)


# --- Component contract ------------------------------------------------------------------------


@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_input_names_do_not_shadow_component_attributes(component_class):
    """An input named like a ``Component`` attribute resolves to that attribute, not the value."""
    reserved = set(dir(Component))
    assert [i.name for i in component_class.inputs if i.name in reserved] == []


@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_api_key_is_a_required_secret_the_agent_cannot_set(component_class):
    key = next(i for i in component_class.inputs if i.name == "api_key")
    assert type(key).__name__ == "SecretStrInput"
    assert key.required is True
    assert not getattr(key, "tool_mode", False)


def test_class_and_component_names_are_stable():
    """Saved flows refer to these names; changing one breaks them."""
    assert {c.__name__: c.name for c in ALL_COMPONENTS} == {
        "AdspirerAccountsComponent": "AdspirerAccounts",
        "AdspirerCampaignPerformanceComponent": "AdspirerCampaignPerformance",
        "AdspirerWastedSpendComponent": "AdspirerWastedSpend",
        "AdspirerKeywordResearchComponent": "AdspirerKeywordResearch",
        "AdspirerRunToolComponent": "AdspirerRunTool",
    }


def test_tool_names_are_adspirer_specific():
    """An Agent cannot hold two tools with one name, so every tool name carries the vendor."""
    names = []
    for component_class in ALL_COMPONENTS:
        tools = asyncio.run(build(component_class).to_toolkit())
        names += [tool.name for tool in tools]
    assert sorted(names) == [
        "adspirer_accounts",
        "adspirer_campaign_performance",
        "adspirer_keyword_research",
        "adspirer_run_tool",
        "adspirer_wasted_spend",
    ]


def test_agent_cannot_switch_on_changes():
    tools = asyncio.run(build(AdspirerRunToolComponent).to_toolkit())
    assert set(tools[0].args) == {"tool_name", "tool_arguments"}


# --- Accounts ----------------------------------------------------------------------------------


def test_accounts_lists_every_platform_by_default(api):
    api.success("2 accounts", structured={"accounts": [{"id": "123"}]})
    result = build(AdspirerAccountsComponent).adspirer_accounts()
    assert api.tool == "list_connected_accounts"
    assert api.arguments == {}
    assert result.text == "2 accounts"
    assert result.data["tool"] == "list_connected_accounts"
    assert result.data["structured"] == {"accounts": [{"id": "123"}]}
    assert result.data["quota"] == QUOTA
    assert "error" not in result.data


@pytest.mark.parametrize(
    ("platform", "value"),
    [
        ("Google Ads", "google_ads"),
        ("Meta Ads", "meta_ads"),
        ("LinkedIn Ads", "linkedin_ads"),
        ("TikTok Ads", "tiktok_ads"),
    ],
)
def test_accounts_filters_by_platform(api, platform, value):
    build(AdspirerAccountsComponent, platform=platform).adspirer_accounts()
    assert api.arguments == {"platform": value}


def test_accounts_returns_errors_as_data(api):
    api.failure(400, "Not authenticated. Please connect your Adspirer account first at https://adspirer.ai")
    result = build(AdspirerAccountsComponent).adspirer_accounts()
    assert "did not recognize the API key" in result.data["error"]
    assert result.text == result.data["error"]


# --- Campaign performance ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "tool", "account_argument"),
    [
        ("Google Ads", "get_campaign_performance", "customer_id"),
        ("Meta Ads", "get_meta_campaign_performance", "ad_account_id"),
        ("LinkedIn Ads", "get_linkedin_campaign_performance", "ad_account_id"),
        ("TikTok Ads", "get_tiktok_campaign_performance", "advertiser_id"),
    ],
)
def test_performance_picks_the_tool_and_account_argument(api, platform, tool, account_argument):
    component = build(AdspirerCampaignPerformanceComponent, platform=platform, account_id=" 123 ", lookback_days=7)
    result = component.adspirer_campaign_performance()
    assert api.tool == tool
    assert api.arguments == {account_argument: "123", "lookback_days": 7}
    assert result.data["tool"] == tool
    assert tool in READ_ONLY_TOOLS


def test_performance_defaults_to_google_ads_last_30_days(api):
    build(AdspirerCampaignPerformanceComponent).adspirer_campaign_performance()
    assert api.tool == "get_campaign_performance"
    assert api.arguments == {"lookback_days": 30}


@pytest.mark.parametrize(("given", "sent"), [(0, 30), (-5, 1), (1, 1), (120, 120), (500, 120), ("14", 14)])
def test_performance_clamps_lookback_days(api, given, sent):
    build(AdspirerCampaignPerformanceComponent, lookback_days=given).adspirer_campaign_performance()
    assert api.arguments["lookback_days"] == sent


def test_performance_custom_dates_replace_lookback(api):
    component = build(
        AdspirerCampaignPerformanceComponent, start_date="2026-10-01", end_date="2026-10-31", lookback_days=7
    )
    component.adspirer_campaign_performance()
    assert api.arguments == {"start_date": "2026-10-01", "end_date": "2026-10-31"}


@pytest.mark.parametrize(
    ("start", "end"), [("2026-10-01", ""), ("", "2026-10-31"), ("10/01/2026", "2026-10-31"), ("yesterday", "today")]
)
def test_performance_rejects_bad_dates_without_a_request(api, start, end):
    component = build(AdspirerCampaignPerformanceComponent, start_date=start, end_date=end)
    result = component.adspirer_campaign_performance()
    assert "YYYY-MM-DD" in result.data["error"]
    assert api.calls == []


def test_performance_rejects_non_numeric_lookback(api):
    result = build(AdspirerCampaignPerformanceComponent, lookback_days="a month").adspirer_campaign_performance()
    assert "whole number" in result.data["error"]
    assert api.calls == []


def test_performance_rejects_unknown_platform_without_a_request(api):
    result = build(AdspirerCampaignPerformanceComponent, platform="Snapchat Ads").adspirer_campaign_performance()
    assert "Choose a platform" in result.data["error"]
    assert api.calls == []


def test_performance_raw_data_is_sent_only_when_enabled(api):
    build(AdspirerCampaignPerformanceComponent, raw_data=True).adspirer_campaign_performance()
    assert api.arguments["raw_data"] is True
    build(AdspirerCampaignPerformanceComponent, raw_data=False).adspirer_campaign_performance()
    assert "raw_data" not in api.arguments


@pytest.mark.usefixtures("api")
def test_performance_uses_the_timeout_input(monkeypatch):
    seen = {}
    original = httpx.Client.__init__

    def init(self, *args, **kwargs):
        seen.update(kwargs)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", init)
    build(AdspirerCampaignPerformanceComponent, timeout=15).adspirer_campaign_performance()
    assert seen["timeout"] == 15


def test_performance_quota_error_keeps_the_upgrade_link(api):
    api.failure(402, "Monthly limit reached (150/150). Upgrade at https://adspirer.ai", quota=QUOTA)
    result = build(AdspirerCampaignPerformanceComponent).adspirer_campaign_performance()
    assert result.data["error"].startswith("Adspirer tool-call allowance reached (402)")
    assert "https://adspirer.ai" in result.data["error"]


def test_performance_runs_as_an_agent_tool(api):
    api.success("Spend $1,200, ROAS 3.1x")
    tools = asyncio.run(build(AdspirerCampaignPerformanceComponent).to_toolkit())
    output = asyncio.run(tools[0].ainvoke({"platform": "Meta Ads", "account_id": "act_1", "lookback_days": 14}))
    assert api.tool == "get_meta_campaign_performance"
    assert api.arguments == {"ad_account_id": "act_1", "lookback_days": 14}
    assert "ROAS 3.1x" in str(output)


# --- Wasted spend ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "tool", "account_argument"),
    [
        ("Google Ads", "analyze_wasted_spend", "customer_id"),
        ("Meta Ads", "analyze_meta_wasted_spend", "ad_account_id"),
        ("LinkedIn Ads", "analyze_linkedin_wasted_spend", "ad_account_id"),
        ("TikTok Ads", "analyze_tiktok_wasted_spend", "advertiser_id"),
    ],
)
def test_wasted_spend_picks_the_tool_and_account_argument(api, platform, tool, account_argument):
    build(AdspirerWastedSpendComponent, platform=platform, account_id="9").adspirer_wasted_spend()
    assert api.tool == tool
    assert api.arguments == {account_argument: "9", "lookback_days": 30}
    assert tool in READ_ONLY_TOOLS


@pytest.mark.parametrize(("given", "sent"), [(3, 3.0), ("2.5", 2.5)])
def test_wasted_spend_sends_a_positive_target_roas(api, given, sent):
    build(AdspirerWastedSpendComponent, target_roas=given).adspirer_wasted_spend()
    assert api.arguments["target_roas"] == sent


@pytest.mark.parametrize("given", [0, 0.0, -1, None, ""])
def test_wasted_spend_omits_an_unset_target_roas(api, given):
    build(AdspirerWastedSpendComponent, target_roas=given).adspirer_wasted_spend()
    assert "target_roas" not in api.arguments


def test_wasted_spend_rejects_a_non_numeric_target(api):
    result = build(AdspirerWastedSpendComponent, target_roas="high").adspirer_wasted_spend()
    assert "Target ROAS must be a number" in result.data["error"]
    assert api.calls == []


# --- Keyword research --------------------------------------------------------------------------


def test_keyword_research_needs_something_to_research(api):
    result = build(AdspirerKeywordResearchComponent).adspirer_keyword_research()
    assert "business description, seed keywords or a website" in result.data["error"]
    assert api.calls == []


def test_keyword_research_sends_only_what_was_entered(api):
    build(AdspirerKeywordResearchComponent, business_description=" Emergency plumber ").adspirer_keyword_research()
    assert api.tool == "research_keywords"
    assert api.arguments == {"business_description": "Emergency plumber", "target_location": "United States"}


def test_keyword_research_splits_seed_keywords(api):
    component = build(
        AdspirerKeywordResearchComponent,
        seed_keywords="plumber near me, emergency plumber\n drain cleaning ,,",
        website_url="https://example.com",
        target_location="Canada",
        account_id="123-456-7890",
    )
    component.adspirer_keyword_research()
    assert api.arguments == {
        "seed_keywords": ["plumber near me", "emergency plumber", "drain cleaning"],
        "website_url": "https://example.com",
        "target_location": "Canada",
        "customer_id": "123-456-7890",
    }


def test_keyword_research_returns_errors_as_data(api):
    api.failure(429, "Google Ads quota")
    result = build(AdspirerKeywordResearchComponent, seed_keywords="shoes").adspirer_keyword_research()
    assert result.data["error"].startswith("The ad platform rate limit was reached (429)")


# --- Run tool: the read-only gate --------------------------------------------------------------


def test_catalog_groups_do_not_overlap():
    assert READ_ONLY_TOOLS.isdisjoint(CHANGE_TOOLS)
    assert READ_ONLY_TOOLS.isdisjoint(DESTRUCTIVE_TOOLS)
    assert CHANGE_TOOLS.isdisjoint(DESTRUCTIVE_TOOLS)
    assert {"get_campaign_performance", "list_connected_accounts", "research_keywords"} <= READ_ONLY_TOOLS
    assert {"create_search_campaign", "update_campaign", "pause_campaign"} <= CHANGE_TOOLS
    assert {"remove_keywords", "delete_monitor"} <= DESTRUCTIVE_TOOLS


def test_run_tool_runs_read_only_tools_by_default(api):
    component = build(AdspirerRunToolComponent, tool_name="list_campaigns", tool_arguments='{"customer_id": "1"}')
    result = component.adspirer_run_tool()
    assert api.tool == "list_campaigns"
    assert api.arguments == {"customer_id": "1"}
    assert "Idempotency-Key" not in api.last["headers"]
    assert result.data["tool"] == "list_campaigns"


@pytest.mark.parametrize("tool", ["create_search_campaign", "update_campaign", "pause_campaign", "add_keywords"])
def test_run_tool_refuses_changes_by_default(api, tool):
    result = build(AdspirerRunToolComponent, tool_name=tool, tool_arguments="{}").adspirer_run_tool()
    assert "can change an ad account" in result.data["error"]
    assert "Allow Changes" in result.data["error"]
    assert api.calls == []


def test_run_tool_treats_an_unknown_tool_as_a_change(api):
    result = build(AdspirerRunToolComponent, tool_name="brand_new_tool").adspirer_run_tool()
    assert "can change an ad account" in result.data["error"]
    assert api.calls == []


def test_run_tool_runs_changes_when_allowed_with_an_idempotency_key(api):
    component = build(
        AdspirerRunToolComponent,
        tool_name="pause_campaign",
        tool_arguments='{"campaign_id": "77"}',
        allow_changes=True,
    )
    result = component.adspirer_run_tool()
    assert api.tool == "pause_campaign"
    assert api.arguments == {"campaign_id": "77"}
    assert uuid.UUID(api.last["headers"]["Idempotency-Key"]).version == 4
    assert "error" not in result.data


def test_run_tool_uses_a_fresh_idempotency_key_per_run(api):
    component = build(AdspirerRunToolComponent, tool_name="pause_campaign", allow_changes=True)
    component.adspirer_run_tool()
    component.adspirer_run_tool()
    first, second = (call["headers"]["Idempotency-Key"] for call in api.calls)
    assert first != second


@pytest.mark.parametrize("tool", sorted(DESTRUCTIVE_TOOLS))
def test_run_tool_refuses_removals_without_the_second_switch(api, tool):
    result = build(AdspirerRunToolComponent, tool_name=tool, allow_changes=True).adspirer_run_tool()
    assert "removes something" in result.data["error"]
    assert api.calls == []


def test_run_tool_removal_switch_alone_is_not_enough(api):
    result = build(AdspirerRunToolComponent, tool_name="remove_keywords", allow_removals=True).adspirer_run_tool()
    assert "can change an ad account" in result.data["error"]
    assert api.calls == []


def test_run_tool_runs_removals_with_both_switches(api):
    component = build(AdspirerRunToolComponent, tool_name="remove_keywords", allow_changes=True, allow_removals=True)
    component.adspirer_run_tool()
    assert api.tool == "remove_keywords"
    assert "Idempotency-Key" in api.last["headers"]


def test_agent_tool_call_cannot_bypass_the_gate(api):
    """Extra arguments an agent invents must not switch changes on."""
    tools = asyncio.run(build(AdspirerRunToolComponent).to_toolkit())
    output = asyncio.run(
        tools[0].ainvoke({"tool_name": "create_search_campaign", "tool_arguments": '{"allow_changes": true}'})
    )
    assert api.calls == []
    assert "can change an ad account" in str(output)


@pytest.mark.parametrize("tool", ["../../admin", "list campaigns", ""])
def test_run_tool_rejects_bad_tool_names(api, tool):
    result = build(AdspirerRunToolComponent, tool_name=tool, allow_changes=True).adspirer_run_tool()
    assert "Enter an Adspirer tool name" in result.data["error"]
    assert api.calls == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", {}),
        (None, {}),
        ("   ", {}),
        ('{"lookback_days": 30}', {"lookback_days": 30}),
        ({"a": 1}, {"a": 1}),
        (json.dumps({"nested": {"k": [1, 2]}}), {"nested": {"k": [1, 2]}}),
    ],
)
def test_parse_arguments_accepts_json_objects(value, expected):
    assert parse_arguments(value) == expected


@pytest.mark.parametrize("value", ["not json", "[1, 2]", '"text"', "42", "{'single': 'quotes'}"])
def test_parse_arguments_rejects_everything_else(value):
    with pytest.raises(AdspirerAPIError, match="Arguments must be a JSON object"):
        parse_arguments(value)


def test_run_tool_reports_bad_arguments_without_a_request(api):
    result = build(AdspirerRunToolComponent, tool_name="list_campaigns", tool_arguments="[1]").adspirer_run_tool()
    assert "Arguments must be a JSON object" in result.data["error"]
    assert api.calls == []
