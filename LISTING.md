# Adspirer — Langflow listing details

| Field | Value |
| --- | --- |
| Bundle name | `adspirer` (display name Adspirer) |
| Package | `lfx-adspirer` (this repository); in Langflow, the `lfx-bundles[adspirer]` extra |
| Components | Accounts, Campaign Performance, Wasted Spend, Keyword Research, Run Tool |
| API host | `https://api.adspirer.ai` (fixed; no user-supplied URL) |
| Sign-in | The user's own Adspirer API key (`sk_live_…`) as a Bearer token |
| Global variable | `ADSPIRER_API_KEY` |
| Dependencies | `httpx` only; no SDK |
| Read-only | Four components are. Run Tool changes accounts only with Allow Changes on |
| Icon | [assets/icon.svg](assets/icon.svg); Langflow icon files in [upstream/icons/Adspirer](upstream/icons/Adspirer) |
| Docs page | [upstream/docs/bundles-adspirer.mdx](upstream/docs/bundles-adspirer.mdx) |
| Website | https://www.adspirer.com |
| API reference | https://www.adspirer.com/docs/api-reference/introduction |
| Privacy | https://www.adspirer.com/privacy |
| Terms | https://www.adspirer.com/terms |
| Support | support@adspirer.com |

## Getting listed

Langflow lists a vendor's components when a pull request adds them to its `lfx-bundles` package.
[upstream/README.md](upstream/README.md) has the steps and the file list.

## Status

Not yet submitted.
