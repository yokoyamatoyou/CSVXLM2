# -*- coding: utf-8 -*-
"""
CSV parsing utilities, now using CSV profiles.
"""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import csv
from pathlib import Path
from typing import Dict, List, Any, Optional
import os

class CSVParsingError(Exception):
    """Raised for any CSV-related problem."""
    pass

def parse_csv(
    file_path: str | Path,
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Parses a CSV file based on a provided profile and returns its content.
    The profile dictionary should contain keys like "delimiter", "encoding",
    "header" (bool), and optionally "column_names" (list for no-header CSVs).
    """
    path = Path(file_path)
    if not path.exists():
        raise CSVParsingError(f"CSV file not found: {path}")

    encoding = profile.get("encoding", "utf-8")
    delimiter = profile.get("delimiter", ",")
    has_header = profile.get("header", True)
    profile_column_names = profile.get("column_names") if not has_header else None

    records: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding=encoding, newline="") as fp:
            if has_header:
                reader = csv.DictReader(fp, delimiter=delimiter)
                for row in reader:
                    records.append(dict(row))
            else:
                reader = csv.reader(fp, delimiter=delimiter)
                if profile_column_names:
                    for row_values in reader:
                        num_cols = len(profile_column_names)
                        record = {}
                        for i in range(num_cols):
                            record[profile_column_names[i]] = row_values[i] if i < len(row_values) else None
                        records.append(record)
                else:
                    for row_values in reader:
                        records.append({str(i): col for i, col in enumerate(row_values)})
    except UnicodeDecodeError as exc:
        raise CSVParsingError(f"Unicode decode error in {path} with encoding {encoding}: {exc}") from exc
    except csv.Error as exc:
        raise CSVParsingError(f"CSV parse error in {path}: {exc}") from exc
    except Exception as exc:
        raise CSVParsingError(f"An unexpected error occurred while parsing {path}: {exc}") from exc
    return records

if __name__ == "__main__":
    # Self-test print statements are fine here, as it's for direct execution.
    # If this module's logger was to be tested, basicConfig would be needed here.
    print("CSV Parser module self-test (with profiles)...")
    temp_dir = Path("temp_csv_parser_test_data_profiles")
    os.makedirs(temp_dir, exist_ok=True)

    profile1_header = {"delimiter": ",", "encoding": "utf-8", "header": True}
    profile2_no_header_auto_cols = {"delimiter": ";", "encoding": "utf-8", "header": False}
    profile3_no_header_custom_cols = {"delimiter": ",", "encoding": "shift_jis", "header": False, "column_names": ["colA", "colB", "colC"]}
    profile4_mismatch_cols = {"delimiter": ",", "encoding": "utf-8", "header": False, "column_names": ["colA", "colB", "colC", "colD"]}

    csv_path1 = temp_dir / "test1_header.csv"
    with open(csv_path1, "w", encoding="utf-8") as f: f.write("id,name,value\n1,itemA,100\n2,itemB,200")
    csv_path2 = temp_dir / "test2_no_header_auto.csv"
    with open(csv_path2, "w", encoding="utf-8") as f: f.write("val1;val2\nval3;val4")
    csv_path3 = temp_dir / "test3_no_header_sjis.csv"
    sjis_content = "商品A,1000,雑貨\n商品B,2000,食品"
    with open(csv_path3, "w", encoding="shift_jis") as f: f.write(sjis_content)
    csv_path4_mismatch = temp_dir / "test4_mismatch.csv"
    with open(csv_path4_mismatch, "w", encoding="utf-8") as f: f.write("one,two\nalpha,beta,gamma,delta,epsilon")

    try:
        print("--- Test 1: With header (profile1) ---")
        data1 = parse_csv(csv_path1, profile=profile1_header)
        print(f"Data1: {data1}")
        assert len(data1) == 2 and data1[0]["name"] == "itemA"

        print("--- Test 2: No header, auto column names (profile2) ---")
        data2 = parse_csv(csv_path2, profile=profile2_no_header_auto_cols)
        print(f"Data2: {data2}")
        assert len(data2) == 2 and data2[0]["1"] == "val2"

        print("--- Test 3: No header, custom column names, Shift_JIS (profile3) ---")
        data3 = parse_csv(csv_path3, profile=profile3_no_header_custom_cols)
        print(f"Data3: {data3}")
        assert len(data3) == 2 and data3[0]["colA"] == "商品A" and data3[1]["colC"] == "食品"

        print("--- Test 4: No header, custom columns, row has fewer columns than profile ---")
        data4_less = parse_csv(csv_path4_mismatch, profile=profile4_mismatch_cols)
        print(f"Data4 (less): {data4_less}")
        assert len(data4_less) == 2
        assert data4_less[0]["colA"] == "one" and data4_less[0]["colB"] == "two"
        assert data4_less[0]["colC"] is None and data4_less[0]["colD"] is None

        print("--- Test 5: No header, custom columns, row has more columns than profile (truncates) ---")
        assert data4_less[1]["colA"] == "alpha" and data4_less[1]["colB"] == "beta"
        assert data4_less[1]["colC"] == "gamma" and data4_less[1]["colD"] == "delta"
        assert "epsilon" not in data4_less[1].values()

        print("--- Test 6: FileNotFoundError ---")
        try: parse_csv("non_existent.csv", profile=profile1_header)
        except CSVParsingError as e: print(f"Caught expected: {e}"); assert "not found" in str(e).lower()

        print("CSV Parser self-test (with profiles) PASSED.")
    except Exception as e_main:
        print(f"CSV Parser self-test FAILED: {e_main}")
        raise
    finally:
        for p in [csv_path1, csv_path2, csv_path3, csv_path4_mismatch]:
            if p.exists(): p.unlink()
        if temp_dir.exists(): temp_dir.rmdir()
        print("Cleanup done.")
