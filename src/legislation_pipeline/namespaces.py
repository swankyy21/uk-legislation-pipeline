from __future__ import annotations

from typing import Optional
from xml.etree.ElementTree import Element

# ---------------------------------------------------------------------------
# Namespace registry
# ---------------------------------------------------------------------------

NS: dict[str, str] = {
    # Primary legislation namespaces
    "leg":  "http://www.legislation.gov.uk/namespaces/legislation",
    "ukm":  "http://www.legislation.gov.uk/namespaces/metadata",
    # Dublin Core (both flavours seen in the wild)
    "dc":   "http://purl.org/dc/elements/1.1/",
    "dct":  "http://purl.org/dc/terms/",
    # Standard XML namespaces
    "xsi":  "http://www.w3.org/2001/XMLSchema-instance",
    "xhtml":"http://www.w3.org/1999/xhtml",
    # Atom (used in feeds / alternatives lists)
    "atom": "http://www.w3.org/2005/Atom",
}


def xpath(path: str) -> str:
    parts = path.split("/")
    resolved = []
    for part in parts:
        if ":" in part:
            prefix, local = part.split(":", 1)
            ns = NS.get(prefix)
            if ns:
                resolved.append(f"{{{ns}}}{local}")
            else:
                resolved.append(part)
        else:
            resolved.append(part)
    return "/".join(resolved)


def xpath_all(element: Element, path: str) -> list[Element]:
    return element.findall(xpath(path))


def attr(element: Element, name: str, default: Optional[str] = None) -> Optional[str]:
    return element.get(name, default)


def text_or_none(parent: Element, prefixed_tag: str) -> Optional[str]:
    el = parent.find(xpath(prefixed_tag))
    if el is not None and el.text:
        return el.text.strip() or None
    return None