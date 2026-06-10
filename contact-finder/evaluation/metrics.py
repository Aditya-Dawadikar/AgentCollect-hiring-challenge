"""Precision/recall/F1 on the binary verified (= NOT needs_human_review)
label, plus a secondary 4-bucket classification accuracy. See ADR-0006 for
why the binary label -- not 4-bucket accuracy -- is the headline metric."""

import csv
from pathlib import Path


def precision_recall_f1(y_true: list[bool], y_pred: list[bool]) -> dict:
    """Both lists are 'verified' booleans (= NOT needs_human_review),
    positive class = True. Returns
    {"precision": float, "recall": float, "f1": float,
     "tp": int, "fp": int, "fn": int, "tn": int, "n": int}.
    Edge cases: tp+fp==0 -> precision=0.0; tp+fn==0 -> recall=0.0;
    precision+recall==0 -> f1=0.0 (no division by zero)."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "n": len(y_true),
    }


def _read_csv_rows(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_bool(value: str) -> bool:
    return value == "True"


def evaluate_predictions(predictions_csv: str | Path, ground_truth_csv: str | Path) -> dict:
    """Joins on company_name, returns precision_recall_f1(...) plus
    'classification_accuracy': float (4-bucket exact-match accuracy,
    secondary metric)."""
    predictions = {row["company_name"]: row for row in _read_csv_rows(predictions_csv)}
    ground_truth = _read_csv_rows(ground_truth_csv)

    y_true: list[bool] = []
    y_pred: list[bool] = []
    correct_buckets = 0

    for gt_row in ground_truth:
        pred_row = predictions[gt_row["company_name"]]

        y_true.append(not _to_bool(gt_row["expected_needs_human_review"]))
        y_pred.append(not _to_bool(pred_row["needs_human_review"]))

        if pred_row["classification"] == gt_row["expected_classification"]:
            correct_buckets += 1

    metrics = precision_recall_f1(y_true, y_pred)
    metrics["classification_accuracy"] = (
        correct_buckets / len(ground_truth) if ground_truth else 0.0
    )
    return metrics
