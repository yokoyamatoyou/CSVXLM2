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


def _validate_required_columns(
    header: List[str],
    required: Optional[List[str]],
) -> None:
    """Ensures all ``required`` columns exist in ``header``.

    Raises ``CSVParsingError`` if any required column is missing.
    """
    if not required:
        return

    missing = [c for c in required if c not in header]
    if missing:
        msg = "CSV header is missing required column(s): " + ", ".join(missing)
        logger.error(msg)
        raise CSVParsingError(msg)


def _parse_csv_stream(
    file_obj: io.TextIOBase,
    delimiter: str,
    required_columns: Optional[List[str]],
    skip_comments: bool,
    header_override: Optional[List[str]],
    quotechar: str,
    escapechar: Optional[str],
    doublequote: bool,
) -> List[Dict[str, str]]:
    """Internal helper to parse an opened CSV file object."""
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
        _validate_required_columns(header_cols, required_columns)
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
            _validate_required_columns(header_cols, required_columns)
            continue
        if len(row) != len(header_cols):
            logger.warning(
                "Skipping line %d due to column count mismatch "
                "(expected %d, got %d): %s",
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
    """Parses a CSV from a file path or from string content.

    Providing ``header_override`` allows parsing files that lack a header
    row. ``required_columns`` are validated against either the detected
    header or the supplied override.

    Args:
        source: Path to the CSV file or the CSV data itself.
        delimiter: Character that separates fields. Defaults to ",".
        encoding: Encoding used to read the file. Defaults to "utf-8".
        required_columns: Column names that must be present in the header.
        skip_comments: When ``True`` lines starting with ``#`` are ignored.
        header_override: Column names to use when the CSV has no header row.
        quotechar: Character used to quote fields.
        escapechar: Character used to escape the delimiter.
        doublequote: Whether two consecutive quotechars represent one.

    Returns:
        A list of dictionaries representing rows in the CSV. If no header is
        found and ``header_override`` is not supplied, an empty list is
        returned.

    Raises:
        FileNotFoundError: If ``source`` is a file path that does not exist.
        UnicodeDecodeError: If ``encoding`` cannot decode the file contents.
        CSVParsingError: For I/O errors while reading the file or when
            ``required_columns`` are missing.
    """
    is_file_path = os.path.exists(source) or not (
        "\n" in source or "\r" in source
    )

    if is_file_path and not os.path.exists(source):
        logger.error("File not found: %s", source)
        raise FileNotFoundError(f"No such file or directory: '{source}'")

    try:
        if is_file_path:
            logger.debug("Reading CSV from file path: %s", source)
            with open(source, "r", encoding=encoding, newline="") as file_obj:
                return _parse_csv_stream(
                    file_obj,
                    delimiter,
                    required_columns,
                    skip_comments,
                    header_override,
                    quotechar,
                    escapechar,
                    doublequote,
                )
        logger.debug("Parsing CSV from provided string content.")
        with io.StringIO(source) as file_obj:
            return _parse_csv_stream(
                file_obj,
                delimiter,
                required_columns,
                skip_comments,
                header_override,
                quotechar,
                escapechar,
                doublequote,
            )
    except UnicodeDecodeError as e:
        logger.error(
            "Encoding error for file %s with encoding %s: %s",
            source,
            encoding,
            e,
        )
        raise
    except Exception as e:
        logger.error("Error reading CSV %s: %s", source, e)
        raise CSVParsingError(f"Error reading CSV {source}: {e}") from e


def parse_csv_from_profile(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    """Parse a CSV file based on a profile dictionary.

    Args:
        profile: A dictionary containing parsing parameters. Expected keys:
            'source' (str): Path to CSV or CSV content string. (Required)
            'has_header' (bool, optional): Whether the CSV has a header row.
                Defaults to True. If False, 'column_names' must be provided.
            'column_names' (List[str], optional): Column names used when the
                CSV has no header row.
            'delimiter' (str, optional): CSV delimiter. Defaults to ','.
            'encoding' (str, optional): File encoding. Defaults to 'utf-8'.
            'required_columns' (List[str], optional): Required column names.
            'skip_comments' (bool, optional): Whether to skip comments.
                Defaults to True.
            'quotechar' (str, optional): Character used to quote fields.
                Defaults to '"'.
            'escapechar' (str, optional): Character used to escape the
                delimiter. Defaults to None.
            'doublequote' (bool, optional): Whether two consecutive
                quotechars represent one. Defaults to True.

    Returns:
        A list of dictionaries representing rows from the CSV.

    Raises:
        ValueError: If 'source' is missing or 'column_names' are required when
            ``has_header`` is False.
        CSVParsingError: Propagated from ``parse_csv`` or raised when required
            columns listed in ``column_names`` are missing.
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
            msg = (
                "Profile has 'has_header: False' but no 'column_names' are "
                "provided."
            )
            logger.error(msg)
            raise ValueError(msg)

        if required_columns_profile:
            missing_in_profile_columns = [
                col
                for col in required_columns_profile
                if col not in profile_column_names
            ]
            if missing_in_profile_columns:
                msg = (
                    "Required column(s) "
                    f"{', '.join(missing_in_profile_columns)} "
                    "not found in profile's 'column_names'."
                )
                logger.error(msg)
                raise CSVParsingError(msg)
        # Headerless CSVs are supported by passing profile_column_names as
        # header_override and skipping further column validation here.
        return parse_csv(
            source=source,
            delimiter=profile.get("delimiter", ","),
            encoding=profile.get("encoding", "utf-8"),
            # Already checked against profile_column_names
            required_columns=None,
            skip_comments=profile.get("skip_comments", True),
            header_override=profile_column_names,
            quotechar=profile.get("quotechar", '"'),
            escapechar=profile.get("escapechar"),
            doublequote=profile.get("doublequote", True),
        )
    else:  # has_header is True
        # parse_csv will detect header from source and
        # check required_columns_profile against it.
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
