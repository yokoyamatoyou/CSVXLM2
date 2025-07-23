"""Utility helpers for the CSVXLM project."""

from __future__ import annotations

import logging
from os import PathLike
from typing import Optional, Union

from lxml import etree

from .csv_to_json import convert_csv_to_json

logger = logging.getLogger(__name__)


def parse_xml(path: Union[str, PathLike[str]]) -> Optional[etree._ElementTree]:
    """Return an ``ElementTree`` for ``path`` or ``None`` on error.

    Parameters
    ----------
    path:
        Path to an XML file. Accepts :class:`str` or :class:`os.PathLike`.
    """
    try:
        return etree.parse(str(path))
    except etree.XMLSyntaxError as exc:
        logger.error("XMLSyntaxError parsing %s: %s", path, exc)
    except OSError as exc:
        logger.error("Error reading XML %s: %s", path, exc)
    except Exception as exc:  # pragma: no cover - unexpected errors
        logger.error("Unexpected error parsing %s: %s", path, exc)
    return None


__all__ = ["parse_xml", "convert_csv_to_json"]
