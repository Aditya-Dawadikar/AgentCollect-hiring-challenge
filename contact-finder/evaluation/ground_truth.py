"""Hand-labeled ground truth for the 18 companies that can be judged by
hand: the 12 companies absent from `enrichment_responses.json` (trivially
`cannot_verify` / review) plus 6 mock-backed companies hand-judged by
inspecting the mock data directly. See ADR-0006 for the binary
verified/needs_human_review label rationale and the per-row reasoning
below."""

import csv
from pathlib import Path

GROUND_TRUTH_COLUMNS = [
    "company_name",
    "expected_needs_human_review",
    "expected_classification",
    "rationale",
]

_ZERO_SOURCE_RATIONALE = "Absent from enrichment_responses.json; no data from any source."

_ZERO_SOURCE_COMPANIES = [
    "Redwood Cabinetry",
    "Desert Sky Solar",
    "Cornerstone Masonry",
    "Velvet Thread Tailoring",
    "Frontier Towing & Recovery",
    "Blue Heron Landscaping",
    "Ace Mobile Locksmith",
    "Granite Peak Surveying",
    "Sierra Vista Auto Body",
    "Evergreen Tree Care",
    "Liberty Sign & Awning",
    "Crescent Moon Cafe",
]

GROUND_TRUTH: list[dict] = [
    {
        "company_name": name,
        "expected_needs_human_review": True,
        "expected_classification": "cannot_verify",
        "rationale": _ZERO_SOURCE_RATIONALE,
    }
    for name in _ZERO_SOURCE_COMPANIES
] + [
    {
        "company_name": "Cedar Ridge Plumbing LLC",
        "expected_needs_human_review": False,
        "expected_classification": "high",
        "rationale": "All 3 sources agree on Daniel Ortega / Owner, email matches name.",
    },
    {
        "company_name": "Pioneer Landscaping Inc",
        "expected_needs_human_review": False,
        "expected_classification": "high",
        "rationale": "All 3 sources agree on Maria Gomez / President, phone+email corroborate.",
    },
    {
        "company_name": "Harbor Light Electric",
        "expected_needs_human_review": False,
        "expected_classification": "medium",
        "rationale": "Registry+listing agree (Sean Murphy / S. Murphy), Owner role, listing phone.",
    },
    {
        "company_name": "Greenfield Catering Group",
        "expected_needs_human_review": False,
        "expected_classification": "medium",
        "rationale": 'Registry (Angela Brooks/Owner) + enrichment email "a.brooks@..." corroborate.',
    },
    {
        "company_name": "Riverside Print & Sign",
        "expected_needs_human_review": True,
        "expected_classification": "cannot_verify",
        "rationale": 'Single weak enrichment source (confidence 41), generic "info@" email.',
    },
    {
        "company_name": "Coastal Breeze Pool Service",
        "expected_needs_human_review": True,
        "expected_classification": "low",
        "rationale": 'Registry ("Tina Alvarez") and listing ("Marcus Webb") name a different person each -- conflict.',
    },
]


def write_ground_truth_csv(path: str | Path) -> None:
    """Writes GROUND_TRUTH to CSV with columns: company_name,
    expected_needs_human_review, expected_classification, rationale."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GROUND_TRUTH_COLUMNS)
        writer.writeheader()
        writer.writerows(GROUND_TRUTH)
