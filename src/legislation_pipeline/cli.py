from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .extractor import CLMLExtractor
from .fetcher import FetchError, fetch_xml, normalise_url
from .serialisers import to_csv, to_html, to_json, to_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uk-legislation-extract",
        description="Extract structured data from legislation.gov.uk CLML XML.",
    )
    parser.add_argument(
        "url",
        help="Legislation URL, for example https://www.legislation.gov.uk/ukpga/2024/15",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text", "csv", "html"),
        default="json",
        help="Output format. Defaults to json.",
    )
    parser.add_argument(
        "--resources-only",
        action="store_true",
        help="Fetch /resources/data.xml metadata instead of the full document XML.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Write output to this file instead of stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        xml_url = normalise_url(args.url, resources_only=args.resources_only)
        root = fetch_xml(xml_url)
        record = CLMLExtractor(root, source_url=xml_url).extract()
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        output = to_json(record)
    elif args.format == "csv":
        output = to_csv([record])
    elif args.format == "html":
        output = to_html(record)
    else:
        output = to_text(record)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
