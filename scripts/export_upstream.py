"""Copy the Adspirer bundle into a checkout of langflow-ai/langflow, in the in-tree layout.

Usage: python scripts/export_upstream.py path/to/langflow

Writes the provider folder under ``src/bundles/lfx-bundles``, its tests, the docs page and the
icon files. Imports and the icon name are rewritten for the in-tree package. The registration
edits to existing Langflow files are not made here; upstream/README.md lists them.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/lfx_adspirer/components/adspirer"
OUT_OF_TREE, IN_TREE = "lfx_adspirer.components.adspirer", "lfx_bundles.adspirer"

LAZY_INIT = '''from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .adspirer_accounts import AdspirerAccountsComponent
    from .adspirer_keyword_research import AdspirerKeywordResearchComponent
    from .adspirer_performance import AdspirerCampaignPerformanceComponent
    from .adspirer_run_tool import AdspirerRunToolComponent
    from .adspirer_wasted_spend import AdspirerWastedSpendComponent

_dynamic_imports = {
    "AdspirerAccountsComponent": "adspirer_accounts",
    "AdspirerCampaignPerformanceComponent": "adspirer_performance",
    "AdspirerKeywordResearchComponent": "adspirer_keyword_research",
    "AdspirerRunToolComponent": "adspirer_run_tool",
    "AdspirerWastedSpendComponent": "adspirer_wasted_spend",
}

__all__ = [
    "AdspirerAccountsComponent",
    "AdspirerCampaignPerformanceComponent",
    "AdspirerKeywordResearchComponent",
    "AdspirerRunToolComponent",
    "AdspirerWastedSpendComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import Adspirer components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    """List the lazily imported component names."""
    return list(__all__)
'''


def in_tree(text: str) -> str:
    text = text.replace(OUT_OF_TREE, IN_TREE)
    # In this repository the package is first-party and sorts into its own import block; inside
    # Langflow it sorts with the other third-party imports.
    text = text.replace("\n\nfrom lfx_adspirer import (", "\nfrom lfx_bundles.adspirer import (")
    text = text.replace("``lfx-adspirer``", "``lfx-bundles[adspirer]``")
    return text.replace('icon = "megaphone"', 'icon = "Adspirer"')


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Langflow's frontend check (Biome) rejects CRLF line endings.
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(f"  wrote {path}")


def main(langflow: str) -> None:
    repo = Path(langflow).resolve()
    bundles = repo / "src/bundles/lfx-bundles"
    if not (bundles / "pyproject.toml").is_file():
        sys.exit(f"{repo} does not look like a Langflow checkout (no src/bundles/lfx-bundles).")

    provider = bundles / "src/lfx_bundles/adspirer"
    for module in sorted(SOURCE.glob("adspirer_*.py")):
        write(provider / module.name, in_tree(module.read_text(encoding="utf-8")))
    write(provider / "__init__.py", LAZY_INIT)

    tests = bundles / "tests/test_adspirer"
    write(tests / "__init__.py", '"""Adspirer bundle tests."""\n')
    test_source = (ROOT / "tests/test_adspirer_components.py").read_text(encoding="utf-8")
    write(tests / "test_adspirer_components.py", in_tree(test_source))

    docs_source = (ROOT / "upstream/docs/bundles-adspirer.mdx").read_text(encoding="utf-8")
    write(repo / "docs/docs/Components/bundles-adspirer.mdx", docs_source)

    icons = repo / "src/frontend/src/icons/Adspirer"
    for icon in sorted((ROOT / "upstream/icons/Adspirer").iterdir()):
        icons.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(icon, icons / icon.name)
        print(f"  wrote {icons / icon.name}")

    print("\nNow make the registration edits listed in upstream/README.md.")


if __name__ == "__main__":
    main(sys.argv[1])
