"""lfx-adspirer: Adspirer advertising components for Langflow.

This package is the distribution unit ``lfx-adspirer``. At runtime Langflow's loader discovers
``extension.json`` shipped alongside this ``__init__.py`` and registers the components under
namespaced IDs such as ``ext:adspirer:AdspirerCampaignPerformanceComponent@official``.

Adspirer (https://www.adspirer.com) connects AI agents to ad accounts on Google Ads, Meta Ads,
LinkedIn Ads and TikTok Ads. The components call its REST API with ``httpx`` and need only the
user's own API key, so the bundle carries no vendor SDK dependency.
"""

from lfx_adspirer.components.adspirer import (
    AdspirerAccountsComponent,
    AdspirerCampaignPerformanceComponent,
    AdspirerKeywordResearchComponent,
    AdspirerRunToolComponent,
    AdspirerWastedSpendComponent,
)

__all__ = [
    "AdspirerAccountsComponent",
    "AdspirerCampaignPerformanceComponent",
    "AdspirerKeywordResearchComponent",
    "AdspirerRunToolComponent",
    "AdspirerWastedSpendComponent",
]
