"""Client over the canned mock provider responses.

Wraps challenge/mocks/enrichment_responses.json and presents the three
"providers" (registry, listing, enrichment) behind a single query interface.
A provider that is absent for a company (or the company missing entirely)
is treated as a "not found" from that source, per challenge/mocks/README.md.
"""

import json
from pathlib import Path

from config import settings

PROVIDERS = ("registry", "listing", "enrichment")


class MockProviderClient:
    def __init__(self, mocks_path: str | Path | None = None):
        path = Path(mocks_path) if mocks_path else settings.MOCKS_JSON
        with open(path, encoding="utf-8") as f:
            self._data: dict = json.load(f)

    def query_all(self, company_name: str) -> dict:
        """Returns {"registry": dict | None, "listing": dict | None,
        "enrichment": dict | None}."""
        record = self._data.get(company_name, {})
        return {provider: record.get(provider) for provider in PROVIDERS}
