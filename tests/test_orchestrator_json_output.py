import json
from csv_to_xml_converter.orchestrator import Orchestrator


def test_json_written(monkeypatch, tmp_path):
    csv_file = tmp_path / "hc.csv"
    csv_file.write_text("doc_id\nDOC1\n", encoding="utf-8")

    rules_file = tmp_path / "hc_rules.json"
    rules = [
        {"rule_type": "direct_mapping", "input_field": "doc_id", "output_field": "documentIdExtension"}
    ]
    rules_file.write_text(json.dumps(rules), encoding="utf-8")

    def fake_gen(obj):
        return "<ClinicalDocument/>"

    def fake_validate_write(self, xml_string, xsd_path, out_path, log_prefix, invalid_out_path=None):
        out_path.write_text(xml_string, encoding="utf-8")
        return True

    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.generate_health_checkup_cda", fake_gen
    )
    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.Orchestrator._validate_and_write_xml",
        fake_validate_write,
    )

    orch = Orchestrator({"csv_profiles": {"hc": {"delimiter": ",", "encoding": "utf-8"}}})
    out_dir = tmp_path / "out"
    orch.process_csv_to_health_checkup_cdas(
        str(csv_file), str(rules_file), "dummy.xsd", str(out_dir), csv_profile_name="hc"
    )

    json_path = csv_file.with_suffix(".json")
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data == [{"doc_id": "DOC1"}]


def test_json_written_guidance_cda(monkeypatch, tmp_path):
    csv_file = tmp_path / "hg.csv"
    csv_file.write_text("doc_id\nDOC1\n", encoding="utf-8")

    rules_file = tmp_path / "hg_rules.json"
    rules = [
        {"rule_type": "direct_mapping", "input_field": "doc_id", "output_field": "documentIdExtension"}
    ]
    rules_file.write_text(json.dumps(rules), encoding="utf-8")

    def fake_gen(obj):
        return "<ClinicalDocument/>"

    def fake_validate_write(self, xml_string, xsd_path, out_path, log_prefix, invalid_out_path=None):
        out_path.write_text(xml_string, encoding="utf-8")
        return True

    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.generate_health_guidance_cda", fake_gen
    )
    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.Orchestrator._validate_and_write_xml",
        fake_validate_write,
    )

    orch = Orchestrator({"csv_profiles": {"hg": {"delimiter": ",", "encoding": "utf-8"}}})
    out_dir = tmp_path / "out"
    orch.process_csv_to_health_guidance_cdas(
        str(csv_file), str(rules_file), "dummy.xsd", str(out_dir), csv_profile_name="hg"
    )

    json_path = csv_file.with_suffix(".json")
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data == [{"doc_id": "DOC1"}]


def test_json_written_checkup_settlement(monkeypatch, tmp_path):
    csv_file = tmp_path / "cs.csv"
    csv_file.write_text("doc_id\nDOC1\n", encoding="utf-8")

    rules_file = tmp_path / "cs_rules.json"
    rules = [
        {"rule_type": "direct_mapping", "input_field": "doc_id", "output_field": "documentIdExtension"}
    ]
    rules_file.write_text(json.dumps(rules), encoding="utf-8")

    def fake_gen(obj):
        return "<Settlement/>"

    def fake_validate_write(self, xml_string, xsd_path, out_path, log_prefix, invalid_out_path=None):
        out_path.write_text(xml_string, encoding="utf-8")
        return True

    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.generate_checkup_settlement_xml", fake_gen
    )
    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.Orchestrator._validate_and_write_xml",
        fake_validate_write,
    )

    orch = Orchestrator({"csv_profiles": {"cs": {"delimiter": ",", "encoding": "utf-8"}}})
    out_dir = tmp_path / "out"
    orch.process_csv_to_checkup_settlement_xmls(
        str(csv_file), str(rules_file), "dummy.xsd", str(out_dir), csv_profile_name="cs"
    )

    json_path = csv_file.with_suffix(".json")
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data == [{"doc_id": "DOC1"}]


def test_json_written_guidance_settlement(monkeypatch, tmp_path):
    csv_file = tmp_path / "gs.csv"
    csv_file.write_text("doc_id\nDOC1\n", encoding="utf-8")

    rules_file = tmp_path / "gs_rules.json"
    rules = [
        {"rule_type": "direct_mapping", "input_field": "doc_id", "output_field": "documentIdExtension"}
    ]
    rules_file.write_text(json.dumps(rules), encoding="utf-8")

    def fake_gen(obj, ts):
        return "<GuidanceSettlement/>"

    def fake_validate_write(self, xml_string, xsd_path, out_path, log_prefix, invalid_out_path=None):
        out_path.write_text(xml_string, encoding="utf-8")
        return True

    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.generate_guidance_settlement_xml", fake_gen
    )
    monkeypatch.setattr(
        "csv_to_xml_converter.orchestrator.Orchestrator._validate_and_write_xml",
        fake_validate_write,
    )

    orch = Orchestrator({"csv_profiles": {"gs": {"delimiter": ",", "encoding": "utf-8"}}})
    out_dir = tmp_path / "out"
    orch.process_csv_to_guidance_settlement_xmls(
        str(csv_file), str(rules_file), "dummy.xsd", str(out_dir), csv_profile_name="gs"
    )

    json_path = csv_file.with_suffix(".json")
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data == [{"doc_id": "DOC1"}]
