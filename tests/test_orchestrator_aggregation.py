import os
from lxml import etree
from csv_to_xml_converter.orchestrator import Orchestrator


def test_orchestrator_aggregation(tmp_path):
    cda_path = tmp_path / "cda.xml"
    cda_path.write_text(
        "<cda:ClinicalDocument xmlns:cda=\"urn:hl7-org:v3\"></cda:ClinicalDocument>",
        encoding="utf-8",
    )
    cc08_path = tmp_path / "cc08.xml"
    cc08_path.write_text(
        "<checkupClaim xmlns=\"https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000161103.html\"><settlement><claimAmount value=\"1500\"/></settlement></checkupClaim>",
        encoding="utf-8",
    )
    gc08_path = tmp_path / "gc08.xml"
    gc08_path.write_text(
        "<gc:GuidanceClaimDocument xmlns:gc=\"urn:MHLW:guidance:claim:GC:2021\"><gc:settlementDetails><gc:claimAmount value=\"2500\"/></gc:settlementDetails></gc:GuidanceClaimDocument>",
        encoding="utf-8",
    )

    config = {
        "rule_files": {
            "index_rules": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config_rules", "index_rules.json")),
            "summary_rules": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config_rules", "summary_rules.json")),
        }
    }
    orch = Orchestrator(config)
    index_xsd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "XSD", "ix08_V08.xsd"))
    summary_xsd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "XSD", "su08_V08.xsd"))
    index_out = tmp_path / "index.xml"
    summary_out = tmp_path / "summary.xml"

    assert orch.generate_aggregated_index_xml([str(cda_path)], [str(cc08_path), str(gc08_path)], str(index_out), index_xsd)
    assert orch.generate_aggregated_summary_xml([str(cc08_path), str(gc08_path)], [str(cda_path)], str(summary_out), summary_xsd)

    ns = {"m": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000161103.html"}
    tree_i = etree.parse(str(index_out))
    assert tree_i.xpath("/m:index/m:totalRecordCount/@value", namespaces=ns)[0] == "3"

    tree_s = etree.parse(str(summary_out))
    assert tree_s.xpath("/m:summary/m:totalSubjectCount/@value", namespaces=ns)[0] == "1"
    assert tree_s.xpath("/m:summary/m:totalClaimAmount/@value", namespaces=ns)[0] == "4000"
