from lxml import etree
from csv_to_xml_converter.xml_generator import generate_health_checkup_cda


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
