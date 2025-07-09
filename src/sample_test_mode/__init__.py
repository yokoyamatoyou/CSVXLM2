"""Utilities for sample data conversion test mode."""
from pathlib import Path
from typing import Iterable, List
from lxml import etree

from csv_to_xml_converter.csv_parser import parse_csv


def _csv_to_xml(records: List[dict]) -> str:
    root = etree.Element("records")
    for rec in records:
        r_el = etree.SubElement(root, "record")
        for k, v in rec.items():
            child = etree.SubElement(r_el, k)
            child.text = v
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")


def convert_first_csvs(directories: Iterable[str], output_dir: str) -> List[str]:
    """Convert the first CSV file from each directory into a simple XML file.

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
        first_csv = next(iter(sorted(dir_path.glob("*.csv"))), None)
        if first_csv is None:
            continue
        try:
            records = parse_csv(str(first_csv), encoding="shift_jis")
        except Exception:
            records = []
        xml_str = _csv_to_xml(records)
        xml_file = out_path / f"{dir_path.name}.xml"
        xml_file.write_text(xml_str, encoding="utf-8")
        output_paths.append(str(xml_file))
    return output_paths
