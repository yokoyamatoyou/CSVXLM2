# -*- coding: utf-8 -*-
"""Helper to convert a CSV file to JSON using configured profiles."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import load_config, DEFAULT_CONFIG_PATH
from ..csv_parser import parse_csv_from_profile

logger = logging.getLogger(__name__)

# Allow tests or callers to override the configuration file used
DEFAULT_CONFIG_FILE = str(DEFAULT_CONFIG_PATH)


def _build_profile(config: dict, profile_name: str, csv_path: str) -> dict:
    """Return a profile dictionary for ``parse_csv_from_profile``."""
    profiles = config.get("csv_profiles", {})
    profile = profiles.get(profile_name)
    if profile is None:
        profile = profiles.get("default", {})
        logger.warning("Profile '%s' not found. Using 'default'.", profile_name)
    # Map config keys to parse_csv_from_profile format
    prof = profile.copy()
    if "header" in prof:
        prof["has_header"] = prof.pop("header")
    if "columns" in prof:
        prof["column_names"] = prof.pop("columns")
    prof["source"] = csv_path
    return prof


def convert_csv_to_json(csv_path: str, profile_name: str) -> list[dict]:
    """Parse ``csv_path`` using ``profile_name`` and write JSON next to the CSV."""
    config = load_config(DEFAULT_CONFIG_FILE)
    profile = _build_profile(config, profile_name, csv_path)
    records = parse_csv_from_profile(profile)

    out_path = Path(csv_path).with_suffix(".json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info("Wrote %d records to %s", len(records), out_path)
    return records


__all__ = ["convert_csv_to_json"]
