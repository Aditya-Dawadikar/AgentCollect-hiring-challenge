"""Plain-text v1-vs-v2 comparison report. See ADR-0006 for what these
metrics mean and how the ground truth set was built."""

from pathlib import Path

_METRIC_LABELS = {
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
    "classification_accuracy": "Classification accuracy (4-bucket)",
}


def _review_rate(metrics: dict) -> float:
    """Fraction of companies this classifier marked needs_human_review."""
    return (metrics["fn"] + metrics["tn"]) / metrics["n"] if metrics["n"] else 0.0


def _ground_truth_review_rate(metrics: dict) -> float:
    """Fraction of companies ground truth says should be reviewed. Same for
    v1 and v2 metrics (both scored against the same ground truth labels)."""
    return (metrics["fp"] + metrics["tn"]) / metrics["n"] if metrics["n"] else 0.0


def _format_table(name: str, metrics: dict) -> list[str]:
    lines = [name, "-" * len(name)]
    for key, label in _METRIC_LABELS.items():
        lines.append(f"  {label}: {metrics[key]:.3f}")
    lines.append(
        f"  Confusion (verified=positive): tp={metrics['tp']} fp={metrics['fp']} "
        f"fn={metrics['fn']} tn={metrics['tn']} n={metrics['n']}"
    )
    lines.append(f"  Review rate: {_review_rate(metrics):.3f}")
    return lines


def write_comparison_report(v1_metrics: dict, v2_metrics: dict, path: str | Path) -> None:
    """Writes a plain-text comparison.txt: both metrics tables side by side
    + a one-line verdict (which classifier has higher precision, and the
    review-rate of each vs. ground truth's review rate)."""
    lines = [
        "Contact Finder: v1 (rule-based) vs v2 (decision tree) classifier comparison",
        "=" * 76,
        "",
    ]
    lines += _format_table("v1 (rule-based)", v1_metrics)
    lines.append("")
    lines += _format_table("v2 (decision tree)", v2_metrics)
    lines.append("")

    if v1_metrics["precision"] > v2_metrics["precision"]:
        winner = "v1 (rule-based)"
    elif v2_metrics["precision"] > v1_metrics["precision"]:
        winner = "v2 (decision tree)"
    else:
        winner = "v1 and v2 (tied)"

    lines.append(
        f"Verdict: {winner} has higher precision "
        f"(v1={v1_metrics['precision']:.3f}, v2={v2_metrics['precision']:.3f}); "
        f"review rate v1={_review_rate(v1_metrics):.3f}, "
        f"v2={_review_rate(v2_metrics):.3f}, "
        f"ground truth={_ground_truth_review_rate(v1_metrics):.3f}."
    )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
