import csv

import pytest

from data_comparison.conflict_resolver import ConflictResolver
from data_comparison.email_matcher import EmailMatcher
from data_comparison.fuzzy_matcher import FuzzyNameMatcher
from data_comparison.phone_matcher import PhoneMatcher
from data_comparison.signal_fusion import SignalFusionEngine
from data_sources.mocks import MockProviderClient
from classification.v1_rule_based import RuleBasedClassifier
from output.formatter import build_reason, format_output_row, write_predictions_csv

import run


@pytest.fixture
def fusion_engine():
    return SignalFusionEngine(
        mock_client=MockProviderClient(),
        name_matcher=FuzzyNameMatcher(),
        email_matcher=EmailMatcher(),
        phone_matcher=PhoneMatcher(),
        conflict_resolver=ConflictResolver(),
    )


@pytest.fixture
def classifier():
    return RuleBasedClassifier()


# --- output.formatter.build_reason -----------------------------------------

def test_build_reason_no_data():
    signals = {"sources_count": 0, "has_conflict": False, "generic_email": False}
    assert build_reason(signals, 0, 70) == "No data available from any source."


def test_build_reason_conflict():
    signals = {"sources_count": 2, "has_conflict": True, "generic_email": False}
    assert build_reason(signals, 25, 70) == "Registry and listing disagree on contact identity."


def test_build_reason_generic_single_source():
    signals = {"sources_count": 1, "has_conflict": False, "generic_email": True}
    assert build_reason(signals, 0, 70) == "Single weak source with a generic contact email."


def test_build_reason_below_threshold():
    signals = {"sources_count": 1, "has_conflict": False, "generic_email": False}
    assert build_reason(signals, 40, 70) == "Confidence 40 below threshold 70."


def test_build_reason_verified():
    signals = {"sources_count": 3, "has_conflict": False, "generic_email": False}
    assert build_reason(signals, 95, 70) == "Verified via 3 agreeing source(s)."


# --- output.formatter.format_output_row -------------------------------------

def test_format_output_row_cedar_ridge_verified(fusion_engine, classifier):
    fc = fusion_engine.fuse("Cedar Ridge Plumbing LLC", "4821 Maple Ave, Lincoln, NE 68504")
    result = classifier.score(fc.signals)

    row = format_output_row(fc, result)

    assert row["company_name"] == "Cedar Ridge Plumbing LLC"
    assert row["contact_name"] == "Daniel Ortega"
    assert row["contact_role"] == "Owner"
    assert row["contact_email_or_phone"] == "d.ortega@cedarridgeplumbing.com"
    assert row["needs_human_review"] is False
    assert set(row["source"].split(",")) == {"registry", "listing", "enrichment"}
    for field in ("name", "role", "email"):
        assert f"{field}:" in row["source_urls"]
    assert row["reason"] == "Verified via 3 agreeing source(s)."


def test_format_output_row_riverside_needs_review(fusion_engine, classifier):
    fc = fusion_engine.fuse("Riverside Print & Sign", "302 W 3rd St, Davenport, IA 52801")
    result = classifier.score(fc.signals)

    row = format_output_row(fc, result)

    assert row["contact_name"] == ""
    assert row["contact_role"] == ""
    assert row["contact_email_or_phone"] == ""
    assert row["needs_human_review"] is True
    assert "mock://enrichment/riverside-print-sign" in row["source_urls"]
    assert "generic contact email" in row["reason"]


def test_write_predictions_csv(tmp_path, fusion_engine, classifier):
    fc = fusion_engine.fuse("Cedar Ridge Plumbing LLC", "4821 Maple Ave, Lincoln, NE 68504")
    result = classifier.score(fc.signals)
    row = format_output_row(fc, result)

    path = tmp_path / "predictions.csv"
    write_predictions_csv([row], path)

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["company_name"] == "Cedar Ridge Plumbing LLC"
    assert list(rows[0].keys()) == list(row.keys())


# --- run.main: full 30-company pipeline -------------------------------------

def test_run_main_writes_predictions_for_every_company(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "OUTPUT_DIR", tmp_path)

    run.main()

    for filename in ("v1_predictions.csv", "v2_predictions.csv"):
        path = tmp_path / filename
        assert path.exists()

        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 30
        for row in rows:
            assert row["classification"] in {"high", "medium", "low", "cannot_verify"}
            if row["needs_human_review"] == "False":
                assert row["source_urls"] != ""
