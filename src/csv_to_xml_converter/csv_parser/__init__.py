# -*- coding: utf-8 -*-
"""
CSV parsing utilities.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Any, Optional

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
) -> List[Dict[str, str]]:
    """
    Parses a CSV from a file path or a string content.

    Args:
        source: Path to the CSV file or a string containing CSV data.
        delimiter: Character used to separate fields.
        encoding: Encoding of the file if 'source' is a path.
        required_columns: A list of column names that must be present in the header.
                          (Checked against auto-detected header or header_override).
        skip_comments: If True, lines starting with '#' will be skipped.
        header_override: Optional list of strings to use as header. If provided,
                         no header is read from the source data itself.

    Returns:
        A list of dictionaries, where each dictionary represents a row
        with column headers as keys.

    Raises:
        FileNotFoundError: If 'source' is a path and the file is not found.
        UnicodeDecodeError: If there's an error decoding the file.
        CSVParsingError: If required columns are missing, if no header is found,
                         or for other CSV format inconsistencies.
    """
    lines: List[str]
    # Heuristic: content usually has newlines. A simple filename typically does not.
    # This helps distinguish "non_existent_file.csv" (should be FileNotFoundError)
    # from "header\ndata" (should be treated as content if no file 'header\ndata' exists).
    is_likely_path = not ("\n" in source or "\r" in source)

    if is_likely_path:
        if not os.path.exists(source):
            logger.error("File not found: %s", source)
            raise FileNotFoundError(f"No such file or directory: '{source}'")
        # If it exists, it's definitely a file path we should try to read
        logger.debug("Source '%s' is an existing file path. Reading content.", source)
        try:
            with open(source, 'r', encoding=encoding) as f:
                lines = f.read().splitlines()
        except UnicodeDecodeError as e: # FileNotFoundError is already handled by os.path.exists
            logger.error("Encoding error for file %s with encoding %s: %s", source, encoding, e)
            raise
        except Exception as e: # Catch other potential read errors
            logger.error("Error reading file %s: %s", source, e)
            raise CSVParsingError(f"Error reading file {source}: {e}") from e
    else: # Not a likely path (e.g., contains newlines) or os.path.exists was false for it
        if os.path.exists(source): # It's not a likely path (e.g. "file\nwith\nnewline_name.csv") but it EXISTS
            logger.debug("Source '%s' with newlines exists as a file. Reading content.", source)
            try:
                with open(source, 'r', encoding=encoding) as f:
                    lines = f.read().splitlines()
            except UnicodeDecodeError as e:
                logger.error("Encoding error for file %s with encoding %s: %s", source, encoding, e)
                raise
            except Exception as e:
                logger.error("Error reading file %s: %s", source, e)
                raise CSVParsingError(f"Error reading file {source}: {e}") from e
        else: # It's not a likely path AND it doesn't exist -> treat as string content
            logger.debug("Source is treated as direct string content. Splitting into lines.")
            lines = source.splitlines()

    records: List[Dict[str, str]] = []
    header_cols: Optional[List[str]] = None
    header_line_index = -1 # Index of the line used as header, or -1 if header_override is used
    data_lines = lines

    if header_override is not None:
        logger.info("Using provided header_override: %s", header_override)
        header_cols = header_override
        # All lines are data lines
    else:
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:  # Skip blank lines
                continue
            if skip_comments and line.startswith('#'):
                logger.debug("Skipping comment line: %s", line)
                continue

            header_cols = [col.strip() for col in line.split(delimiter)]
            header_line_index = i
            data_lines = lines[header_line_index + 1:]
            logger.info("Header found on line %d: %s", i + 1, header_cols)
            break

    if header_cols is None: # Should only happen if not header_override and no header found in content
        logger.warning("No header row found or provided in CSV data.")
        return [] # No header means no parsable data according to current design

    if required_columns: # This check applies to both auto-detected and overridden headers
        missing_cols = [col for col in required_columns if col not in header_cols]
        if missing_cols:
            msg = f"CSV header is missing required column(s): {', '.join(missing_cols)}"
            logger.error(msg)
            raise CSVParsingError(msg)

    for i, line in enumerate(data_lines):
        line_num = header_line_index + 1 + i + 1 # Adjust line_num accounting for header source
        line = line.strip()
        if not line: # Skip blank lines
            continue
        if skip_comments and line.startswith('#'):
            logger.debug("Skipping comment line: %s", line)
            continue

        cells = [cell.strip() for cell in line.split(delimiter)]

        if len(cells) != len(header_cols):
            logger.warning(
                "Skipping line %d due to column count mismatch (expected %d, got %d): '%s'",
                line_num, len(header_cols), len(cells), line
            )
            continue

        record = dict(zip(header_cols, cells))
        records.append(record)

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
            header_override=profile_column_names
        )
    else: # has_header is True
        # parse_csv will detect header from source and check required_columns_profile against it.
        return parse_csv(
            source=source,
            delimiter=profile.get("delimiter", ","),
            encoding=profile.get("encoding", "utf-8"),
            required_columns=required_columns_profile,
            skip_comments=profile.get("skip_comments", True)
            # header_override is None by default
        )

