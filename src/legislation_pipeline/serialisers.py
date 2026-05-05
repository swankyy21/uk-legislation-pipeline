from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .extractor import LegislationRecord


class _HTML(str):
    """Marker for already-escaped HTML snippets produced by this module."""


def to_json(record: LegislationRecord, indent: int = 2) -> str:
    """Serialise a LegislationRecord to a JSON string."""
    data = _to_dict(record)
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def _to_dict(record: LegislationRecord) -> dict[str, Any]:
    """Convert record to a plain dict, converting dataclasses recursively."""
    return asdict(record)


def to_html(record: LegislationRecord) -> str:
    """Serialise a LegislationRecord to a self-contained HTML summary."""
    title = record.title or "Legislation Summary"
    enactment_date = _date_for(record, "enactment")
    modified = _display_date(record.dc_modified)
    valid = _display_date(record.dc_valid)
    extent = record.extent or record.restrict_extent
    pdf_url = record.pdf_url

    versions = [v for v in record.versions if v.relation in (None, "hasVersion")]
    if not versions and record.versions:
        versions = record.versions

    sections = [
        _row("Title", record.title),
        _row("Type", _legislation_type_label(record)),
        _row("Year", record.year),
        _row("Number", record.number),
        _row("Status", _badge(record.status)),
        _row("ISBN", record.isbn),
        _row("Enactment Date", _display_date(enactment_date)),
        _row("Last Modified", modified),
        _row("Valid From", valid),
        _row("Extent", extent),
        _row("Provisions", record.number_of_provisions),
    ]

    identifier_rows = [
        _row("Document URI", _link(record.document_uri, "View Act")),
        _row("ID URI", _link(record.uri, "Identifier")),
        _row("XML Data", _link(_format_url(record, "xml"), "data.xml")),
        _row("Original PDF", _link(pdf_url, "Download PDF")),
    ]

    format_rows = [
        _row(label, _link(url, label_text))
        for label, url, label_text in _format_rows(record)
    ]

    structure_rows = [
        _row("Introduction", _link(_link_by_title(record, "introduction"), "View")),
        _row("Main Body", _link(_link_by_title(record, "body"), "View")),
        _row("Schedules", _link(_link_by_title(record, "schedules"), "View")),
        _row("Table of Contents", _link(_toc_url(record), "View")),
        _row("Parts", record.part_count),
        _row("Chapters", record.chapter_count),
        _row("Sections", record.section_count),
        _row("Schedule Paragraphs", record.paragraph_count),
        _row("Schedules Count", record.schedule_count),
    ]

    version_rows = [_row("Total Versions", len(versions))]
    for version in versions:
        label = _display_date(version.description) or version.description or version.version_date or "Version"
        if str(label).lower() == "enacted":
            label = "Enacted"
        version_rows.append(_row(str(label), _link(version.document_uri, "View")))

    effect_rows = []
    if record.effects:
        effect = record.effects[0]
        effect_rows = [
            _row("Affecting Legislation", _link(effect.affecting_uri, effect.affecting_uri)),
            _row("Type", effect.type),
            _row("Affected Provision", effect.affected_provision),
            _row("Affecting Provision", effect.affecting_provision),
            _row("Notes", effect.note),
            _row("Comments", effect.comments),
            _row("Last Modified", _display_date(effect.modified)),
        ]

    subtitle_parts = [
        record.document_main_type,
        f"Chapter {record.number}" if record.number is not None else None,
        f"Enacted {_display_date(enactment_date)}" if enactment_date else None,
    ]
    subtitle = " &middot; ".join(_escape(part) for part in subtitle_parts if part)

    cards = [
        _card("Core Metadata", sections),
        _card("Identifiers & URIs", identifier_rows),
        _card("Available Formats", format_rows),
        _card("Structure", structure_rows),
        _card("Versions", version_rows),
    ]
    if effect_rows:
        cards.append(_card("Unapplied Effect Example", effect_rows))
    if record.long_title:
        cards.append(_card("Long Title", [_row("Text", record.long_title)]))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Legislation Summary - {_escape(title)}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      margin: 40px;
      background: #f7f9fc;
      color: #1a1a1a;
      line-height: 1.45;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
    }}
    h1 {{
      font-size: 32px;
      margin: 0 0 5px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 18px;
      border-bottom: 2px solid #ddd;
      padding-bottom: 8px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    .meta {{
      color: #555;
      margin-bottom: 30px;
    }}
    .card {{
      background: white;
      padding: 20px 25px;
      margin-bottom: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(180px, 250px) minmax(0, 1fr);
      gap: 8px 20px;
    }}
    .label {{
      font-weight: 600;
      color: #333;
    }}
    .value {{
      min-width: 0;
      overflow-wrap: anywhere;
    }}
    .value a {{
      color: #1a73e8;
      text-decoration: none;
    }}
    .value a:hover {{
      text-decoration: underline;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      background: #e3f2fd;
      color: #0b57d0;
      font-size: 13px;
      font-weight: 600;
    }}
    @media (max-width: 680px) {{
      body {{
        margin: 20px;
      }}
      .grid {{
        grid-template-columns: 1fr;
        gap: 4px 0;
      }}
      .label {{
        margin-top: 8px;
      }}
    }}
  </style>
</head>
<body>
<main>
  <h1>{_escape(title)}</h1>
  <div class="meta">{subtitle}</div>
  {"".join(cards)}
</main>
</body>
</html>
"""


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
    emit("document_category", record.document_category)
    emit("document_main_type", record.document_main_type)
    emit("year", record.year)
    emit("number", record.number)
    emit("status", record.status)
    emit("isbn", record.isbn)

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
    emit("dc_contributor", record.dc_contributor)
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
    emit("restrict_extent", record.restrict_extent)
    emit("restrict_start_date", record.restrict_start_date)
    emit("restrict_end_date", record.restrict_end_date)

    lines.append("")
    lines.append("# Structure")
    emit("section_count", record.section_count)
    emit("paragraph_count", record.paragraph_count)
    emit("part_count", record.part_count)
    emit("chapter_count", record.chapter_count)
    emit("schedule_count", record.schedule_count)
    emit("number_of_provisions", record.number_of_provisions)
    emit("statistics", record.statistics)

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
    "document_category", "document_main_type", "uri", "document_uri",
    "enactment_date", "made_date", "coming_into_force_date",
    "dc_modified", "dc_valid",
    "extent",
    "section_count", "paragraph_count", "part_count", "chapter_count", "schedule_count",
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
              "document_category", "document_main_type",
              "document_uri", "dc_modified", "dc_valid", "extent",
              "section_count", "paragraph_count", "part_count", "chapter_count", "schedule_count",
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


def _date_for(record: LegislationRecord, event: str) -> str | None:
    for item in record.dates:
        if item.event == event:
            return item.date
    return None


def _display_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    date_part = text[:10]
    try:
        parsed = datetime.strptime(date_part, "%Y-%m-%d")
        return f"{parsed.day} {parsed:%b %Y}"
    except ValueError:
        return text


def _legislation_type_label(record: LegislationRecord) -> str | None:
    if record.document_main_type and record.type:
        return f"{record.document_main_type} ({record.type})"
    return record.document_main_type or record.type


def _format_url(record: LegislationRecord, fmt: str) -> str | None:
    if fmt == "pdf" and record.pdf_url:
        return record.pdf_url
    if fmt == "html":
        for item in record.formats:
            if item.format == "html" and item.url.endswith("/data.html"):
                return item.url
    for item in record.formats:
        if item.format == fmt:
            return item.url
    return None


def _format_rows(record: LegislationRecord) -> list[tuple[str, str, str]]:
    preferred = [
        ("HTML", "html"),
        ("RDF", "rdf"),
        ("CSV", "csv"),
        ("AKN", "akn"),
        ("XML", "xml"),
        ("PDF", "pdf"),
    ]
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for label, fmt in preferred:
        url = _format_url(record, fmt)
        if url:
            rows.append((label, url, url.rsplit("/", 1)[-1]))
            seen.add(url)
    for item in record.formats:
        if item.url not in seen:
            rows.append((item.format.upper(), item.url, item.url.rsplit("/", 1)[-1]))
            seen.add(item.url)
    return rows


def _link_by_title(record: LegislationRecord, title: str) -> str | None:
    for link in record.links:
        if str(link.get("title", "")).lower() == title.lower():
            return str(link.get("href"))
    return None


def _toc_url(record: LegislationRecord) -> str | None:
    for link in record.links:
        if link.get("rel") == "http://purl.org/dc/terms/tableOfContents":
            return str(link.get("href"))
    return None


def _card(title: str, rows: list[str]) -> str:
    rows_html = "".join(row for row in rows if row)
    if not rows_html:
        return ""
    return f"""
  <section class="card">
    <h2>{_escape(title)}</h2>
    <div class="grid">
      {rows_html}
    </div>
  </section>
"""


def _row(label: str, value: Any) -> str:
    if value is None or value == "":
        return ""
    rendered = str(value) if isinstance(value, _HTML) else _escape(value)
    return (
        f'<div class="label">{_escape(label)}</div>'
        f'<div class="value">{rendered}</div>'
    )


def _link(url: Any, label: Any) -> str | None:
    if not url:
        return None
    href = _escape(str(url))
    text = _escape(str(label or url))
    return _HTML(f'<a href="{href}">{text}</a>')


def _badge(value: Any) -> str | None:
    if value is None:
        return None
    return _HTML(f'<span class="badge">{_escape(str(value).title())}</span>')


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)
