import os
from csv_to_xml_converter.orchestrator import Orchestrator
from csv_to_xml_converter.rule_engine import load_rules
from csv_to_xml_converter.models import IndexRecord
from csv_to_xml_converter.xml_generator import generate_index_xml


def _write_simple_xsd(path, root_name, require_child=False):
    if require_child:
        content = (
            "<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">"
            f"<xs:element name=\"{root_name}\">"
            "<xs:complexType><xs:sequence>"
            "<xs:element name=\"dummy\" type=\"xs:string\"/>"
            "</xs:sequence></xs:complexType>"
            "</xs:element></xs:schema>"
        )
    else:
        content = (
            "<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">"
            f"<xs:element name=\"{root_name}\"/>"
            "</xs:schema>"
        )
    path.write_text(content, encoding="utf-8")


def test_load_csv_records(tmp_path):
    csv_file = tmp_path / "in.csv"
    csv_file.write_text("a,b\n1,2", encoding="utf-8")
    orch = Orchestrator({"csv_profiles": {"test": {"delimiter": ",", "encoding": "utf-8"}}})
    recs = orch._load_csv_records(str(csv_file), "test")
    assert recs == [{"a": "1", "b": "2"}]


def test_transform_generate_validate(tmp_path):
    orch = Orchestrator({})
    rules = load_rules(os.path.join("config_rules", "index_rules.json"))
    model = orch._transform_record({"creation_date": "20240101", "record_count": "1"}, rules, IndexRecord)
    xml_str = orch._generate_xml_string(model, generate_index_xml)

    xsd_valid = os.path.join("XSD", "ix08_V08.xsd")
    out_valid = tmp_path / "index.xml"
    assert orch._validate_and_write_xml(xml_str, str(xsd_valid), out_valid, "INDEX")
    assert out_valid.exists()

    xsd_invalid = tmp_path / "ix_bad.xsd"
    _write_simple_xsd(xsd_invalid, "index", require_child=True)
    out_bad = tmp_path / "bad.xml"
    invalid_saved = tmp_path / "bad.invalid.xml"
    assert not orch._validate_and_write_xml(xml_str, str(xsd_invalid), out_bad, "INDEX", invalid_saved)
    assert invalid_saved.exists()
