"""TICKET-004 zero-budget contact finder.

Three real US SMBs, each with a (company_name, mailing_address) seed and
real/free-source records for the "registry", "listing", and "enrichment"
providers (see NOTES.md for source rationale and URLs). Reuses the exact
same SignalFusionEngine / matchers / classifiers (v1 rule-based, v2
decision-tree) as run.py -- only the provider client is swapped for one
backed by real data instead of challenge/mocks/enrichment_responses.json.
"""

from classification.v1_rule_based import RuleBasedClassifier
from classification.v2_decision_tree import DecisionTreeConfidenceClassifier
from config import settings
from data_comparison.conflict_resolver import ConflictResolver
from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher
from data_comparison.signal_fusion import SignalFusionEngine
from output.formatter import format_output_row, write_predictions_csv

OUTPUT_DIR = settings.OUTPUT_RESULTS_DIR

# Real, free, publicly-checkable records gathered for 3 real US SMBs.
# registry  -> BBB Business Profile (lists verified "Business Management" /
#              owner contact -- closest free analog to an authoritative
#              business registry of "who runs this business").
# listing   -> Yelp business listing (address + phone).
# enrichment -> the company's own website About/Contact page (self-reported,
#              same "weak, self-reported confidence" framing as the mock
#              enrichment provider).
REAL_RECORDS = {
    "Casey's Independent Auto Repair": {
        "mailing_address": "11610 NE 65th St, Vancouver, WA 98662",
        "registry": {
            "name": "Paul McGowan",
            "role": "Owner",
            "source_url": "https://www.bbb.org/us/wa/vancouver/profile/auto-repair/caseys-independent-auto-repair-1296-72000185",
        },
        "listing": {
            "name": None,
            "phone": "(360) 253-7111",
            "source_url": "https://www.yelp.com/biz/caseys-independent-auto-repair-vancouver",
        },
        "enrichment": {
            "email": "service@caseysia.com",
            "phone": "(360) 253-7111",
            "provider_confidence": 50,
            "source_url": "https://caseysindependentauto.com/contact-us/",
        },
    },
    "My Dad's Plumbing": {
        "mailing_address": "San Dimas, CA 91773",
        "registry": {
            "name": "Joe Atto",
            "role": "Owner",
            "source_url": "https://www.bbb.org/us/ca/san-diego/profile/plumber/my-dads-plumbing-1126-1000059807",
        },
        "listing": {
            "name": None,
            "phone": "(909) 542-9394",
            "source_url": "https://www.yelp.com/biz/my-dads-plumbing-san-dimas",
        },
        # mydadsplumbing.com returns HTTP 403 to automated fetches -- no
        # usable enrichment record could be obtained (the "hard row").
        "enrichment": None,
    },
    "The Print House": {
        "mailing_address": "200 Maplewood St, Malden, MA 02148",
        "registry": {
            "name": "Greg Doucette",
            "role": "Owner",
            "source_url": "https://www.bbb.org/us/ma/malden/profile/printers/the-print-house-0021-11033",
        },
        "listing": {
            "name": None,
            "phone": "(781) 324-4455",
            "source_url": "https://www.yelp.com/biz/the-print-house-malden-2",
        },
        "enrichment": {
            "email": None,
            "phone": "1-781-324-4455",
            "provider_confidence": 75,
            "source_url": "https://www.printhouse.com/about",
        },
    },
}


class RealProviderClient:
    """`query_all()` interface compatible with MockProviderClient, backed by
    REAL_RECORDS instead of challenge/mocks/enrichment_responses.json."""

    def __init__(self, records: dict):
        self._records = records

    def query_all(self, company_name: str) -> dict:
        record = self._records.get(company_name, {})
        return {
            provider: record.get(provider)
            for provider in ("registry", "listing", "enrichment")
        }


def main() -> None:
    fusion_engine = SignalFusionEngine(
        mock_client=RealProviderClient(REAL_RECORDS),
        name_matcher=FuzzyNameMatcher(),
        email_matcher=EmailMatcher(),
        phone_matcher=PhoneMatcher(),
        conflict_resolver=ConflictResolver(),
    )
    v1 = RuleBasedClassifier()
    v2 = DecisionTreeConfidenceClassifier()

    v1_rows = []
    v2_rows = []

    for company_name, record in REAL_RECORDS.items():
        fused = fusion_engine.fuse(company_name, record["mailing_address"])

        v1_result = v1.score(fused.signals)
        v2_result = v2.score(fused.signals)

        v1_rows.append(format_output_row(fused, v1_result))
        v2_rows.append(format_output_row(fused, v2_result))

        print(f"{company_name}")
        print(f"  signals: {fused.signals}")
        print(
            f"  v1={v1_result['classification']}({v1_result['confidence_score']}, "
            f"review={v1_result['needs_human_review']}) "
            f"v2={v2_result['classification']}({v2_result['confidence_score']}, "
            f"review={v2_result['needs_human_review']})"
        )

    write_predictions_csv(v1_rows, OUTPUT_DIR / "ticket004_v1_predictions.csv")
    write_predictions_csv(v2_rows, OUTPUT_DIR / "ticket004_v2_predictions.csv")


if __name__ == "__main__":
    main()
