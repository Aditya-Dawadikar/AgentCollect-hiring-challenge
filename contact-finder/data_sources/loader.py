"""Loads the input CSV of companies + mailing addresses."""

import csv
from pathlib import Path

from config import settings


def load_companies(csv_path: str | Path | None = None) -> list[dict]:
    """Returns a list of {"company_name": str, "mailing_address": str}."""
    path = Path(csv_path) if csv_path else settings.COMPANIES_CSV
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {
                "company_name": row["company_name"],
                "mailing_address": row["mailing_address"],
            }
            for row in reader
        ]
