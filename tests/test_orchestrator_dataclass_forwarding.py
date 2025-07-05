import json
from csv_to_xml_converter.orchestrator import Orchestrator
from csv_to_xml_converter.models import HealthCheckupRecord, IndexRecord


def test_process_csv_to_hc_uses_dataclass(monkeypatch, tmp_path):
    csv_file = tmp_path / "hc.csv"
    csv_file.write_text("doc_id\nDOC1\n", encoding="utf-8")

    rules_file = tmp_path / "hc_rules.json"
    rules = [
        {"rule_type": "direct_mapping", "input_field": "doc_id", "output_field": "documentIdExtension"}
    ]
    rules_file.write_text(json.dumps(rules), encoding="utf-8")

    seen = {}

    def fake_gen(obj):
        seen['type'] = type(obj)
        return "<ClinicalDocument/>"

    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.generate_health_checkup_cda", fake_gen
    )
    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.validate_xml", lambda xml, xsd: (True, [])
    )

    orch = Orchestrator({"csv_profiles": {"hc": {"delimiter": ",", "encoding": "utf-8"}}})
    out_dir = tmp_path / "out"
    res = orch.process_csv_to_health_checkup_cdas(
        str(csv_file), str(rules_file), "dummy.xsd", str(out_dir), csv_profile_name="hc"
    )
    assert seen.get('type') is HealthCheckupRecord
    assert len(res) == 1


def test_generate_aggregated_index_uses_dataclass(monkeypatch, tmp_path):
    data_xml = tmp_path / "d.xml"
    data_xml.write_text("<ClinicalDocument/>", encoding="utf-8")
    claim_xml = tmp_path / "c.xml"
    claim_xml.write_text(
        "<checkupClaim><settlement><claimAmount value='10'/></settlement></checkupClaim>",
        encoding="utf-8",
    )

    rules_file = tmp_path / "index_rules.json"
    rules = [
        {"rule_type": "default_value", "output_field": "senderIdRootOid", "value": "1"},
        {"rule_type": "default_value", "output_field": "senderIdExtension", "value": "1"},
        {"rule_type": "default_value", "output_field": "receiverIdRootOid", "value": "1"},
        {"rule_type": "default_value", "output_field": "receiverIdExtension", "value": "1"},
        {"rule_type": "direct_mapping", "input_field": "record_count", "output_field": "totalRecordCount"},
        {"rule_type": "data_type_conversion", "input_field": "creation_date", "output_field": "creationTime", "conversion_type": "to_date_yyyymmdd"}
    ]
    rules_file.write_text(json.dumps(rules), encoding="utf-8")

    seen = {}

    def fake_gen(obj):
        seen['type'] = type(obj)
        return "<index/>"

    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.generate_index_xml", fake_gen
    )
    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.validate_xml", lambda xml, xsd: (True, [])
    )

    orch = Orchestrator({})
    out_path = tmp_path / "index.xml"
    ok = orch.generate_aggregated_index_xml(
        [str(data_xml)], [str(claim_xml)], str(out_path), "dummy.xsd", rules_file_path=str(rules_file)
    )
    assert ok
    assert seen.get('type') is IndexRecord
