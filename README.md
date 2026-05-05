# UK Legislation Data Pipeline

Deterministic Python pipeline for extracting structured data from legislation.gov.uk CLML XML.

The extractor performs pure XML extraction: it reads fields that are present in the CLML document, Dublin Core metadata, UK metadata namespace, and Atom links. It does not use AI inference or enrich missing values from outside sources.

## What It Extracts

- Identity: title, long title, legislation type slug, CLML main type, category, year, number, status, ISBN.
- Identifiers: identifier URI, document URI, this-document URI, Dublin Core identifier.
- Dates: enactment, made, laid, coming into force, and other dated UK metadata events when present.
- Formats and links: XML, AKN, HTML, RDF, CSV, PDF, original/static PDFs, table of contents, navigation links, notes, related resources.
- Versions: `hasVersion`, `replaces`, and `isReplacedBy` links exposed in Atom metadata.
- Structure: parts, chapters, crossheadings, sections, schedules, schedule paragraphs, counts, provision totals, CLML statistics.
- Effects: unapplied/applied effect records, source attributes, affected/affecting URIs, provisions, notes, comments, modified timestamps, in-force flags.
- Other metadata: extent/restriction attributes, associated documents, commentary notes, powers conferred where present.

## Install

No third-party runtime dependencies are required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

You can also run directly from the source tree:

```bash
PYTHONPATH=src python3 -m legislation_pipeline --help
```

## Usage

Extract JSON from any legislation.gov.uk document URL:

```bash
uk-legislation-extract https://www.legislation.gov.uk/ukpga/2024/15 --output output/media_act_2024.json
```

Other formats:

```bash
uk-legislation-extract https://www.legislation.gov.uk/ukpga/2024/15 --format text
uk-legislation-extract https://www.legislation.gov.uk/ukpga/2024/15 --format html --output output/media_act_2024.html
uk-legislation-extract https://www.legislation.gov.uk/uksi/2024/858/made --format csv
uk-legislation-extract https://www.legislation.gov.uk/id/ukpga/2024/15 --resources-only
```

The CLI normalises document, identifier, version, section, and existing `data.xml` URLs by appending or preserving the correct XML endpoint.

## Example Output

Example files generated from the Media Act 2024 live XML endpoint are included:

- `output/media_act_2024.json`
- `output/media_act_2024.txt`
- `output/media_act_2024.html`

The JSON begins with fields such as:

```json
{
  "title": "Media Act 2024",
  "type": "ukpga",
  "year": 2024,
  "number": 15,
  "status": "revised",
  "uri": "http://www.legislation.gov.uk/id/ukpga/2024/15",
  "pdf_url": "http://www.legislation.gov.uk/ukpga/2024/15/pdfs/ukpga_20240015_en.pdf"
}
```

## Tests

The tests use `unittest` and a compact CLML fixture that mirrors the real Media Act metadata patterns.

```bash
python3 -m unittest discover -s tests
python3 -m compileall src tests
```

