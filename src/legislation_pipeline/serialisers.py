from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from typing import Any

from .extractor import LegislationRecord

def to_json(record: LegislationRecord, indent: int = 2) -> str:
    """Serialise a LegislationRecord to a JSON string."""
    data = _to_dict(record)
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def _to_dict(record: LegislationRecord) -> dict[str, Any]:
    """Convert record to a plain dict, converting dataclasses recursively."""
    return asdict(record)


def to_text(record: LegislationRecord) -> str:
    lines: list[str] = []

    def emit(key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, list) and len(value) == 0:
            return
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v is not None:
                            lines.append(f"  {k}: {v}")
                    lines.append("")
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")

    emit("title", record.title)
    emit("long_title", record.long_title)
    emit("type", record.type)
    emit("year", record.year)
    emit("number", record.number)
    emit("status", record.status)

    lines.append("")
    lines.append("# Identifiers")
    emit("uri", record.uri)
    emit("document_uri", record.document_uri)
    emit("this_document_uri", record.this_document_uri)
    emit("dc_identifier", record.dc_identifier)

    lines.append("")
    lines.append("# Dates")
    for d in record.dates:
        emit(d.event + "_date", d.date)

    lines.append("")
    lines.append("# Dublin Core Metadata")
    emit("dc_title", record.dc_title)
    emit("dc_description", record.dc_description)
    emit("dc_publisher", record.dc_publisher)
    emit("dc_modified", record.dc_modified)
    emit("dc_valid", record.dc_valid)
    emit("dc_language", record.dc_language)
    emit("dc_rights", record.dc_rights)
    if record.dc_subject:
        emit("dc_subject", record.dc_subject)

    lines.append("")
    lines.append("# Available Formats")
    for fmt in record.formats:
        lang_note = f" [{fmt.language}]" if fmt.language else ""
        lines.append(f"  {fmt.format}{lang_note}: {fmt.url}")
    emit("pdf_url", record.pdf_url)

    lines.append("")
    lines.append("# Geographic Extent")
    emit("extent", record.extent)
    emit("extent_uri", record.extent_uri)

    lines.append("")
    lines.append("# Structure")
    emit("section_count", record.section_count)
    emit("part_count", record.part_count)
    emit("chapter_count", record.chapter_count)
    emit("schedule_count", record.schedule_count)

    if record.contents:
        lines.append("")
        lines.append("# Table of Contents")
        for item in record.contents:
            indent = "  " if item.level in ("section", "schedule", "chapter") else ""
            num = f"{item.number} " if item.number else ""
            title = item.title or "(untitled)"
            lines.append(f"  {indent}[{item.level}] {num}{title}")

    if record.versions:
        lines.append("")
        lines.append("# Versions")
        for v in record.versions:
            desc = v.description or ""
            date = v.version_date or ""
            uri = v.document_uri or ""
            lines.append(f"  {date} {desc} — {uri}".strip(" —"))

    lines.append("")
    lines.append("# Effects / Amendments")
    emit("unapplied_effects_count", record.unapplied_effects_count)
    emit("applied_effects_count", record.applied_effects_count)
    emit("total_effects", len(record.effects))

    if record.powers_conferred:
        lines.append("")
        lines.append("# Powers Conferred")
        for p in record.powers_conferred:
            lines.append(f"  provision: {p.provision or '?'}  function: {p.function or '?'}")

    if record.commentary:
        lines.append("")
        lines.append(f"# Commentary ({len(record.commentary)} items)")

    lines.append("")
    lines.append("# Pipeline")
    emit("source_url", record.source_url)
    emit("extracted_at", record.extracted_at)
    emit("schema_version", record.schema_version)

    return "\n".join(lines)


_CSV_FIELDS = [
    "title", "type", "year", "number", "status",
    "uri", "document_uri",
    "enactment_date", "made_date", "coming_into_force_date",
    "dc_modified", "dc_valid",
    "extent",
    "section_count", "part_count", "chapter_count", "schedule_count",
    "unapplied_effects_count", "applied_effects_count",
    "pdf_url",
    "format_count",
    "source_url",
    "extracted_at",
]


def to_csv(records: list[LegislationRecord], include_header: bool = True) -> str:
    """
    Serialise a list of LegislationRecords to a flat CSV string.

    Each record becomes a single row with summary columns.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    if include_header:
        writer.writeheader()
    for record in records:
        row = _flatten_record(record)
        writer.writerow(row)
    return buf.getvalue()


def _flatten_record(record: LegislationRecord) -> dict[str, Any]:
    """Flatten a record to a single dict for CSV output."""
    row: dict[str, Any] = {}

    # Simple scalar fields
    for f in ["title", "type", "year", "number", "status", "uri",
              "document_uri", "dc_modified", "dc_valid", "extent",
              "section_count", "part_count", "chapter_count", "schedule_count",
              "unapplied_effects_count", "applied_effects_count",
              "pdf_url", "source_url", "extracted_at"]:
        row[f] = getattr(record, f, None)

    # Dates
    date_map: dict[str, str] = {}
    for d in record.dates:
        # Keep first occurrence of each event type
        key = d.event.replace("-", "_") + "_date"
        if key not in date_map:
            date_map[key] = d.date

    row["enactment_date"] = date_map.get("enactment_date")
    row["made_date"] = date_map.get("made_date")
    row["coming_into_force_date"] = date_map.get("coming_into_force_date")

    row["format_count"] = len(record.formats)

    return row