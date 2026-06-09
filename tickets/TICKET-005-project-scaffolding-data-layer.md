# TICKET-005: Project scaffolding & data layer

**Status:** todo
**Branch:** `feat/TICKET-005-project-scaffolding`
**Depends on:** none

## Goal

Stand up the `contact-finder/` project skeleton and the data-access layer:
read `challenge/data/companies.csv` and serve canned responses from
`challenge/mocks/enrichment_responses.json` through a small client with a
stable interface that every later module depends on.

## Why this is its own ticket

Every other ticket imports from `config.settings` and `data_sources.*`. Get
these interfaces and the path-resolution to `challenge/` (one directory up
from `contact-finder/`) right first, with tests, so nothing downstream has to
guess.

## Files

- Create: `contact-finder/requirements.txt`
- Create: `contact-finder/.gitignore`
- Create: `contact-finder/run.py` (stub: prints "not yet implemented", real logic in TICKET-011)
- Create: `contact-finder/run_evaluation.py` (stub, real logic in TICKET-010/011)
- Create: `contact-finder/config/__init__.py`
- Create: `contact-finder/config/settings.py`
- Create: `contact-finder/data_sources/__init__.py`
- Create: `contact-finder/data_sources/loader.py`
- Create: `contact-finder/data_sources/mocks.py`
- Create: `contact-finder/tests/__init__.py`
- Create: `contact-finder/tests/test_data_sources.py`
- Create: all other `__init__.py` for `data_comparison/`, `classification/`,
  `evaluation/`, `output/`, `output/results/.gitkeep` (so the package layout
  from `INSTRUCTIONS.md` exists; later tickets fill in the modules)

## Interface contract

```python
# config/settings.py
CONFIDENCE_THRESHOLD = 70          # CLARIFICATIONS.md: < 70 -> needs_human_review
FUZZY_NAME_THRESHOLD = 85
GENERIC_EMAIL_LOCAL_PARTS = {"info", "office", "contact", "sales", "support",
                             "admin", "help", "hello", "hr", "billing"}
ROLE_PRIORITY = [                  # CLARIFICATIONS.md target-contact priority
    "ap manager", "accounts payable", "owner", "founder", "president",
    "cfo", "office manager",
]
NON_DECISION_MAKER_ROLES = {"registered agent"}
COMPANIES_CSV = <repo>/challenge/data/companies.csv
MOCKS_JSON = <repo>/challenge/mocks/enrichment_responses.json
```

```python
# data_sources/loader.py
def load_companies(csv_path: str | Path | None = None) -> list[dict]:
    """Returns [{"company_name": str, "mailing_address": str}, ...]"""
```

```python
# data_sources/mocks.py
class MockProviderClient:
    def __init__(self, mocks_path: str | Path | None = None): ...
    def query_all(self, company_name: str) -> dict:
        """Returns {"registry": dict|None, "listing": dict|None,
        "enrichment": dict|None}. Missing provider key -> None
        (a 'not found' from that source, per mocks/README.md)."""
```

## Acceptance criteria

- [ ] `pytest contact-finder/tests/test_data_sources.py -v` passes
- [ ] `load_companies()` returns exactly 30 rows matching `companies.csv`
- [ ] `MockProviderClient.query_all("Cedar Ridge Plumbing LLC")` returns all 3
      providers populated; `query_all("Redwood Cabinetry")` (a company absent
      from the mocks) returns `{"registry": None, "listing": None,
      "enrichment": None}`
- [ ] `python run.py` and `python run_evaluation.py` run without error (stubs)

## Decisions to record

- ADR-0001: dependency versions for Python 3.13 (the `requirements.txt` in
  `INSTRUCTIONS.md` pins `pandas==2.0.3`/`numpy==1.24.3`/`scikit-learn==1.3.0`/
  `python-Levenshtein==0.21.0`, none of which ship Python 3.13 wheels).
