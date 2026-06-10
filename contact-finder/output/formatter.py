"""Builds the final per-row output schema (with provenance) and writes
predictions CSVs. See ADR-0007 for the schema extensions beyond the minimal
CLARIFICATIONS.md fields (`classification`, `source_urls`, `reason`)."""

import csv
from pathlib import Path

from config import settings
from data_comparison.signal_fusion import FusedContact

OUTPUT_COLUMNS = [
    "company_name",
    "contact_name",
    "contact_role",
    "contact_email_or_phone",
    "confidence_score",
    "classification",
    "source",
    "needs_human_review",
    "source_urls",
    "reason",
]


def build_reason(signals: dict, confidence_score: int, threshold: int) -> str:
    """Short human-readable explanation for a confidence_score, in priority
    order: no data, identity conflict, lone generic email, below threshold,
    or verified."""
    if signals["sources_count"] == 0:
        return "No data available from any source."
    if signals["has_conflict"]:
        return "Registry and listing disagree on contact identity."
    if signals["generic_email"] and signals["sources_count"] == 1:
        return "Single weak source with a generic contact email."
    if confidence_score < threshold:
        return f"Confidence {confidence_score} below threshold {threshold}."
    return f"Verified via {signals['sources_count']} agreeing source(s)."


def _provider_from_url(url: str) -> str:
    """mock://<provider>/... -> <provider>"""
    return url.split("//", 1)[1].split("/", 1)[0]


def _format_source_urls(fused: FusedContact) -> str:
    """field:provider:url|field:provider:url, always populated when data
    exists -- including on review rows -- for audit trail."""
    parts = [
        f"{field}:{_provider_from_url(url)}:{url}"
        for field, urls in fused.source_urls.items()
        for url in urls
    ]
    return "|".join(parts)


def format_output_row(fused: FusedContact, result: dict,
                       threshold: int = settings.CONFIDENCE_THRESHOLD) -> dict:
    """Builds the output schema. contact_email_or_phone = fused.candidate_email
    or fused.candidate_phone (email preferred). Blanks contact_name/
    contact_role/contact_email_or_phone when result['needs_human_review']."""
    needs_review = result["needs_human_review"]
    contact_email_or_phone = fused.candidate_email or fused.candidate_phone or ""

    return {
        "company_name": fused.company_name,
        "contact_name": "" if needs_review else (fused.candidate_name or ""),
        "contact_role": "" if needs_review else (fused.candidate_role or ""),
        "contact_email_or_phone": "" if needs_review else contact_email_or_phone,
        "confidence_score": result["confidence_score"],
        "classification": result["classification"],
        "source": ",".join(fused.sources),
        "needs_human_review": needs_review,
        "source_urls": _format_source_urls(fused),
        "reason": build_reason(fused.signals, result["confidence_score"], threshold),
    }


def write_predictions_csv(rows: list[dict], path: str | Path) -> None:
    """csv.DictWriter with the schema's keys as header, in order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
