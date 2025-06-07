import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

DEFAULT_XSD_DIRS = [
    Path('5521111111_00280081_202405271_1/5521111111_00280081_202405271_1/XSD'),
    Path('XSD')
]


def resolve_xsd_path(xsd_name: str, extra_dirs: Iterable[str] | None = None) -> str:
    """Return the path to the requested XSD file.

    The search prefers the deeper example directory before falling back to the
    top-level XSD directory. Additional directories can be supplied via
    ``extra_dirs``.
    """
    search_dirs = []
    if extra_dirs:
        search_dirs.extend(Path(p) for p in extra_dirs)
    search_dirs.extend(DEFAULT_XSD_DIRS)

    for base in search_dirs:
        candidate = base / xsd_name
        if candidate.exists():
            resolved = str(candidate.resolve())
            logger.debug("Resolved XSD %s to %s", xsd_name, resolved)
            return resolved
    logger.error("XSD file %s not found in search paths: %s", xsd_name, search_dirs)
    raise FileNotFoundError(f"XSD file {xsd_name} not found")
