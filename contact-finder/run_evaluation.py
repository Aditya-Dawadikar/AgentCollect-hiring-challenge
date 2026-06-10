"""Evaluation entrypoint.

Generates output/results/ground_truth.csv and compares
v1_predictions.csv / v2_predictions.csv against it, writing
output/results/comparison.txt with precision/recall/F1 for each
classifier.
"""

import sys

from config import settings
from evaluation.ground_truth import write_ground_truth_csv
from evaluation.metrics import evaluate_predictions
from evaluation.reporter import write_comparison_report

OUTPUT_DIR = settings.OUTPUT_RESULTS_DIR


def main() -> None:
    v1_csv = OUTPUT_DIR / "v1_predictions.csv"
    v2_csv = OUTPUT_DIR / "v2_predictions.csv"

    if not v1_csv.exists() or not v2_csv.exists():
        print("Predictions not found. Run `python run.py` first.")
        sys.exit(1)

    ground_truth_csv = OUTPUT_DIR / "ground_truth.csv"
    write_ground_truth_csv(ground_truth_csv)

    v1_metrics = evaluate_predictions(v1_csv, ground_truth_csv)
    v2_metrics = evaluate_predictions(v2_csv, ground_truth_csv)

    comparison_path = OUTPUT_DIR / "comparison.txt"
    write_comparison_report(v1_metrics, v2_metrics, comparison_path)

    print(comparison_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
