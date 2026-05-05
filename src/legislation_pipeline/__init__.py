"""UK legislation CLML extraction pipeline."""

from .extractor import CLMLExtractor, LegislationRecord
from .fetcher import FetchError, fetch_xml, normalise_url

__all__ = [
    "CLMLExtractor",
    "FetchError",
    "LegislationRecord",
    "fetch_xml",
    "normalise_url",
]
