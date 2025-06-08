# -*- coding: utf-8 -*-
"""
CSV parsing utilities.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Any, Optional
import csv
import io

logger = logging.getLogger(__name__)

class CSVParsingError(ValueError):
    """Custom error for CSV parsing issues."""
    pass


def parse_csv(
    source: str,
    delimiter: str = ',',
    encoding: str = 'utf-8',
    required_columns: Optional[List[str]] = None,
    skip_comments: bool = True,
    header_override: Optional[List[str]] = None,
    *,
    quotechar: str = '"',
    escapechar: Optional[str] = None,
    doublequote: bool = True,
) -> List[Dict[str, str]]:
    """Parses a CSV from a file path or string content."""
    file_obj: io.TextIOBase
    is_likely_path = not ("\n" in source or "\r" in source)
    if is_likely_path:
        if not os.path.exists(source):
            logger.error("File not found: %s", source)
            raise FileNotFoundError(f"No such file or directory: '{source}'")
        logger.debug("Source '%s' is an existing file path. Reading content.", source)
        try:
            file_obj = open(source, 'r', encoding=encoding, newline='')
        except UnicodeDecodeError as e:
            logger.error("Encoding error for file %s with encoding %s: %s", source, encoding, e)
            raise
        except Exception as e:
            logger.error("Error reading file %s: %s", source, e)
            raise CSVParsingError(f"Error reading file {source}: {e}") from e
    else:
        if os.path.exists(source):
            logger.debug("Source '%s' with newlines exists as a file. Reading content.", source)
            try:
                file_obj = open(source, 'r', encoding=encoding, newline='')
            except UnicodeDecodeError as e:
                logger.error("Encoding error for file %s with encoding %s: %s", source, encoding, e)
                raise
            except Exception as e:
                logger.error("Error reading file %s: %s", source, e)
                raise CSVParsingError(f"Error reading file {source}: {e}") from e
        else:
            logger.debug("Source is treated as direct string content.")
            file_obj = io.StringIO(source)

    reader = csv.reader(
        file_obj,
        delimiter=delimiter,
        quotechar=quotechar,
        escapechar=escapechar,
        doublequote=doublequote,
    )

    records: List[Dict[str, str]] = []
    header_cols: Optional[List[str]] = None
    line_num = 0

    if header_override is not None:
        header_cols = [col.strip() for col in header_override]
        if required_columns:
            missing = [c for c in required_columns if c not in header_cols]
            if missing:
                msg = f"CSV header is missing required column(s): {', '.join(missing)}"
                logger.error(msg)
                raise CSVParsingError(msg)
        logger.info("Using provided header_override: %s", header_override)

    for row in reader:
        line_num += 1
        if not row:
            continue
        if skip_comments and row[0].startswith('#'):
            logger.debug("Skipping comment line: %s", row)
            continue
        if header_cols is None:
            header_cols = [cell.strip() for cell in row]
            logger.info("Header found on line %d: %s", line_num, header_cols)
            if required_columns:
                missing = [c for c in required_columns if c not in header_cols]
                if missing:
                    msg = f"CSV header is missing required column(s): {', '.join(missing)}"
                    logger.error(msg)
                    raise CSVParsingError(msg)
            continue
        if len(row) != len(header_cols):
            logger.warning(
                "Skipping line %d due to column count mismatch (expected %d, got %d): %s",
                line_num,
                len(header_cols),
                len(row),
                row,
            )
            continue
        cells = [cell.strip() for cell in row]
        records.append(dict(zip(header_cols, cells)))

    if header_cols is None:
        logger.warning("No header row found or provided in CSV data.")
        return []

    logger.info("Loaded %d records from CSV.", len(records))
    if records:
        logger.debug("First record: %s", records[0])

    return records
def parse_csv_from_profile(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Parses a CSV file based on a provided profile dictionary.

    Args:
        profile: A dictionary containing parsing parameters. Expected keys:
            'source' (str): Path to CSV or CSV content string. (Required)
            'has_header' (bool, optional): Whether the CSV has a header row. Defaults to True.
                                           If False, 'column_names' must be provided.
            'column_names' (List[str], optional): List of column names. Required if 'has_header' is False.
                                                  Used as the header if 'has_header' is False.
            'delimiter' (str, optional): CSV delimiter. Defaults to ','.
            'encoding' (str, optional): File encoding. Defaults to 'utf-8'.
            'required_columns' (List[str], optional): List of required column names.
            'skip_comments' (bool, optional): Whether to skip comments. Defaults to True.
            'quotechar' (str, optional): Character used to quote fields. Defaults to '"'.
            'escapechar' (str, optional): Character used to escape the delimiter. Defaults to None.
            'doublequote' (bool, optional): Whether two consecutive quotechars represent one. Defaults to True.

    Returns:
        A list of dictionaries representing rows from the CSV.

    Raises:
        ValueError: If 'source' is not in profile or if 'column_names' are needed but not provided
                    when has_header is False.
        CSVParsingError: Propagated from `parse_csv` or for profile-specific CSV errors
                         (e.g. required column not in 'column_names' when has_header=False).
    """
    source = profile.get("source")
    if source is None:
        msg = "'source' key is missing from the profile."
        logger.error(msg)
        raise ValueError(msg)

    has_header = profile.get("has_header", True)
    profile_column_names = profile.get("column_names")
    required_columns_profile = profile.get("required_columns")

    if not has_header:
        if not profile_column_names:
            msg = "Profile has 'has_header: False' but no 'column_names' are provided."
            logger.error(msg)
            raise ValueError(msg)

        if required_columns_profile:
            missing_in_profile_columns = [
                col for col in required_columns_profile if col not in profile_column_names
            ]
            if missing_in_profile_columns:
                msg = (f"Required column(s) {', '.join(missing_in_profile_columns)} "
                       f"not found in profile's 'column_names'.")
                logger.error(msg)
                raise CSVParsingError(msg)
        # TODO: Adapt parse_csv or add new function to handle no-header CSVs using profile_column_names.
        # The 'required_columns_profile' are validated against 'profile_column_names' here.
        # For the actual parsing, if has_header is False, parse_csv would need to use
        # profile_column_names as the header and not perform its own required_columns check,
        # or its check should be against profile_column_names.
        # The 'required_columns_profile' have been validated against 'profile_column_names'.
        # So, when providing header_override, parse_csv doesn't need to re-check them.
        # Pass required_columns=None to parse_csv in this case.
        return parse_csv(
            source=source,
            delimiter=profile.get("delimiter", ","),
            encoding=profile.get("encoding", "utf-8"),
            required_columns=None, # Already checked against profile_column_names
            skip_comments=profile.get("skip_comments", True),
            header_override=profile_column_names,
            quotechar=profile.get("quotechar", '"'),
            escapechar=profile.get("escapechar"),
            doublequote=profile.get("doublequote", True),
        )
    else: # has_header is True
        # parse_csv will detect header from source and check required_columns_profile against it.
        return parse_csv(
            source=source,
            delimiter=profile.get("delimiter", ","),
            encoding=profile.get("encoding", "utf-8"),
            required_columns=required_columns_profile,
            skip_comments=profile.get("skip_comments", True),
            quotechar=profile.get("quotechar", '"'),
            escapechar=profile.get("escapechar"),
            doublequote=profile.get("doublequote", True)
            # header_override is None by default
        )

