"""Utility helpers for the CSVXLM project."""

from __future__ import annotations

import logging
from typing import Optional

from lxml import etree

logger = logging.getLogger(__name__)


def parse_xml(path: str) -> Optional[etree._ElementTree]:
    """Return an ``ElementTree`` for ``path`` or ``None`` on error."""
    try:
        return etree.parse(path)
    except etree.XMLSyntaxError as exc:
        logger.error("XMLSyntaxError parsing %s: %s", path, exc)
    except OSError as exc:
        logger.error("Error reading XML %s: %s", path, exc)
    except Exception as exc:  # pragma: no cover - unexpected errors
        logger.error("Unexpected error parsing %s: %s", path, exc)
    return None


__all__ = ["parse_xml"]
