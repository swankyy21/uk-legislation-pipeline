from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from xml.etree.ElementTree import Element
from urllib.parse import urlparse

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
    relation: Optional[str] = None


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
    uri: Optional[str]
    type: Optional[str]
    affected_uri: Optional[str]
    affecting_uri: Optional[str]
    affected_provision: Optional[str]
    affecting_provision: Optional[str]
    in_force: Optional[str]
    in_force_notes: Optional[str]
    note: Optional[str]
    comments: Optional[str]
    modified: Optional[str]
    applied: Optional[bool]
    required_amendments: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)


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
    document_category: Optional[str] = None
    document_main_type: Optional[str] = None
    year: Optional[int] = None
    number: Optional[int] = None
    status: Optional[str] = None         # e.g. "revised", "enacted"
    isbn: Optional[str] = None

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
    dc_contributor: Optional[str] = None

    # --- Formats & Links ---
    formats: list[FormatLink] = field(default_factory=list)
    pdf_url: Optional[str] = None        # Primary PDF (convenience field)
    links: list[dict] = field(default_factory=list)
    associated_documents: list[dict] = field(default_factory=list)

    # --- Versions ---
    versions: list[VersionInfo] = field(default_factory=list)

    # --- Geographic Extent ---
    extent: Optional[str] = None
    extent_uri: Optional[str] = None
    restrict_extent: Optional[str] = None
    restrict_start_date: Optional[str] = None
    restrict_end_date: Optional[str] = None

    # --- Structure ---
    contents: list[ContentsItem] = field(default_factory=list)
    schedule_count: int = 0
    section_count: int = 0
    paragraph_count: int = 0
    part_count: int = 0
    chapter_count: int = 0
    number_of_provisions: Optional[int] = None
    statistics: dict[str, int] = field(default_factory=dict)

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
        record.uri = attr(self.root, "IdURI") or None
        record.document_uri = attr(self.root, "DocumentURI") or None
        record.schema_version = attr(self.root, "SchemaVersion") or None
        record.restrict_extent = attr(self.root, "RestrictExtent") or None
        record.restrict_start_date = attr(self.root, "RestrictStartDate") or None
        record.restrict_end_date = attr(self.root, "RestrictEndDate") or None
        record.number_of_provisions = _int_or_none(attr(self.root, "NumberOfProvisions"))

        if meta is None:
            return

        primary = _first_found(meta, [
            "ukm:PrimaryMetadata",
            "ukm:SecondaryMetadata",
            "ukm:EUMetadata",
        ])
        if primary is None:
            primary = meta

        category_el = primary.find(xpath("ukm:DocumentClassification/ukm:DocumentCategory"))
        if category_el is not None:
            record.document_category = attr(category_el, "Value") or None

        doc_type = primary.find(xpath("ukm:DocumentClassification/ukm:DocumentMainType"))
        if doc_type is not None:
            record.document_main_type = attr(doc_type, "Value") or None

        # Year
        year_el = primary.find(xpath("ukm:Year"))
        if year_el is not None:
            record.year = _int_or_none(attr(year_el, "Value"))

        # Number
        number_el = primary.find(xpath("ukm:Number"))
        if number_el is not None:
            record.number = _int_or_none(attr(number_el, "Value"))

        # Status (enacted / revised)
        status_el = primary.find(xpath("ukm:DocumentClassification/ukm:DocumentStatus"))
        if status_el is None:
            status_el = primary.find(xpath("ukm:DocumentStatus"))
        if status_el is not None:
            record.status = attr(status_el, "Value") or None

        isbn_el = primary.find(xpath("ukm:ISBN"))
        if isbn_el is not None:
            record.isbn = attr(isbn_el, "Value") or None

        # Title  — prefer dc:title, will be set in _extract_metadata
        # but also try the TitleBlock in the body
        title_el = self.root.find(xpath("leg:Primary/leg:PrimaryPrelims/leg:Title"))
        if title_el is None:
            title_el = self.root.find(xpath("leg:Secondary/leg:SecondaryPrelims/leg:Title"))
        if title_el is None:
            title_el = self.root.find(xpath("leg:Body/leg:TitleBlock/leg:Title"))
        if title_el is not None:
            record.title = _text(title_el)

        # Long title / preamble
        long_title_el = _first_found(self.root, [
            "leg:Primary/leg:PrimaryPrelims/leg:LongTitle",
            "leg:Secondary/leg:SecondaryPrelims/leg:LongTitle",
        ])
        if long_title_el is not None:
            record.long_title = _text(long_title_el)

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
        record.dc_contributor = text_or_none(meta, "dc:contributor")

        # Multiple subjects
        record.dc_subject = [
            el.text.strip()
            for el in xpath_all(meta, "dc:subject")
            if el.text and el.text.strip()
        ]

        # If we still have no title, use dc_title
        if not record.title and record.dc_title:
            record.title = record.dc_title

        if not record.document_uri and record.dc_identifier:
            record.document_uri = record.dc_identifier
        if not record.type:
            record.type = _type_from_uri(record.uri) or _type_from_uri(record.document_uri) or _type_from_uri(record.dc_identifier)

        # URIs
        id_el = _first_found(meta, [
            "ukm:PrimaryMetadata/ukm:Identifier",
            "ukm:SecondaryMetadata/ukm:Identifier",
            "ukm:Identifier",
        ])
        if id_el is not None:
            record.uri = record.uri or attr(id_el, "URI") or None

        # DocumentURI from the Metadata element itself or its children
        record.document_uri = record.document_uri or attr(meta, "DocumentURI") or None
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

        for tag, fmt in format_map.items():
            for el in _iter_by_local(meta, tag.split(":", 1)[1]):
                url = attr(el, "URI")
                lang = attr(el, "Language") or None
                if url:
                    record.formats.append(FormatLink(format=fmt, url=url, language=lang))

        # PDF — dedicated tag
        for el in _iter_by_local(meta, "PDF"):
            url = attr(el, "URI")
            lang = attr(el, "Language") or None
            if url:
                record.formats.append(FormatLink(format="pdf", url=url, language=lang))
                if not record.pdf_url:
                    record.pdf_url = url

        for alt_el in _iter_by_local(meta, "Alternative"):
            url = attr(alt_el, "URI")
            if not url:
                continue
            title = attr(alt_el, "Title")
            size = _int_or_none(attr(alt_el, "Size"))
            item = {
                "uri": url,
                "title": title,
                "date": attr(alt_el, "Date"),
                "size": size,
                "print": attr(alt_el, "Print"),
            }
            record.associated_documents.append({k: v for k, v in item.items() if v is not None})
            fmt = _format_from_url(url, title)
            record.formats.append(FormatLink(format=fmt, url=url, language=attr(alt_el, "Language")))
            if fmt == "pdf" and not record.pdf_url and attr(alt_el, "Print") == "true":
                record.pdf_url = url

        for link_el in xpath_all(meta, "atom:link"):
            href = attr(link_el, "href")
            if not href:
                continue
            link = {
                "rel": attr(link_el, "rel"),
                "href": href,
                "type": attr(link_el, "type"),
                "title": attr(link_el, "title"),
                "hreflang": attr(link_el, "hreflang"),
            }
            record.links.append({k: v for k, v in link.items() if v is not None})
            if attr(link_el, "rel") == "alternate" or attr(link_el, "type"):
                fmt = _format_from_link(link_el)
                record.formats.append(FormatLink(
                    format=fmt,
                    url=href,
                    language=attr(link_el, "hreflang"),
                ))
                if fmt == "pdf" and not record.pdf_url:
                    record.pdf_url = href

        # Deduplicate formats preserving order
        seen_urls: set[tuple[str, str, Optional[str]]] = set()
        deduped: list[FormatLink] = []
        for f in record.formats:
            key = (f.format, f.url, f.language)
            if key not in seen_urls:
                deduped.append(f)
                seen_urls.add(key)
        record.formats = deduped
        record.pdf_url = _select_primary_pdf(record) or record.pdf_url

        # Derive PDF URL heuristically if still missing
        if not record.pdf_url and record.document_uri:
            record.pdf_url = f"{record.document_uri.rstrip('/')}/data.pdf"
        elif not record.pdf_url and record.type and record.year and record.number:
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

        version_rels = {
            "http://purl.org/dc/terms/hasVersion",
            "http://purl.org/dc/terms/replaces",
            "http://purl.org/dc/terms/isReplacedBy",
        }
        seen: set[tuple[Optional[str], Optional[str], Optional[str]]] = {
            (v.relation, v.document_uri, v.description) for v in record.versions
        }
        for link_el in xpath_all(meta, "atom:link"):
            rel = attr(link_el, "rel")
            if rel not in version_rels:
                continue
            href = attr(link_el, "href")
            title = attr(link_el, "title")
            version_date = title if title and re.fullmatch(r"\d{4}-\d{2}-\d{2}", title) else None
            item = VersionInfo(
                version_date=version_date,
                description=title,
                document_uri=href,
                relation=rel.rsplit("/", 1)[-1],
            )
            key = (item.relation, item.document_uri, item.description)
            if key not in seen:
                record.versions.append(item)
                seen.add(key)

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
                record.extent = attr(extent_el, "Value") or attr(extent_el, "Extent") or None
                record.extent_uri = attr(extent_el, "URI") or None
                break

    # ------------------------------------------------------------------
    # Table of contents
    # ------------------------------------------------------------------

    def _extract_contents(self, record: LegislationRecord) -> None:
        toc_root = self.root.find(xpath("leg:Contents"))
        if toc_root is not None:
            self._walk_contents(toc_root, record)

        if not record.contents:
            self._extract_body_structure(record)

    def _walk_contents(self, node: Element, record: LegislationRecord) -> None:
        """Recursively walk the Contents tree and collect items."""
        LEVEL_TAGS = {
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
                title_el = child.find(xpath("leg:ContentsTitle"))
                if title_el is None:
                    title_el = child.find(xpath("leg:Title"))

                number = _text(number_el) if number_el is not None else None
                title = _text(title_el) if title_el is not None else None
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

    def _extract_body_structure(self, record: LegislationRecord) -> None:
        """Collect major divisions from the legislation body when no ToC is present."""
        major_tags = {
            "Part": "part",
            "Chapter": "chapter",
            "Pblock": "crossheading",
            "Schedule": "schedule",
        }
        seen_ids: set[str] = set()
        parents = _parent_map(self.root)
        for el in self.root.iter():
            local = _local_name(el)
            level = major_tags.get(local)
            if local == "P1":
                level = "paragraph" if _has_ancestor(el, parents, "Schedule") else "section"
            if not level:
                continue
            doc_uri = attr(el, "DocumentURI") or None
            id_uri = attr(el, "IdURI") or None
            item_id = id_uri or doc_uri
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            number = _child_text(el, "Number")
            if number is None and local == "P1":
                number = _child_text(el, "Pnumber")
            title = _child_text(el, "Title")
            if title is None and local == "P1":
                parent = parents.get(el)
                if parent is not None and _local_name(parent) == "P1group":
                    title = _child_text(parent, "Title")

            record.contents.append(ContentsItem(
                number=number,
                title=title,
                id=id_uri or attr(el, "id") or None,
                document_uri=doc_uri,
                level=level,
            ))

    # ------------------------------------------------------------------
    # Effects / amendments
    # ------------------------------------------------------------------

    def _extract_effects(self, record: LegislationRecord) -> None:
        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is None:
            return

        unapplied = 0
        applied = 0

        effect_elements = list(_iter_by_local(meta, "UnappliedEffect")) + list(_iter_by_local(meta, "Effect"))
        seen_effects: set[int] = set()

        for effect_el in effect_elements:
            if id(effect_el) in seen_effects:
                continue
            seen_effects.add(id(effect_el))

            applied_flag: Optional[bool] = None
            applied_attr = attr(effect_el, "Applied")
            if applied_attr is None:
                in_force_el = next(_iter_by_local(effect_el, "InForce"), None)
                if in_force_el is not None:
                    applied_attr = attr(in_force_el, "Applied")
            if applied_attr is not None:
                applied_flag = applied_attr.lower() == "true"

            # Required amendments
            req_amendments = [
                attr(req, "URI") or ""
                for req in _iter_by_local(effect_el, "Amendment")
            ]

            effect = Effect(
                effect_id=attr(effect_el, "EffectId") or None,
                uri=attr(effect_el, "URI") or None,
                type=attr(effect_el, "Type") or None,
                affected_uri=attr(effect_el, "AffectedURI") or None,
                affecting_uri=attr(effect_el, "AffectingURI") or None,
                affected_provision=attr(effect_el, "AffectedProvision") or attr(effect_el, "AffectedProvisions") or None,
                affecting_provision=attr(effect_el, "AffectingProvision") or attr(effect_el, "AffectingProvisions") or None,
                in_force=attr(effect_el, "InForce") or _in_force_summary(effect_el),
                in_force_notes=attr(effect_el, "InForceNotes") or None,
                note=attr(effect_el, "Note") or attr(effect_el, "Notes") or None,
                comments=attr(effect_el, "Comments") or None,
                modified=attr(effect_el, "Modified") or None,
                applied=applied_flag,
                required_amendments=[r for r in req_amendments if r],
                attributes=dict(effect_el.attrib),
            )
            record.effects.append(effect)

            if _local_name(effect_el) == "UnappliedEffect" or applied_flag is False:
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

        for power_el in _iter_by_local(meta, "Power"):
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
            record.paragraph_count = sum(1 for c in record.contents if c.level == "paragraph")
            record.part_count = sum(1 for c in record.contents if c.level == "part")
            record.chapter_count = sum(1 for c in record.contents if c.level == "chapter")
        else:
            # Fall back to counting body elements
            parents = _parent_map(self.root)
            record.section_count = sum(
                1 for el in self.root.iter()
                if _local_name(el) in {"P1", "Section"} and not _has_ancestor(el, parents, "Schedule")
            )
            record.paragraph_count = sum(
                1 for el in self.root.iter()
                if _local_name(el) == "P1" and _has_ancestor(el, parents, "Schedule")
            )
            record.schedule_count = sum(1 for el in self.root.iter() if _local_name(el) == "Schedule")
            record.part_count = sum(1 for el in self.root.iter() if _local_name(el) == "Part")
            record.chapter_count = sum(1 for el in self.root.iter() if _local_name(el) == "Chapter")

        meta = self.root.find(xpath("ukm:Metadata"))
        if meta is not None:
            for stat_el in _iter_by_local(meta, "Statistics"):
                for child in stat_el:
                    value = _int_or_none(attr(child, "Value"))
                    if value is not None:
                        record.statistics[_local_name(child)] = value


def _first_found(parent: Element, paths: list[str]) -> Optional[Element]:
    for path in paths:
        el = parent.find(xpath(path))
        if el is not None:
            return el
    return None


def _local_name(element: Element) -> str:
    return element.tag.rsplit("}", 1)[-1] if "}" in element.tag else element.tag


def _iter_by_local(parent: Element, local_name: str):
    for el in parent.iter():
        if _local_name(el) == local_name:
            yield el


def _text(element: Element) -> Optional[str]:
    text = " ".join("".join(element.itertext()).split())
    return text or None


def _child_text(parent: Element, local_name: str) -> Optional[str]:
    for child in parent:
        if _local_name(child) == local_name:
            return _text(child)
    return None


def _int_or_none(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _type_from_uri(uri: Optional[str]) -> Optional[str]:
    if not uri:
        return None
    path_parts = [part for part in urlparse(uri).path.split("/") if part]
    if path_parts and path_parts[0] == "id":
        path_parts = path_parts[1:]
    if path_parts:
        return path_parts[0].lower()
    return None


def _format_from_url(url: str, title: Optional[str] = None) -> str:
    lowered = url.lower()
    if lowered.endswith(".xml"):
        return "xml"
    if lowered.endswith(".akn"):
        return "akn"
    if lowered.endswith((".xht", ".htm", ".html")):
        return "html"
    if lowered.endswith(".rdf"):
        return "rdf"
    if lowered.endswith(".csv"):
        return "csv"
    if lowered.endswith(".pdf") or (title and "pdf" in title.lower()):
        return "pdf"
    return "other"


def _format_from_link(link_el: Element) -> str:
    mime = (attr(link_el, "type") or "").lower()
    title = attr(link_el, "title")
    href = attr(link_el, "href") or ""
    if "pdf" in mime:
        return "pdf"
    if "rdf" in mime:
        return "rdf"
    if "csv" in mime:
        return "csv"
    if "html" in mime:
        return "html"
    if "akn" in mime:
        return "akn"
    if "xml" in mime:
        return "xml"
    return _format_from_url(href, title)


def _in_force_summary(effect_el: Element) -> Optional[str]:
    values: list[str] = []
    for in_force_el in _iter_by_local(effect_el, "InForce"):
        parts = []
        for key in ("Date", "Applied", "Prospective", "Qualification"):
            value = attr(in_force_el, key)
            if value:
                parts.append(f"{key}={value}")
        if parts:
            values.append("; ".join(parts))
    return " | ".join(values) or None


def _parent_map(root: Element) -> dict[Element, Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _has_ancestor(element: Element, parents: dict[Element, Element], local_name: str) -> bool:
    parent = parents.get(element)
    while parent is not None:
        if _local_name(parent) == local_name:
            return True
        parent = parents.get(parent)
    return False


def _select_primary_pdf(record: LegislationRecord) -> Optional[str]:
    for item in record.associated_documents:
        if item.get("print") == "true" and isinstance(item.get("uri"), str):
            return item["uri"]
    for link in record.links:
        title = str(link.get("title", "")).lower()
        href = link.get("href")
        if "original pdf" in title and isinstance(href, str):
            return href
    for fmt in record.formats:
        if fmt.format == "pdf" and "/pdfs/" in fmt.url:
            return fmt.url
    for fmt in record.formats:
        if fmt.format == "pdf":
            return fmt.url
    return None
