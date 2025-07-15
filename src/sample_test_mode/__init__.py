"""Utilities for sample data conversion test mode."""
from pathlib import Path
from typing import Iterable, List
from lxml import etree
import re

from csv_to_xml_converter.csv_parser import parse_csv


def _sanitize_tag(tag: str) -> str:
    """Return a tag name safe for XML creation."""
    # Replace characters invalid in XML tag names with underscores
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", tag)
    # Tag names cannot start with digits or punctuation
    if not sanitized or not sanitized[0].isalpha() and sanitized[0] not in "_":
        sanitized = f"_{sanitized}"
    return sanitized


def _csv_to_xml(records: List[dict]) -> str:
    root = etree.Element("records")
    for rec in records:
        r_el = etree.SubElement(root, "record")
        for k, v in rec.items():
            safe_tag = _sanitize_tag(k)
            child = etree.SubElement(r_el, safe_tag)
            child.text = v
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")


def convert_first_csvs(
    directories: Iterable[str], output_dir: str, num_files: int = 1
) -> List[str]:
    """Convert the first ``num_files`` CSV files from each directory into XML.

    Parameters
    ----------
    directories: Iterable[str]
        Directories to search for CSV files.
    output_dir: str
        Directory where XML files will be written.

    Returns
    -------
    List[str]
        Paths of generated XML files.
    """
    output_paths: List[str] = []
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    for d in directories:
        dir_path = Path(d)
        if not dir_path.is_dir():
            continue
        csv_files = sorted(dir_path.glob("*.csv"))[:num_files]
        for idx, csv_path in enumerate(csv_files, start=1):
            try:
                records = parse_csv(str(csv_path), encoding="shift_jis")
            except Exception:
                records = []
            xml_str = _csv_to_xml(records)
            suffix = f"_{idx}" if num_files > 1 else ""
            xml_file = out_path / f"{dir_path.name}{suffix}.xml"
            xml_file.write_text(xml_str, encoding="utf-8")
            output_paths.append(str(xml_file))
    return output_paths
