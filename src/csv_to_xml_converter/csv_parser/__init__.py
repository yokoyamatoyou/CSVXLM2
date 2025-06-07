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

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    print("CSV Parser module self-test (New Design)...")
    temp_dir = "temp_csv_parser_tests"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Test data
    csv_content_basic = "name,age,city\nAlice,30,New York\nBob,25,Los Angeles"
    csv_path_basic = os.path.join(temp_dir, "test_basic.csv")
    with open(csv_path_basic, "w", encoding="utf-8") as f:
        f.write(csv_content_basic)

    csv_content_tab = "name\tage\tcity\nCarol\t40\tChicago\nDave\t35\tHouston"
    csv_path_tab = os.path.join(temp_dir, "test_tab.csv")
    with open(csv_path_tab, "w", encoding="utf-8") as f:
        f.write(csv_content_tab)

    # Shift_JIS content: 名前 (name), 年齢 (age), 都市 (city)
    sjis_name = "名前".encode('shift_jis').decode('shift_jis')
    sjis_age = "年齢".encode('shift_jis').decode('shift_jis')
    sjis_city = "都市".encode('shift_jis').decode('shift_jis')
    sjis_data_row1_name = "山田太郎".encode('shift_jis').decode('shift_jis')
    sjis_data_row1_age = "45".encode('shift_jis').decode('shift_jis')
    sjis_data_row1_city = "東京".encode('shift_jis').decode('shift_jis')

    csv_content_sjis = f"{sjis_name},{sjis_age},{sjis_city}\n{sjis_data_row1_name},{sjis_data_row1_age},{sjis_data_row1_city}"
    csv_path_sjis = os.path.join(temp_dir, "test_sjis.csv")
    with open(csv_path_sjis, "w", encoding="shift_jis") as f:
        f.write(csv_content_sjis)

    csv_content_missing_col = "name,city\nEve,50,Miami" # Missing 'age'
    csv_path_missing_col = os.path.join(temp_dir, "test_missing_col.csv")
    with open(csv_path_missing_col, "w", encoding="utf-8") as f:
        f.write(csv_content_missing_col)

    csv_content_comments_empty = """
# This is a comment
name,value
# Another comment

itemA,100

itemB,200
# Trailing comment
"""
    csv_path_comments_empty = os.path.join(temp_dir, "test_comments_empty.csv")
    with open(csv_path_comments_empty, "w", encoding="utf-8") as f:
        f.write(csv_content_comments_empty)

    try:
        print("--- Test 1: Basic CSV (from file) ---")
        records1 = parse_csv(csv_path_basic)
        assert len(records1) == 2
        assert records1[0] == {"name": "Alice", "age": "30", "city": "New York"}
        assert records1[1] == {"name": "Bob", "age": "25", "city": "Los Angeles"}
        print("Test 1 PASSED")

        print("--- Test 2: Tab-separated CSV (from file) ---")
        records2 = parse_csv(csv_path_tab, delimiter='\t')
        assert len(records2) == 2
        assert records2[0] == {"name": "Carol", "age": "40", "city": "Chicago"}
        print("Test 2 PASSED")

        print("--- Test 3: Shift_JIS encoded CSV (from file) ---")
        records3 = parse_csv(csv_path_sjis, encoding='shift_jis')
        assert len(records3) == 1
        # After decoding, keys and values should be standard Python strings
        assert records3[0][sjis_name] == sjis_data_row1_name
        assert records3[0][sjis_age] == sjis_data_row1_age
        assert records3[0][sjis_city] == sjis_data_row1_city
        print("Test 3 PASSED")

        print("--- Test 4: Required column missing (from file) ---")
        try:
            parse_csv(csv_path_missing_col, required_columns=["name", "age", "city"])
            assert False, "ValueError was not raised for missing required column"
        except CSVParsingError as e:
            assert "CSV header is missing required column(s): age" in str(e), f"Error message mismatch: {str(e)}"
            print(f"Caught expected CSVParsingError: {e}")
        print("Test 4 PASSED")

        print("--- Test 5: Skip empty lines and comments (from file) ---")
        records5 = parse_csv(csv_path_comments_empty)
        assert len(records5) == 2
        assert records5[0] == {"name": "itemA", "value": "100"}
        assert records5[1] == {"name": "itemB", "value": "200"}
        print("Test 5 PASSED")

        print("--- Test 6: Basic CSV (from string content) ---")
        records6 = parse_csv(csv_content_basic)
        assert len(records6) == 2
        assert records6[0] == {"name": "Alice", "age": "30", "city": "New York"}
        print("Test 6 PASSED")

        print("--- Test 7: Using parse_csv_from_profile ---")
        profile_test = {
            "source": csv_path_basic,
            "delimiter": ",",
            "encoding": "utf-8",
            "required_columns": ["name", "age"]
        }
        records7 = parse_csv_from_profile(profile_test)
        assert len(records7) == 2
        assert records7[0]["name"] == "Alice"
        print("Test 7 PASSED")

        print("--- Test 8: Profile missing 'source' ---")
        try:
            parse_csv_from_profile({"delimiter": ","}) # type: ignore
            assert False, "ValueError not raised for profile missing source"
        except ValueError as e:
            assert "'source' key is missing" in str(e)
            print(f"Caught expected ValueError: {e}")
        print("Test 8 PASSED")

        # New tests for has_header=False and profile_column_names logic
        print("--- Test 8.1: Profile with has_header=False but no column_names ---")
        profile_no_cols = {
            "source": "dummy_content\n1,2,3", # content doesn't matter much here
            "has_header": False
        }
        try:
            parse_csv_from_profile(profile_no_cols)
            assert False, "ValueError not raised for has_header=False without column_names"
        except ValueError as e:
            assert "no 'column_names' are provided" in str(e)
            print(f"Caught expected ValueError: {e}")
        print("Test 8.1 PASSED")

        print("--- Test 8.2: Profile with has_header=False, required column missing from profile's column_names ---")
        profile_req_col_missing_from_profile_cols = {
            "source": "dummy_content\n1,2,3",
            "has_header": False,
            "column_names": ["colA", "colB"],
            "required_columns": ["colA", "colC"]
        }
        try:
            parse_csv_from_profile(profile_req_col_missing_from_profile_cols)
            assert False, "CSVParsingError not raised for required col missing in profile's column_names"
        except CSVParsingError as e:
            assert "Required column(s) colC not found in profile's 'column_names'" in str(e)
            print(f"Caught expected CSVParsingError: {e}")
        print("Test 8.2 PASSED")

        print("--- Test 8.3: Profile with has_header=False, all required columns in profile's column_names (valid profile config) ---")
        csv_content_no_header_data = "valA1,valB1\nvalA2,valB2" # Data for parse_csv to (mis)interpret
        csv_path_no_header_data = os.path.join(temp_dir, "test_no_header_data.csv")
        with open(csv_path_no_header_data, "w", encoding="utf-8") as f:
            f.write(csv_content_no_header_data)

        profile_valid_no_header = {
            "source": csv_path_no_header_data,
            "has_header": False,
            "column_names": ["colA", "colB"], # These are the intended headers
            "required_columns": ["colA"]      # This is valid against 'column_names'
        }
        try:
            # This call tests the profile validation in parse_csv_from_profile.
            # parse_csv will still run and might interpret "valA1,valB1" as a header.
            # If "required_columns": ["colA"] is passed to parse_csv, it will then check
            # With header_override, parse_csv will use ["colA", "colB"] as headers.
            # parse_csv_from_profile passes required_columns=None to parse_csv in this case,
            # so parse_csv's internal required_columns check is skipped.
            # The data "valA1,valB1", "valA2,valB2" should be parsed correctly.
            records8_3 = parse_csv_from_profile(profile_valid_no_header)
            assert len(records8_3) == 2, f"Test 8.3 Expected 2 records, got {len(records8_3)}"
            assert records8_3[0] == {"colA": "valA1", "colB": "valB1"}
            assert records8_3[1] == {"colA": "valA2", "colB": "valB2"}
            print("Test 8.3 PASSED: Correctly parsed with has_header=False and valid profile.")

        except Exception as e: # Catch any exception, not just CSVParsingError
            assert False, f"Test 8.3 FAILED with an unexpected error: {e}"

        print("--- Test 8.4: Profile with has_header=False, profile required_columns, and valid data ---")
        # This is similar to 8.3 but explicitly tests that profile's required_columns
        # are for profile validation and don't interfere with parse_csv when header_override is used.
        csv_content_no_header_data_req = "valX,valY\nvalZ,valW"
        csv_path_no_header_data_req = os.path.join(temp_dir, "test_no_header_data_req.csv")
        with open(csv_path_no_header_data_req, "w", encoding="utf-8") as f:
            f.write(csv_content_no_header_data_req)

        profile_valid_no_header_with_req = {
            "source": csv_path_no_header_data_req,
            "has_header": False,
            "column_names": ["headerX", "headerY"],
            "required_columns": ["headerX"] # This is for profile validation, should pass.
        }
        try:
            records8_4 = parse_csv_from_profile(profile_valid_no_header_with_req)
            assert len(records8_4) == 2
            assert records8_4[0] == {"headerX": "valX", "headerY": "valY"}
            assert records8_4[1] == {"headerX": "valZ", "headerY": "valW"}
            print("Test 8.4 PASSED")
        except Exception as e:
            assert False, f"Test 8.4 FAILED with an unexpected error: {e}"


        print("--- Test 9: File Not Found ---")
        try:
            parse_csv("non_existent_file.csv")
            assert False, "FileNotFoundError not raised"
        except FileNotFoundError:
            print("Caught expected FileNotFoundError")
        print("Test 9 PASSED")

        print("--- Test 10: Column count mismatch ---")
        # This test relies on observing log output, manual check for now
        # Or we could capture logs if using a more sophisticated test framework
        csv_content_col_mismatch = "header1,header2\ndata1\ndata1,data2,data3"
        records10 = parse_csv(csv_content_col_mismatch)
        # Only valid lines are parsed, so records10 should be empty
        assert len(records10) == 0, f"Expected 0 records, got {len(records10)}"
        print("Test 10 PASSED (check logs for warnings)")


        print("\nAll new CSV Parser self-tests PASSED.")

    except AssertionError as e:
        print(f"\nSelf-test FAILED: {e}")
        raise
    except Exception as e:
        print(f"\nSelf-test FAILED with unexpected error: {e}")
        raise
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, item))
            os.rmdir(temp_dir)
        print(f"Cleaned up temp directory: {temp_dir}")
