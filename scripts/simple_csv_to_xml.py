import csv
from pathlib import Path
import xml.etree.ElementTree as ET


def csv_file_to_xml(csv_path: Path, output_path: Path) -> None:
    """Convert a single CSV file to a basic XML representation."""
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))

    root = ET.Element('csv')
    if rows:
        headers = rows[0]
        for row in rows[1:]:
            row_elem = ET.SubElement(root, 'row')
            for header, value in zip(headers, row):
                col = ET.SubElement(row_elem, 'col', name=header)
                col.text = value

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)


def convert_folder(folder: Path, dest_base: Path) -> None:
    """Convert all CSV files in *folder* into XML under *dest_base*."""
    for csv_file in folder.glob('*.csv'):
        out_path = dest_base / folder.name / f"{csv_file.stem}.xml"
        csv_file_to_xml(csv_file, out_path)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Convert CSV files to simple XML")
    parser.add_argument('source_dirs', nargs='+', help='Directories containing CSV files')
    parser.add_argument('-o', '--output', default='xml_output', help='Output base directory')
    args = parser.parse_args()

    out_base = Path(args.output)
    for src in args.source_dirs:
        folder = Path(src)
        if folder.is_dir():
            convert_folder(folder, out_base)
        else:
            print(f"Warning: {src} is not a directory, skipping")
    print(f"Conversion complete. XML files written under {out_base}")


if __name__ == '__main__':
    main()
