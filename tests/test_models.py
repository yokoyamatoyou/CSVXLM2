from csv_to_xml_converter.models import (
    CDAHeaderData,
    II_Element,
    ObservationDataItem,
    CD_Element,
    HealthCheckupRecord,
    ObservationGroup,
    HealthGuidanceRecord,
    MO_Element_Data,
    CheckupSettlementRecord,
    GuidanceSettlementRecord,
)


def test_model_initialization():
    header = CDAHeaderData(document_id=II_Element(root="1.2", extension="doc1"))
    assert header.document_id.root == "1.2"
    height_obs = ObservationDataItem(item_code=CD_Element(code="H", display_name="Height"), value="170", value_type="PQ", unit="cm")
    record = HealthCheckupRecord(header=header)
    record.height = height_obs
    assert record.header.document_id.extension == "doc1"
    group = ObservationGroup(panel_code=CD_Element(code="P", display_name="Panel"))
    group.components.append(height_obs)
    assert len(group.components) == 1
    guidance_header = CDAHeaderData(document_title="Plan")
    guidance_record = HealthGuidanceRecord(header=guidance_header)
    guidance_record.guidance_classification = ObservationDataItem(item_code=CD_Element(code="G", display_name="Class"))
    assert guidance_record.guidance_classification.item_code.display_name == "Class"
    mo_data = MO_Element_Data(value="1000", currency="USD")
    cs_record = CheckupSettlementRecord(document_id_ext="CS1")
    cs_record.total_cost_value = "5000"
    gs_record = GuidanceSettlementRecord()
    gs_record.document_id = II_Element(root="1.2.3", extension="GS")
    gs_record.total_cost_settlement = mo_data
    assert gs_record.total_cost_settlement.currency == "USD"
