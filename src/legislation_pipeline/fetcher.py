from __future__ import annotations

import re
import time
import logging
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional
from xml.etree.ElementTree import Element
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# Legislation types recognised by legislation.gov.uk
LEGISLATION_TYPES = {
    "ukpga", "uksi", "ukla", "ukpp", "ukmo", "ukdsi",
    "asp",   "asc",  "anaw", "mwa",  "ukcm", "nia",
    "nisi",  "nisr", "nisro","eur",  "eudn", "eudr",
    "apni",  "aosp", "ssi",  "wsi",
}

_URL_PATTERN = re.compile(
    r"^/(?:(?P<id>id)/)?"
    r"(?P<type>[a-z]+)/(?P<year>[0-9A-Za-z-]+)/(?P<number>[0-9]+)"
    r"(?P<rest>/.*)?$",
    re.IGNORECASE,
)


class FetchError(Exception):
    """Raised when the XML document cannot be fetched or parsed."""


def normalise_url(url: str, resources_only: bool = False) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "legislation.gov.uk",
        "www.legislation.gov.uk",
    }:
        raise FetchError(
            f"URL does not look like a legislation.gov.uk document URL: {url!r}\n"
            f"Expected format: https://www.legislation.gov.uk/<type>/<year>/<number>"
        )

    path = parsed.path.rstrip("/")

    # Strip any existing format suffix.
    path = re.sub(r"/(?:resources/)?data\.[A-Za-z0-9]+$", "", path)

    m = _URL_PATTERN.match(path)
    if not m:
        raise FetchError(
            f"URL does not look like a legislation.gov.uk document URL: {url!r}\n"
            f"Expected format: https://www.legislation.gov.uk/<type>/<year>/<number>"
        )

    leg_type = m.group("type").lower()
    if leg_type not in LEGISLATION_TYPES:
        logger.warning("Unrecognised legislation type %r — proceeding anyway.", leg_type)

    if m.group("id"):
        path = path.removeprefix("/id")

    path = path.rstrip("/")
    if resources_only:
        path = f"{path}/resources/data.xml"
    else:
        path = f"{path}/data.xml"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def fetch_xml(
    url: str,
    max_retries: int = 3,
    backoff: float = 1.5,
    timeout: int = 30,
    user_agent: str = "uk-legislation-pipeline/1.0 (github.com/example)",
) -> Element:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/xml, text/xml;q=0.9, */*;q=0.8",
    }

    last_error: Optional[Exception] = None
    delay = backoff

    for attempt in range(1, max_retries + 1):
        logger.debug("Fetching %s (attempt %d/%d)", url, attempt, max_retries)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read()

            # Validate content type loosely (some servers return text/html for errors)
            if "html" in content_type and b"<html" in raw[:512]:
                raise FetchError(
                    f"Server returned HTML instead of XML — "
                    f"the URL may not exist: {url}"
                )

            try:
                root = ET.fromstring(raw)
            except ET.ParseError as exc:
                raise FetchError(f"XML parse error for {url}: {exc}") from exc

            logger.info("Successfully fetched %s (%d bytes)", url, len(raw))
            return root

        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                logger.warning(
                    "HTTP %d — retrying in %.1fs (attempt %d/%d)",
                    exc.code, delay, attempt, max_retries,
                )
                time.sleep(delay)
                delay *= 2
                last_error = exc
                continue
            raise FetchError(
                f"HTTP {exc.code} fetching {url}: {exc.reason}"
            ) from exc

        except urllib.error.URLError as exc:
            if attempt < max_retries:
                logger.warning("URL error — retrying in %.1fs: %s", delay, exc)
                time.sleep(delay)
                delay *= 2
                last_error = exc
                continue
            raise FetchError(f"Network error fetching {url}: {exc}") from exc

        except TimeoutError as exc:
            raise FetchError(f"Request timed out after {timeout}s: {url}") from exc

    raise FetchError(f"All {max_retries} attempts failed for {url}") from last_error


def fetch_versions(base_url: str, **kwargs) -> list[dict]:
    try:
        normalised = normalise_url(base_url)
    except FetchError:
        return []
    parsed = urlsplit(normalised)
    m = _URL_PATTERN.match(parsed.path.removesuffix("/data.xml"))
    if not m:
        return []

    leg_type = m.group("type")
    year = m.group("year")
    number = m.group("number")
    feed_url = (
        f"https://www.legislation.gov.uk/{leg_type}/{year}/{number}/data.feed"
    )

    try:
        root = fetch_xml(feed_url, **kwargs)
    except FetchError as exc:
        logger.warning("Could not fetch version feed: %s", exc)
        return []

    # Atom namespace
    atom_ns = "{http://www.w3.org/2005/Atom}"
    versions: list[dict] = []
    for entry in root.findall(f"{atom_ns}entry"):
        title_el = entry.find(f"{atom_ns}title")
        updated_el = entry.find(f"{atom_ns}updated")
        link_el = entry.find(f"{atom_ns}link[@rel='self']")
        versions.append({
            "title": title_el.text.strip() if title_el is not None and title_el.text else None,
            "date": updated_el.text.strip() if updated_el is not None and updated_el.text else None,
            "uri": link_el.get("href") if link_el is not None else None,
        })
    return versions
