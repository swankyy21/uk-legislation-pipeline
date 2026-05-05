from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from xml.etree.ElementTree import Element

from .namespaces import NS, xpath, xpath_all, attr, text_or_none


# ---------------------------------------------------------------------------
# Schema dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DateInfo:
    """A dated event associated with the legislation."""
    event: str          # e.g. "enactment", "made", "laid", "coming-into-force"
    date: str           # ISO 8601 date string


@dataclass
class FormatLink:
    """A link to a specific format/representation of the legislation."""
    format: str         # e.g. "xml", "html", "pdf", "rdf"
    url: str
    language: Optional[str] = None


@dataclass
class VersionInfo:
    """A point-in-time or named version of the legislation."""
    version_date: Optional[str] = None
    description: Optional[str] = None
    document_uri: Optional[str] = None


@dataclass
class ContentsItem:
    """A single item in the table of contents."""
    number: Optional[str]
    title: Optional[str]
    id: Optional[str]
    document_uri: Optional[str]
    level: str          # "part", "chapter", "section", "schedule", etc.


@dataclass
class Effect:
    """An unapplied or applied amendment effect."""
    effect_id: Optional[str]
    type: Optional[str]
    affected_uri: Optional[str]
    affecting_uri: Optional[str]
    affected_provision: Optional[str]
    affecting_provision: Optional[str]
    in_force: Optional[str]
    in_force_notes: Optional[str]
    note: Optional[str]
    applied: Optional[bool]
    required_amendments: list[str] = field(default_factory=list)


@dataclass
class PowerConferred:
    """A power to make secondary legislation conferred by this Act."""
    uri: Optional[str]
    provision: Optional[str]
    function: Optional[str]
    body: Optional[str]


