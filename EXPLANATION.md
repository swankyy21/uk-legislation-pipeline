# Brief Explanation

## Approach

This project implements a deterministic Python pipeline for extracting structured data from legislation.gov.uk CLML XML.

The pipeline is split into small modules:

- `fetcher.py` normalises legislation.gov.uk URLs and fetches XML endpoints such as `/data.xml`.
- `extractor.py` parses CLML into dataclasses and extracts only fields explicitly present in the XML.
- `serialisers.py` exports the extracted record as JSON, text, CSV, or HTML.
- `cli.py` provides a command-line interface for running the pipeline on any legislation URL.

The extractor reads CLML metadata, Dublin Core metadata, Atom links, versions, formats, identifiers, dates, structural elements, commentary, effects, and associated documents. It avoids interpretation or enrichment: missing XML fields remain `null` or empty in the structured output.

## How To Run

Install the project:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Run JSON extraction:

```bash
uk-legislation-extract https://www.legislation.gov.uk/ukpga/2024/15 --format json --output output/media_act_2024.json
```

Run HTML summary extraction:

```bash
uk-legislation-extract https://www.legislation.gov.uk/ukpga/2024/15 --format html --output output/media_act_2024.html
```

Run directly without installing:

```bash
PYTHONPATH=src python3 -m legislation_pipeline https://www.legislation.gov.uk/ukpga/2024/15 --format json
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Example Output

Example outputs for the Media Act 2024 are included in `output/`:

- `output/media_act_2024.json`
- `output/media_act_2024.html`
- `output/media_act_2024.txt`
- `output/media_act_2024.csv`

## Trade-Offs

- JSON is the canonical output because it preserves nested structures such as versions, links, effects, commentary, and contents.
- CSV is intentionally a flat summary export, so it does not include every nested field.
- HTML is a readable summary view, similar to the provided example output, but it is generated from extracted XML data rather than hardcoded values.
- The extractor uses pragmatic CLML traversal and local-name matching for robustness across legislation types, instead of requiring every document to have identical metadata layout.
- No third-party runtime dependencies are used, keeping the project simple to run and review.

## What I Would Improve With More Time

- Add more fixtures across UKPGA, UKSI, Welsh bilingual legislation, EU-origin retained legislation, and section-level URLs.
- Validate incoming documents against the published CLML schema.
- Add richer version comparison helpers.
- Add more detailed extraction for commencement and amendment effect sub-elements.
- Add streaming or incremental parsing for very large legislation documents.
