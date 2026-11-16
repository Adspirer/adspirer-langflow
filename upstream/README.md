# Contributing the Adspirer bundle to Langflow

This folder holds what a pull request to
[langflow-ai/langflow](https://github.com/langflow-ai/langflow) needs beyond the component code.
The route is a provider folder inside the `lfx-bundles` package, the same way Olostep
([#16279](https://github.com/langflow-ai/langflow/pull/16279)), Keenable
([#15992](https://github.com/langflow-ai/langflow/pull/15992)) and SocialScrape
([#16421](https://github.com/langflow-ai/langflow/pull/16421)) were added.

Checked against Langflow's `release-1.14.0` branch on 2026-11-16. Langflow moves quickly: before
opening a pull request, open the most recently merged bundle pull request and compare its file
list with the one below.

## 1. Copy the files

```bash
git clone https://github.com/<your-fork>/langflow && cd langflow
git checkout release-X.Y.Z        # the active release branch, never main
python /path/to/adspirer-langflow/scripts/export_upstream.py .
```

The script writes:

| Written to | From |
| --- | --- |
| `src/bundles/lfx-bundles/src/lfx_bundles/adspirer/` | `src/lfx_adspirer/components/adspirer/`, with imports and the icon name rewritten |
| `src/bundles/lfx-bundles/tests/test_adspirer/` | `tests/` |
| `docs/docs/Components/bundles-adspirer.mdx` | [docs/bundles-adspirer.mdx](docs/bundles-adspirer.mdx) |
| `src/frontend/src/icons/Adspirer/` | [icons/Adspirer/](icons/Adspirer) |

## 2. Register the bundle

Each edit goes next to the matching Olostep line. Lists are alphabetical.

| File | Edit |
| --- | --- |
| `src/bundles/lfx-bundles/pyproject.toml` | Add `adspirer = []` to the extras, and `"lfx-bundles[adspirer]",` to both `all` and `all-no-torch`. Raise `version` by one patch. |
| `pyproject.toml` (root) | Raise the floor in `lfx-bundles[all-no-torch]>=…` to the new version. |
| `uv.lock` | Run `uv lock` with the repository's pinned uv version. The diff should be the version, the new extra and nothing else. |
| `scripts/migrate/consolidate_bundles.py` | Add `"adspirer"` to `PRE_CONSOLIDATED_PROVIDERS` and `"adspirer": [],  # httpx REST only` to `PROVIDER_DEPS`. |
| `scripts/ci/release_inventory_contract.json` | Add `"adspirer"` wherever `"olostep"` appears. |
| `src/lfx/src/lfx/extension/migration/migration_table.json` | Append one row per component (below). The table is append-only. |
| `src/lfx/src/lfx/services/settings/constants.py` | Add `"ADSPIRER_API_KEY",` to the environment variable list. |
| `src/lfx/tests/unit/extension/loader/test_load_lfx_bundles.py` | Add an `("adspirer", {…five class names…})` case. |
| `src/frontend/src/icons/lazyIconImports.ts` | `Adspirer: () => import("@/icons/Adspirer").then((mod) => ({ default: mod.AdspirerIcon })),` |
| `src/frontend/src/utils/styleUtils.ts` | `{ display_name: "Adspirer", name: "adspirer", icon: "Adspirer" },` in `SIDEBAR_BUNDLES`. |
| `src/frontend/src/utils/__tests__/sidebarBundles.test.ts` | Add a "classifies Adspirer as a sidebar bundle" case. Add the icon case to the lazy-import test if that file has one per bundle. |
| `docs/sidebars.js` | Add `"Components/bundles-adspirer",`. |
| `docs/docs/Lfx/extensions-bundle-list.mdx` | Add the row ``| [`adspirer`](./bundles-adspirer) (Adspirer) | `uv pip install "lfx-bundles[adspirer]"` |``. The link must be relative. |

Migration rows, with `added_in` set to the release being targeted:

```json
{ "bare_class_name": "AdspirerAccountsComponent", "target": "ext:adspirer:AdspirerAccountsComponent@official", "added_in": "X.Y.Z" },
{ "bare_class_name": "AdspirerCampaignPerformanceComponent", "target": "ext:adspirer:AdspirerCampaignPerformanceComponent@official", "added_in": "X.Y.Z" },
{ "bare_class_name": "AdspirerKeywordResearchComponent", "target": "ext:adspirer:AdspirerKeywordResearchComponent@official", "added_in": "X.Y.Z" },
{ "bare_class_name": "AdspirerRunToolComponent", "target": "ext:adspirer:AdspirerRunToolComponent@official", "added_in": "X.Y.Z" },
{ "bare_class_name": "AdspirerWastedSpendComponent", "target": "ext:adspirer:AdspirerWastedSpendComponent@official", "added_in": "X.Y.Z" }
```

If the release branch has pending component-break acknowledgments, the version bump invalidates
their IDs. Olostep's pull request shows the fix: regenerate `scripts/ci/component_breaks.json`,
rename the `docs/release_notes/compatibility/lfx-bundles-*.md` files and update
`.secrets.baseline`.

## 3. Check before opening the pull request

```bash
ruff check src/bundles/lfx-bundles/src/lfx_bundles/adspirer src/bundles/lfx-bundles/tests/test_adspirer
ruff format --check src/bundles/lfx-bundles/src/lfx_bundles/adspirer src/bundles/lfx-bundles/tests/test_adspirer
python -m pytest src/bundles/lfx-bundles/tests/test_adspirer -q
python -m pytest src/lfx/tests/unit/extension/loader/test_load_lfx_bundles.py -k adspirer -q
uv lock --check
cd src/frontend && npx biome check src/icons/Adspirer
```

On 2026-11-16 the exported code passed the first four against `release-1.14.0`, and the icon
files passed Biome with the repository's formatter settings. The registration edits in step 2
have not been applied to a Langflow checkout yet.

## What gets a bundle merged quickly

Taken from the review threads of the bundles merged between August and November 2026:

1. Target the active `release-X.Y.Z` branch and keep it merged up to date. Pull requests against
   `main` are not picked up.
2. Include every registration edit above. A missing sidebar entry or inventory row passes the
   pull request's own checks and breaks the release later; the maintainer treats it as blocking.
3. Keep it small: a fixed vendor host, `httpx` only, no SDK, an opt-in extra.
4. Give every agent-facing output method a vendor-specific name, and never name an input after
   an attribute of `Component`. This bundle's tests check both.
5. Return errors as data, keep the API's own reason, and redact the key before truncating.
6. Use LF line endings, relative docs links to new pages, and a minimal `uv.lock` diff.
7. Answer every automated review finding in its thread with the commit that fixes it.
8. In the description, say what was run, what was not, and what the live API returned. Say that
   the author works at Adspirer.
9. Open the pull request from a personal fork with "Allow edits from maintainers" on. The
   maintainer often pushes small fixes himself and cannot push to an organization's fork.
