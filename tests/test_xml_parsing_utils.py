import os
from csv_to_xml_converter.xml_generator.xml_parsing_utils import (
    get_claim_amount_from_cc08,
    get_claim_amount_from_gc08,
    get_subject_count_from_cda,
)


def test_xml_parsing_utils(tmp_path):
    cc08_path = tmp_path / "cc08.xml"
    gc08_path = tmp_path / "gc08.xml"
    cda_path = tmp_path / "cda.xml"

    cc08_content = (
        "<checkupClaim xmlns=\"https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000161103.html\">"
        "<settlement><claimAmount value=\"12345.67\"/></settlement></checkupClaim>"
    )
    cc08_path.write_text(cc08_content, encoding="utf-8")

    gc08_content = (
        "<gc:GuidanceClaimDocument xmlns:gc=\"urn:MHLW:guidance:claim:GC:2021\">"
        "<gc:settlementDetails><gc:claimAmount value=\"5000\"/></gc:settlementDetails>"
        "</gc:GuidanceClaimDocument>"
    )
    gc08_path.write_text(gc08_content, encoding="utf-8")

    cda_content = (
        "<cda:ClinicalDocument xmlns:cda=\"urn:hl7-org:v3\"></cda:ClinicalDocument>"
    )
    cda_path.write_text(cda_content, encoding="utf-8")

    assert get_claim_amount_from_cc08(str(cc08_path)) == 12345.67
    assert get_claim_amount_from_gc08(str(gc08_path)) == 5000.0
    assert get_subject_count_from_cda(str(cda_path)) == 1
    assert get_subject_count_from_cda(str(cc08_path)) == 0
