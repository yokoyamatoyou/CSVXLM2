from lxml import etree
from pathlib import Path
from csv_to_xml_converter.xml_generator import (
    generate_health_checkup_cda,
    generate_health_guidance_cda,
    generate_checkup_settlement_xml,
    generate_guidance_settlement_xml,
)
from csv_to_xml_converter.models import (
    CDAHeaderData,
    II_Element,
    CD_Element,
    HealthCheckupRecord,
    HealthGuidanceRecord,
    CheckupSettlementRecord,
    GuidanceSettlementRecord,
    MO_Element_Data,
)
from csv_to_xml_converter.validator import validate_xml


def test_generate_health_checkup_cda():
    er_test_data = {
        "documentIdExtension": "ER_TEST_DOC",
        "documentEffectiveTime": "20230101",
        "typeIdRootOid": "2.16.840.1.113883.1.3",
        "typeIdExtension": "POCD_HD000040",
        "documentTypeCode": "10",
        "documentTypeCodeSystem": "1.2.392.200119.6.1001",
        "documentTypeDisplayName": "特定健診情報",
        "documentIdRootOid": "1.2.3.4.5.6.7",
        "section_ResultsCode": "RESULTS_SECTION",
        "section_ResultsCodeSystem": "LOCAL_SYS",
        "section_ResultsTitle": "検査結果セクション",
        "examination_results_er_group": [
            {
                "parent_obs_data": {
                    "code": "PANEL_ANEMIA",
                    "codeSystem": "LOCAL_CODES",
                    "displayName": "貧血検査パネル",
                    "classCode": "CLUSTER",
                },
                "entry_relationship_typeCode": "COMP",
                "components": [
                    {"code": "HGB", "codeSystem": "JLAC10", "displayName": "ヘモグロビン", "value": "10.5", "unit": "g/dL", "value_type": "PQ"},
                    {"code": "RBC", "codeSystem": "JLAC10", "displayName": "赤血球数", "value": "350", "unit": "x10E4/uL", "value_type": "PQ"},
                ],
            }
        ],
        "item_heightCode": "HGT_C",
        "item_heightCodeSystem": "SYS_H",
        "item_heightDisplayName": "Height",
        "item_height_value": "175",
        "item_height_unit": "cm",
    }
    element = generate_health_checkup_cda(er_test_data)
    xml = etree.tostring(element, encoding="utf-8").decode("utf-8")
    assert "PANEL_ANEMIA" in xml
    assert "entryRelationship" in xml
    assert "HGB" in xml and "RBC" in xml


def test_generate_health_checkup_cda_dataclass():
    header = CDAHeaderData(document_id=II_Element(root="1.2.3", extension="DOC1"))
    record = HealthCheckupRecord(header=header)
    element = generate_health_checkup_cda(record)
    xml = etree.tostring(element, encoding="utf-8").decode("utf-8")
    assert "DOC1" in xml


def test_generate_other_generators_and_validation(tmp_path):
    cs_record = CheckupSettlementRecord(
        document_id_ext="CS1",
        patient_id_mrn=II_Element(root="1.2", extension="P"),
        checkup_org_id=II_Element(root="1.2", extension="O"),
        insurer_id=II_Element(root="1.2", extension="I"),
        claim_type=CD_Element(code="1"),
        commission_type=CD_Element(code="1"),
        total_points_value="10",
        total_cost_value="1000",
        copayment_amount_value="0",
        claim_amount_value="1000",
    )
    cs_xml = generate_checkup_settlement_xml(cs_record)
    valid_cs, errors_cs = validate_xml(cs_xml, str(Path("cc08_V08.xsd")))
    assert valid_cs is False
    assert errors_cs

    gs_record = GuidanceSettlementRecord(
        document_id=II_Element(root="1.2", extension="GS"),
        author_institution_id=II_Element(root="1.2", extension="AUTH"),
        patient_id_mrn=II_Element(root="1.2", extension="PAT"),
        insurer_id=II_Element(root="1.2", extension="INS"),
        encounter_guidance_org_id=II_Element(root="1.2", extension="ORG"),
        guidance_level=CD_Element(code="1"),
        timing=CD_Element(code="1"),
        copayment_type_hg_card=CD_Element(code="1"),
        points_completed_value="5",
        points_intended_value="10",
        total_cost_settlement=MO_Element_Data(value="1000"),
        copayment_amount_settlement=MO_Element_Data(value="0"),
        claim_amount_settlement=MO_Element_Data(value="1000"),
    )
    gs_xml = generate_guidance_settlement_xml(gs_record, "20230101000000+0000")
    valid_gs, errors_gs = validate_xml(gs_xml, str(Path("gc08_V08.xsd")))
    assert valid_gs is False
    assert errors_gs
