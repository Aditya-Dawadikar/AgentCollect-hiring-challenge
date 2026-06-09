"""Shared configuration and constants for the contact-finder pipeline."""

from pathlib import Path

# contact-finder/
BASE_DIR = Path(__file__).resolve().parent.parent
# AgentCollect-hiring-challenge/
REPO_ROOT = BASE_DIR.parent

COMPANIES_CSV = REPO_ROOT / "challenge" / "data" / "companies.csv"
MOCKS_JSON = REPO_ROOT / "challenge" / "mocks" / "enrichment_responses.json"

OUTPUT_RESULTS_DIR = BASE_DIR / "output" / "results"

# CLARIFICATIONS.md: confidence < 70 -> empty contact + needs_human_review
CONFIDENCE_THRESHOLD = 70

# fuzzywuzzy token_set_ratio threshold for "same name" (see ADR-0002)
FUZZY_NAME_THRESHOLD = 85

# Local-part tokens that indicate a role-based mailbox, not a person
# (e.g. "info@example.com"). Used to discount enrichment emails that
# can't be tied to a specific decision-maker.
GENERIC_EMAIL_LOCAL_PARTS = {
    "info", "office", "contact", "sales", "support",
    "admin", "help", "hello", "hr", "billing",
}

# CLARIFICATIONS.md target-contact priority order (lowercase, for matching
# against registry "role" values).
ROLE_PRIORITY = [
    "ap manager",
    "accounts payable",
    "owner",
    "founder",
    "president",
    "cfo",
    "office manager",
]

# Roles that exist in registry data but are not the decision-maker we're
# looking for (e.g. a law firm acting as registered agent).
NON_DECISION_MAKER_ROLES = {"registered agent"}
