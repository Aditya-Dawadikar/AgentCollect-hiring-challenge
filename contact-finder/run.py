"""Contact Finder pipeline entrypoint.

Reads challenge/data/companies.csv, fuses signals from the three mock
providers, scores each company with both classifiers (v1 rule-based, v2
decision-tree), and writes output/results/v1_predictions.csv and
v2_predictions.csv.
"""

from classification.v1_rule_based import RuleBasedClassifier
from classification.v2_decision_tree import DecisionTreeConfidenceClassifier
from config import settings
from data_comparison.conflict_resolver import ConflictResolver
from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher
from data_comparison.signal_fusion import SignalFusionEngine
from data_sources.loader import load_companies
from data_sources.mocks import MockProviderClient
from output.formatter import format_output_row, write_predictions_csv

OUTPUT_DIR = settings.OUTPUT_RESULTS_DIR


def main() -> None:
    companies = load_companies()

    fusion_engine = SignalFusionEngine(
        mock_client=MockProviderClient(),
        name_matcher=FuzzyNameMatcher(),
        email_matcher=EmailMatcher(),
        phone_matcher=PhoneMatcher(),
        conflict_resolver=ConflictResolver(),
    )
    v1 = RuleBasedClassifier()
    v2 = DecisionTreeConfidenceClassifier()

    v1_rows = []
    v2_rows = []

    for company in companies:
        fused = fusion_engine.fuse(company["company_name"], company["mailing_address"])

        v1_result = v1.score(fused.signals)
        v2_result = v2.score(fused.signals)

        v1_rows.append(format_output_row(fused, v1_result))
        v2_rows.append(format_output_row(fused, v2_result))

        print(
            f"{company['company_name']}: "
            f"v1={v1_result['classification']}({v1_result['confidence_score']}, "
            f"review={v1_result['needs_human_review']}) "
            f"v2={v2_result['classification']}({v2_result['confidence_score']}, "
            f"review={v2_result['needs_human_review']})"
        )

    write_predictions_csv(v1_rows, OUTPUT_DIR / "v1_predictions.csv")
    write_predictions_csv(v2_rows, OUTPUT_DIR / "v2_predictions.csv")


if __name__ == "__main__":
    main()
