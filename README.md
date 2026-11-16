# Adspirer for Langflow

Advertising components for [Langflow](https://www.langflow.org): report campaign performance,
find wasted spend, research keywords and, when you allow it, make changes on Google Ads, Meta
Ads, LinkedIn Ads and TikTok Ads through [Adspirer](https://www.adspirer.com).

The components are read-only by default. Nothing changes an ad account unless you switch on
**Allow Changes** in the one component that can, and new campaigns are still created paused.

## Install

```bash
uv pip install "git+https://github.com/Adspirer/adspirer-langflow"
langflow run
```

Langflow finds the package at startup and shows an **Adspirer** group in the component list.
Requires Langflow 1.13 or later.

## Get an API key

1. Create an Adspirer account at https://www.adspirer.com.
2. Connect your ad accounts at https://adspirer.ai/connections.
3. Create an API key at https://adspirer.ai/keys. It starts with `sk_live_` and is shown once.
4. Paste it into the **Adspirer API Key** field, or store it in a Langflow
   [global variable](https://docs.langflow.org/configuration-global-variables) named
   `ADSPIRER_API_KEY` and select it there.

The key is yours and acts as you: it reaches the ad accounts you connected and uses your plan's
tool-call allowance. Revoke it at any time at https://adspirer.ai/keys.

## Components

| Component | What it does | Changes accounts? |
| --- | --- | --- |
| **Adspirer Accounts** | Lists your connected ad accounts and their IDs | No |
| **Adspirer Campaign Performance** | Spend, conversions, CPA, ROAS and CTR for one platform | No |
| **Adspirer Wasted Spend** | Campaigns that lose money or underperform, with the spend at stake | No |
| **Adspirer Keyword Research** | Google Ads keywords with search volume, cost per click and a budget estimate | No |
| **Adspirer Run Tool** | Runs any tool in the [Adspirer API](https://www.adspirer.com/docs/api-reference/introduction) by name | Only with **Allow Changes** on |

Each component returns a `Data` object: the written report as its text, and the full API payload
(`text`, `structured` when the tool provides it, and your `quota`) as its data. A failure comes
back as a `Data` with an `error` field, so a flow or an agent can read it.

Every component can be used as a [tool](https://docs.langflow.org/agents-tools) by an Agent. The
agent can set the platform, account, dates and tool arguments. It cannot set the API key or the
**Allow Changes** switch.

### Changes and approvals

**Adspirer Run Tool** knows which Adspirer tools read and which change an account:

- **Allow Changes off** (the default): only read-only tools run. A tool that would create or
  update a campaign, budget, keyword or ad is refused with a message that says why.
- **Allow Changes on**: those tools run. Each run sends an idempotency key, so a retry cannot
  create a second campaign. Campaigns are created paused.
- **Allow Removals** (advanced, also needs Allow Changes): tools that remove keywords, creatives
  or monitors.

A flow runs without a person watching, so turning on **Allow Changes** is your approval for
whatever the flow or its agent then does. Keep it off in scheduled flows, and put a human
approval step in front of it otherwise. [AGENT.md](AGENT.md) has instructions to paste into an
Agent that uses these tools.

## Using the MCP server instead

Adspirer also runs a hosted MCP server. Langflow's **MCP Tools** component connects to it with
your API key as a header (Langflow does not yet support browser sign-in for MCP servers):

| Field | Value |
| --- | --- |
| URL | `https://mcp.adspirer.com/mcp` |
| Transport | Streamable HTTP |
| Header | `Authorization` = `Bearer sk_live_...` |

Use the MCP server when you want an agent to discover every tool by itself. Use these components
when you want fixed, typed steps in a flow and the Allow Changes switch.

## Develop

```bash
uv venv && uv pip install -e ".[dev]"
lfx extension validate src/lfx_adspirer
pytest
ruff check . && ruff format --check .
python scripts/build_catalog.py path/to/openapi.json   # refresh the read-only/change catalog
python scripts/export_upstream.py path/to/langflow     # copy the bundle into a Langflow checkout
```

[upstream/](upstream) holds what a pull request to
[langflow-ai/langflow](https://github.com/langflow-ai/langflow) needs beyond the code: the docs
page, the icon files and the list of registration edits. See [upstream/README.md](upstream/README.md).

## Status

Version 0.1.0, built on 2026-11-16. The unit tests mock the API. The components have not yet
been run against a live Adspirer account or inside the Langflow editor, and the package is not
yet on PyPI or in Langflow's bundle list.

## Support

- Support: support@adspirer.com
- API reference: https://www.adspirer.com/docs/api-reference/introduction
- Privacy: https://www.adspirer.com/privacy
- Terms: https://www.adspirer.com/terms
- Security: see [SECURITY.md](SECURITY.md)
