import csv

import pytest

from evaluation.ground_truth import GROUND_TRUTH, write_ground_truth_csv
from evaluation.metrics import evaluate_predictions, precision_recall_f1
from evaluation.reporter import write_comparison_report

GROUND_TRUTH_COLUMNS = {
    "company_name",
    "expected_needs_human_review",
    "expected_classification",
    "rationale",
}

ZERO_SOURCE_COMPANIES = {
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
}

MOCK_BACKED_COMPANIES = {
    "Cedar Ridge Plumbing LLC",
    "Pioneer Landscaping Inc",
    "Harbor Light Electric",
    "Greenfield Catering Group",
    "Riverside Print & Sign",
    "Coastal Breeze Pool Service",
}


# --- evaluation.ground_truth -----------------------------------------------

def test_ground_truth_has_eighteen_rows_with_expected_columns():
    assert len(GROUND_TRUTH) == 18
    for row in GROUND_TRUTH:
        assert set(row.keys()) == GROUND_TRUTH_COLUMNS
        assert isinstance(row["expected_needs_human_review"], bool)
        assert row["expected_classification"] in {"high", "medium", "low", "cannot_verify"}
        assert row["rationale"]


def test_ground_truth_covers_zero_source_and_mock_backed_companies():
    company_names = {row["company_name"] for row in GROUND_TRUTH}

    assert company_names == ZERO_SOURCE_COMPANIES | MOCK_BACKED_COMPANIES

    by_name = {row["company_name"]: row for row in GROUND_TRUTH}
    for company in ZERO_SOURCE_COMPANIES:
        assert by_name[company]["expected_needs_human_review"] is True
        assert by_name[company]["expected_classification"] == "cannot_verify"


def test_ground_truth_hand_judged_labels():
    by_name = {row["company_name"]: row for row in GROUND_TRUTH}

    assert by_name["Cedar Ridge Plumbing LLC"]["expected_needs_human_review"] is False
    assert by_name["Cedar Ridge Plumbing LLC"]["expected_classification"] == "high"

    assert by_name["Pioneer Landscaping Inc"]["expected_needs_human_review"] is False
    assert by_name["Pioneer Landscaping Inc"]["expected_classification"] == "high"

    assert by_name["Harbor Light Electric"]["expected_needs_human_review"] is False
    assert by_name["Harbor Light Electric"]["expected_classification"] == "medium"

    assert by_name["Greenfield Catering Group"]["expected_needs_human_review"] is False
    assert by_name["Greenfield Catering Group"]["expected_classification"] == "medium"

    assert by_name["Riverside Print & Sign"]["expected_needs_human_review"] is True
    assert by_name["Riverside Print & Sign"]["expected_classification"] == "cannot_verify"

    assert by_name["Coastal Breeze Pool Service"]["expected_needs_human_review"] is True
    assert by_name["Coastal Breeze Pool Service"]["expected_classification"] == "low"


def test_write_ground_truth_csv(tmp_path):
    path = tmp_path / "ground_truth.csv"
    write_ground_truth_csv(path)

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 18
    assert set(rows[0].keys()) == GROUND_TRUTH_COLUMNS
    assert {row["company_name"] for row in rows} == ZERO_SOURCE_COMPANIES | MOCK_BACKED_COMPANIES


# --- evaluation.metrics.precision_recall_f1 ---------------------------------

def test_precision_recall_f1_basic():
    result = precision_recall_f1([True, True, False], [True, False, False])

    assert result["tp"] == 1
    assert result["fp"] == 0
    assert result["fn"] == 1
    assert result["tn"] == 1
    assert result["n"] == 3
    assert result["precision"] == 1.0
    assert result["recall"] == 0.5
    assert result["f1"] == pytest.approx(0.667, abs=1e-3)


def test_precision_recall_f1_empty_lists():
    result = precision_recall_f1([], [])

    assert result == {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "n": 0,
    }


def test_precision_recall_f1_no_predicted_positives():
    # tp + fp == 0 -> precision defined as 0.0, no division by zero
    result = precision_recall_f1([True, False], [False, False])

    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0


# --- evaluation.metrics.evaluate_predictions --------------------------------

def _write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_evaluate_predictions_small_fixture(tmp_path):
    ground_truth_csv = tmp_path / "ground_truth.csv"
    predictions_csv = tmp_path / "predictions.csv"

    _write_csv(
        ground_truth_csv,
        ["company_name", "expected_needs_human_review", "expected_classification", "rationale"],
        [
            {"company_name": "A", "expected_needs_human_review": False, "expected_classification": "high", "rationale": "r"},
            {"company_name": "B", "expected_needs_human_review": False, "expected_classification": "medium", "rationale": "r"},
            {"company_name": "C", "expected_needs_human_review": True, "expected_classification": "cannot_verify", "rationale": "r"},
            {"company_name": "D", "expected_needs_human_review": True, "expected_classification": "low", "rationale": "r"},
        ],
    )
    _write_csv(
        predictions_csv,
        ["company_name", "needs_human_review", "classification"],
        [
            {"company_name": "A", "needs_human_review": False, "classification": "high"},   # tp, bucket match
            {"company_name": "B", "needs_human_review": True, "classification": "medium"},  # fn, bucket match
            {"company_name": "C", "needs_human_review": True, "classification": "low"},      # tn, bucket mismatch
            {"company_name": "D", "needs_human_review": False, "classification": "low"},     # fp, bucket match
        ],
    )

    result = evaluate_predictions(predictions_csv, ground_truth_csv)

    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1
    assert result["n"] == 4
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["classification_accuracy"] == 0.75


# --- evaluation.reporter.write_comparison_report ----------------------------

def test_write_comparison_report(tmp_path):
    # n=10, ground truth says 6 should be verified / 4 should be reviewed
    # (fp+tn == 4, tp+fn == 6 for both, since both are scored against the
    # same ground truth labels).
    v1_metrics = {
        "precision": 5 / 6, "recall": 5 / 6, "f1": 5 / 6,
        "tp": 5, "fp": 1, "fn": 1, "tn": 3, "n": 10,
        "classification_accuracy": 0.7,
    }
    v2_metrics = {
        "precision": 1.0, "recall": 4 / 6, "f1": 0.8,
        "tp": 4, "fp": 0, "fn": 2, "tn": 4, "n": 10,
        "classification_accuracy": 0.6,
    }

    path = tmp_path / "comparison.txt"
    write_comparison_report(v1_metrics, v2_metrics, path)

    content = path.read_text(encoding="utf-8")

    assert "v1" in content and "v2" in content
    assert "0.833" in content  # v1 precision/recall/f1
    assert "1.000" in content  # v2 precision

    verdict = content.splitlines()[-1]
    assert verdict.startswith("Verdict:")
    assert "v2 (decision tree) has higher precision" in verdict
    assert "0.400" in verdict  # v1 review rate and ground truth review rate
    assert "0.600" in verdict  # v2 review rate