@dataclass
class LegislationRecord:
    """
    Complete structured representation of a UK legislation document.
    All fields are extracted verbatim from the CLML XML; None indicates
    the field was not present in the source document.
    """
    # --- Identity ---
    title: Optional[str] = None
    long_title: Optional[str] = None
    type: Optional[str] = None           # e.g. "ukpga", "uksi"
    year: Optional[int] = None
    number: Optional[int] = None
    status: Optional[str] = None         # e.g. "revised", "enacted"

    # --- URIs & Identifiers ---
    uri: Optional[str] = None            # Identifier URI (id/)
    document_uri: Optional[str] = None   # Document URI (no /id/)
    this_document_uri: Optional[str] = None

    # --- Dates ---
    dates: list[DateInfo] = field(default_factory=list)

    # --- Dublin Core Metadata ---
    dc_title: Optional[str] = None
    dc_description: Optional[str] = None
    dc_publisher: Optional[str] = None
    dc_subject: list[str] = field(default_factory=list)
    dc_modified: Optional[str] = None
    dc_valid: Optional[str] = None
    dc_language: Optional[str] = None
    dc_format: Optional[str] = None
    dc_type: Optional[str] = None
    dc_rights: Optional[str] = None
    dc_identifier: Optional[str] = None

    # --- Formats & Links ---
    formats: list[FormatLink] = field(default_factory=list)
    pdf_url: Optional[str] = None        # Primary PDF (convenience field)

    # --- Versions ---
    versions: list[VersionInfo] = field(default_factory=list)

    # --- Geographic Extent ---
    extent: Optional[str] = None
    extent_uri: Optional[str] = None

    # --- Structure ---
    contents: list[ContentsItem] = field(default_factory=list)
    schedule_count: int = 0
    section_count: int = 0
    part_count: int = 0
    chapter_count: int = 0

    # --- Changes / Effects ---
    effects: list[Effect] = field(default_factory=list)
    unapplied_effects_count: int = 0
    applied_effects_count: int = 0

    # --- Powers Conferred (revised only) ---
    powers_conferred: list[PowerConferred] = field(default_factory=list)

    # --- Notes ---
    commentary: list[dict] = field(default_factory=list)

    # --- Pipeline metadata ---
    source_url: Optional[str] = None
    extracted_at: Optional[str] = None
    schema_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class CLMLExtractor:
    """
    Extracts all structured data from a parsed CLML XML tree.

    Usage::

        extractor = CLMLExtractor(root_element, source_url="https://...")
        record = extractor.extract()
    """

    def __init__(self, root: Element, source_url: str = ""):
        self.root = root
        self.source_url = source_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self) -> LegislationRecord:
        record = LegislationRecord(source_url=self.source_url)

        self._extract_identity(record)
        self._extract_metadata(record)
        self._extract_dates(record)
        self._extract_formats(record)
        self._extract_versions(record)
        self._extract_extent(record)
        self._extract_contents(record)
        self._extract_effects(record)
        self._extract_powers(record)
        self._extract_commentary(record)
        self._extract_structure_counts(record)

        return record

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def _extract_identity(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        primary = meta.find(xpath("ukm:PrimaryMetadata")) or meta.find(xpath("ukm:SecondaryMetadata"))
        if primary is None:
            # Try common fallbacks
            primary = meta.find(xpath("ukm:EUMetadata")) or meta

        # Document type
        doc_type = primary.find(xpath("ukm:DocumentClassification/ukm:DocumentMainType")) if primary else None
        if doc_type is not None:
            record.type = attr(doc_type, "Value", "").lower() or None

        # Year
        year_el = primary.find(xpath("ukm:Year")) if primary else None
        if year_el is not None:
            try:
                record.year = int(attr(year_el, "Value", ""))
            except (ValueError, TypeError):
                pass

        # Number
        number_el = primary.find(xpath("ukm:Number")) if primary else None
        if number_el is not None:
            try:
                record.number = int(attr(number_el, "Value", ""))
            except (ValueError, TypeError):
                pass

        # Status (enacted / revised)
        status_el = primary.find(xpath("ukm:DocumentStatus")) if primary else None
        if status_el is not None:
            record.status = attr(status_el, "Value") or None

        # Schema version (from root element)
        record.schema_version = attr(self.root, "SchemaVersion") or None

        # Title  — prefer dc:title, will be set in _extract_metadata
        # but also try the TitleBlock in the body
        title_el = self.root.find(xpath("leg:Body/leg:TitleBlock/leg:Title"))
        if title_el is None:
            title_el = self.root.find(xpath("leg:Primary/leg:PrimaryPrelims/leg:Title"))
        if title_el is not None:
            record.title = "".join(title_el.itertext()).strip() or None

        # Long title / preamble
        long_title_el = (
            self.root.find(xpath("leg:Primary/leg:PrimaryPrelims/leg:LongTitle"))
            or self.root.find(xpath("leg:Secondary/leg:SecondaryPrelims/leg:LongTitle"))
        )
        if long_title_el is not None:
            record.long_title = "".join(long_title_el.itertext()).strip() or None

    # ------------------------------------------------------------------
    # Dublin Core & UKM Metadata
    # ------------------------------------------------------------------

    def _extract_metadata(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        # Dublin Core fields
        record.dc_title = text_or_none(meta, "dc:title")
        record.dc_description = text_or_none(meta, "dc:description")
        record.dc_publisher = text_or_none(meta, "dc:publisher")
        record.dc_modified = text_or_none(meta, "dc:modified") or text_or_none(meta, "dct:modified")
        record.dc_valid = text_or_none(meta, "dc:valid") or text_or_none(meta, "dct:valid")
        record.dc_language = text_or_none(meta, "dc:language")
        record.dc_format = text_or_none(meta, "dc:format")
        record.dc_type = text_or_none(meta, "dc:type")
        record.dc_rights = text_or_none(meta, "dc:rights")
        record.dc_identifier = text_or_none(meta, "dc:identifier")

        # Multiple subjects
        record.dc_subject = [
            el.text.strip()
            for el in xpath_all(meta, "dc:subject")
            if el.text and el.text.strip()
        ]

        # If we still have no title, use dc_title
        if not record.title and record.dc_title:
            record.title = record.dc_title

        # URIs
        id_el = meta.find(xpath("ukm:PrimaryMetadata/ukm:Identifier")) \
               or meta.find(xpath("ukm:SecondaryMetadata/ukm:Identifier")) \
               or meta.find(xpath("ukm:Identifier"))
        if id_el is not None:
            record.uri = attr(id_el, "URI") or None

        # DocumentURI from the Metadata element itself or its children
        record.document_uri = attr(meta, "DocumentURI") or None
        if not record.document_uri:
            doc_el = meta.find(xpath("ukm:Document"))
            if doc_el is not None:
                record.document_uri = attr(doc_el, "URI") or None

        record.this_document_uri = attr(meta, "ThisDocumentURI") or None

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------

    def _extract_dates(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        # Check both Primary and Secondary metadata containers
        containers = (
            meta.findall(xpath("ukm:PrimaryMetadata"))
            + meta.findall(xpath("ukm:SecondaryMetadata"))
            + meta.findall(xpath("ukm:EUMetadata"))
            + [meta]
        )

        date_tag_map = {
            "ukm:EnactmentDate": "enactment",
            "ukm:MadeDate": "made",
            "ukm:LaidDate": "laid",
            "ukm:ComingIntoForce": "coming-into-force",
            "ukm:Sifted": "sifted",
            "ukm:Superseded": "superseded",
        }

        seen: set[tuple[str, str]] = set()

        for container in containers:
            for tag, event in date_tag_map.items():
                for el in xpath_all(container, tag):
                    # ComingIntoForce may have children with dates
                    if tag == "ukm:ComingIntoForce":
                        for date_el in xpath_all(el, "ukm:Date"):
                            d = attr(date_el, "Date")
                            if d and (event, d) not in seen:
                                record.dates.append(DateInfo(event=event, date=d))
                                seen.add((event, d))
                    else:
                        d = attr(el, "Date")
                        if d and (event, d) not in seen:
                            record.dates.append(DateInfo(event=event, date=d))
                            seen.add((event, d))

    # ------------------------------------------------------------------
    # Available formats
    # ------------------------------------------------------------------

    def _extract_formats(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        format_map = {
            "ukm:XMLVersion": "xml",
            "ukm:HTMLVersion": "html",
            "ukm:HTMLNotes": "html-notes",
            "ukm:TOC": "toc-html",
            "ukm:RDFVersion": "rdf",
            "ukm:AKNVersion": "akn",
        }

        resources_el = meta.find(xpath("ukm:Alternatives")) or meta

        for tag, fmt in format_map.items():
            for el in xpath_all(resources_el, tag):
                url = attr(el, "URI")
                lang = attr(el, "Language") or None
                if url:
                    record.formats.append(FormatLink(format=fmt, url=url, language=lang))

        # PDF — dedicated tag
        for el in xpath_all(meta, "ukm:PDF") + xpath_all(resources_el, "ukm:PDF"):
            url = attr(el, "URI")
            lang = attr(el, "Language") or None
            if url:
                record.formats.append(FormatLink(format="pdf", url=url, language=lang))
                if not record.pdf_url:
                    record.pdf_url = url

        # Deduplicate formats preserving order
        seen_urls: set[str] = set()
        deduped: list[FormatLink] = []
        for f in record.formats:
            if f.url not in seen_urls:
                deduped.append(f)
                seen_urls.add(f.url)
        record.formats = deduped

        # Derive PDF URL heuristically if still missing
        if not record.pdf_url and record.type and record.year and record.number:
            record.pdf_url = (
                f"http://www.legislation.gov.uk/{record.type}/{record.year}/"
                f"pdfs/{record.type}_{record.year:04d}{record.number:04d}_en.pdf"
            )

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    def _extract_versions(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        for ver_el in xpath_all(meta, "ukm:VersionHistory/ukm:Version") + xpath_all(meta, "ukm:Version"):
            version_date = attr(ver_el, "Date") or None
            document_uri = attr(ver_el, "DocumentURI") or None
            description = attr(ver_el, "Description") or None
            if version_date or document_uri:
                record.versions.append(VersionInfo(
                    version_date=version_date,
                    description=description,
                    document_uri=document_uri,
                ))

    # ------------------------------------------------------------------
    # Geographic extent
    # ------------------------------------------------------------------

    def _extract_extent(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        # Check the Extent element
        for container in [
            meta.find(xpath("ukm:PrimaryMetadata")),
            meta.find(xpath("ukm:SecondaryMetadata")),
            meta,
        ]:
            if container is None:
                continue
            extent_el = container.find(xpath("ukm:Extent"))
            if extent_el is not None:
                record.extent = attr(extent_el, "Value") or None
                record.extent_uri = attr(extent_el, "URI") or None
                break

    # ------------------------------------------------------------------
    # Table of contents
    # ------------------------------------------------------------------

    def _extract_contents(self, record: LegislationRecord) -> None:
        toc_root = self.root.find(xpath("leg:Contents"))
        if toc_root is None:
            return

        self._walk_contents(toc_root, record)

    def _walk_contents(self, node: Element, record: LegislationRecord) -> None:
        """Recursively walk the Contents tree and collect items."""
        LEVEL_TAGS = {
            "ContentsTitle": "title",
            "ContentsPart": "part",
            "ContentsChapter": "chapter",
            "ContentsSection": "section",
            "ContentsSchedules": "schedules",
            "ContentsSchedule": "schedule",
            "ContentsCrossheading": "crossheading",
            "ContentsItem": "item",
            "ContentsAppendix": "appendix",
            "ContentsEUPart": "eu-part",
            "ContentsEUTitle": "eu-title",
            "ContentsEUChapter": "eu-chapter",
            "ContentsEUSection": "eu-section",
        }

        for child in node:
            local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            level = LEVEL_TAGS.get(local)
            if level:
                number_el = child.find(xpath("leg:ContentsNumber"))
                title_el = child.find(xpath("leg:ContentsTitle")) or child.find(xpath("leg:Title"))

                number = "".join(number_el.itertext()).strip() if number_el is not None else None
                title = "".join(title_el.itertext()).strip() if title_el is not None else None
                item_id = attr(child, "IdURI") or attr(child, "id") or None
                doc_uri = attr(child, "DocumentURI") or None

                record.contents.append(ContentsItem(
                    number=number or None,
                    title=title or None,
                    id=item_id,
                    document_uri=doc_uri,
                    level=level,
                ))
                # recurse
                self._walk_contents(child, record)

    # ------------------------------------------------------------------
    # Effects / amendments
    # ------------------------------------------------------------------

    def _extract_effects(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        unapplied = 0
        applied = 0

        for effect_el in xpath_all(meta, "ukm:UnappliedEffects/ukm:UnappliedEffect") \
                        + xpath_all(meta, "ukm:Effects/ukm:Effect"):

            applied_flag: Optional[bool] = None
            applied_attr = attr(effect_el, "Applied")
            if applied_attr is not None:
                applied_flag = applied_attr.lower() == "true"

            # Required amendments
            req_amendments = [
                attr(req, "URI") or ""
                for req in xpath_all(effect_el, "ukm:RequiredAmendments/ukm:Amendment")
            ]

            effect = Effect(
                effect_id=attr(effect_el, "EffectId") or None,
                type=attr(effect_el, "Type") or None,
                affected_uri=attr(effect_el, "AffectedURI") or None,
                affecting_uri=attr(effect_el, "AffectingURI") or None,
                affected_provision=attr(effect_el, "AffectedProvision") or None,
                affecting_provision=attr(effect_el, "AffectingProvision") or None,
                in_force=attr(effect_el, "InForce") or None,
                in_force_notes=attr(effect_el, "InForceNotes") or None,
                note=attr(effect_el, "Note") or None,
                applied=applied_flag,
                required_amendments=[r for r in req_amendments if r],
            )
            record.effects.append(effect)

            if applied_flag is False:
                unapplied += 1
            elif applied_flag is True:
                applied += 1

        record.unapplied_effects_count = unapplied
        record.applied_effects_count = applied

    # ------------------------------------------------------------------
    # Powers conferred
    # ------------------------------------------------------------------

    def _extract_powers(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        for power_el in xpath_all(meta, "ukm:PrimaryMetadata/ukm:PowersConferred/ukm:Power"):
            record.powers_conferred.append(PowerConferred(
                uri=attr(power_el, "URI") or None,
                provision=attr(power_el, "Provision") or None,
                function=attr(power_el, "Function") or None,
                body=attr(power_el, "Body") or None,
            ))

    # ------------------------------------------------------------------
    # Commentary / footnotes
    # ------------------------------------------------------------------

    def _extract_commentary(self, record: LegislationRecord) -> None:
        for comm_el in xpath_all(self.root, "leg:Commentaries/leg:Commentary"):
            comm_id = attr(comm_el, "id") or attr(comm_el, "Ref") or None
            comm_type = attr(comm_el, "Type") or None
            text = "".join(comm_el.itertext()).strip() or None
            if comm_id or text:
                record.commentary.append({
                    "id": comm_id,
                    "type": comm_type,
                    "text": text,
                })

    # ------------------------------------------------------------------
    # Body structure counts
    # ------------------------------------------------------------------

    def _extract_structure_counts(self, record: LegislationRecord) -> None:
        # Count from the ToC (more reliable than body, handles pagination)
        if record.contents:
            record.section_count = sum(1 for c in record.contents if c.level == "section")
            record.schedule_count = sum(1 for c in record.contents if c.level == "schedule")
            record.part_count = sum(1 for c in record.contents if c.level == "part")
            record.chapter_count = sum(1 for c in record.contents if c.level == "chapter")
        else:
            # Fall back to counting body elements
            ns_leg = NS.get("leg", "")
            body = self.root.find(xpath("leg:Body"))
            if body is not None:
                record.section_count = len(xpath_all(body, "leg:P1group")) \
                                       + len(xpath_all(body, "leg:Section"))
                record.schedule_count = len(xpath_all(self.root, "leg:Schedules/leg:Schedule"))
                record.part_count = len(xpath_all(body, "leg:Part"))
                record.chapter_count = len(xpath_all(body, "leg:Chapter"))