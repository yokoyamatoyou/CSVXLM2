from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from csv_to_xml_converter.rule_engine import apply_rules, _set_nested_attr
from csv_to_xml_converter.models import IntermediateRecord


def test_rule_engine_entry_relationship_and_calculate():
    @dataclass
    class TestERModel(IntermediateRecord):
        anemia_panel_results: List[Dict[str, Any]] = field(default_factory=list)
        hgb_value_direct: Optional[str] = None
        rbc_value_direct: Optional[str] = None

    mock_lookups_er = {
        "$oid_catalog$": {
            "OID.JLAC10.Hgb": "1001-9",
            "OID.JLAC10.RBC": "1002-7",
            "MHLW.CodeSystem.JLAC10": "1.2.392.100495.20.2.10",
        }
    }
    er_rules = [
        {
            "rule_type": "entry_relationship_group",
            "output_field_anchor": "anemia_panel_results",
            "entry_relationship_typeCode": "COMP",
            "components": [
                {
                    "rules": [
                        {"rule_type": "direct_mapping", "input_field": "hgb_val_csv", "output_field": "value"},
                        {"rule_type": "default_value", "output_field": "unit", "value": "g/dL"},
                        {"rule_type": "default_value", "output_field": "code_key", "value": "OID.JLAC10.Hgb"},
                        {"rule_type": "lookup_value", "input_field": "code_key", "lookup_table_name": "$oid_catalog$", "output_field": "code"},
                        {"rule_type": "default_value", "output_field": "codeSystem_key", "value": "MHLW.CodeSystem.JLAC10"},
                        {"rule_type": "lookup_value", "input_field": "codeSystem_key", "lookup_table_name": "$oid_catalog$", "output_field": "codeSystem"},
                        {"rule_type": "default_value", "output_field": "displayName", "value": "HGB"},
                        {"rule_type": "default_value", "output_field": "value_type", "value": "PQ"},
                    ]
                },
                {
                    "rules": [
                        {"rule_type": "direct_mapping", "input_field": "rbc_val_csv", "output_field": "value"},
                        {"rule_type": "default_value", "output_field": "unit", "value": "x10E6/uL"},
                        {"rule_type": "default_value", "output_field": "code_key", "value": "OID.JLAC10.RBC"},
                        {"rule_type": "lookup_value", "input_field": "code_key", "lookup_table_name": "$oid_catalog$", "output_field": "code"},
                        {"rule_type": "default_value", "output_field": "codeSystem_key", "value": "MHLW.CodeSystem.JLAC10"},
                        {"rule_type": "lookup_value", "input_field": "codeSystem_key", "lookup_table_name": "$oid_catalog$", "output_field": "codeSystem"},
                        {"rule_type": "default_value", "output_field": "displayName", "value": "RBC"},
                        {"rule_type": "default_value", "output_field": "value_type", "value": "PQ"},
                    ]
                },
            ],
        }
    ]
    er_data = [{"hgb_val_csv": "12.5", "rbc_val_csv": "4.5"}]
    models = apply_rules(er_data, er_rules, model_class=TestERModel, lookup_tables=mock_lookups_er)
    assert models[0].anemia_panel_results[0]["entry_relationship_typeCode"] == "COMP"

    @dataclass
    class NestedObservation:
        value: Optional[Any] = None
        unit: Optional[str] = None

    @dataclass
    class TestCalcModel(IntermediateRecord):
        bmi_observation: Optional[NestedObservation] = None
        height_cm: Optional[float] = None

        def __post_init__(self):
            if hasattr(super(), "__post_init__"):
                super().__post_init__()
            if self.bmi_observation is None:
                self.bmi_observation = NestedObservation()

    test_model_instance = TestCalcModel()
    _set_nested_attr(test_model_instance, "height_cm", 175.0)
    _set_nested_attr(test_model_instance, "bmi_observation.unit", "kg/m2")
    assert test_model_instance.height_cm == 175.0
    assert test_model_instance.bmi_observation.unit == "kg/m2"

    calc_rules = [
        {
            "rule_type": "calculate",
            "calculation_name": "bmi",
            "input_mapping": [
                {"source_field": "weight_csv", "param_name": "weight_kg", "data_type": "float"},
                {"source_field": "height_m_csv", "param_name": "height_m", "data_type": "float"},
            ],
            "output_field": "bmi_observation.value",
        }
    ]
    calc_data = [{"weight_csv": "70", "height_m_csv": "1.75"}]
    result = apply_rules(calc_data, calc_rules, model_class=TestCalcModel, lookup_tables={})
    expected_bmi = round(70 / (1.75 ** 2), 2)
    assert result[0].bmi_observation.value == expected_bmi


def test_concat_split_create_and_lookup_loading():
    from csv_to_xml_converter.models import ObservationDataItem

    @dataclass
    class TestModel(IntermediateRecord):
        first: Optional[str] = None
        last: Optional[str] = None
        full: Optional[str] = None
        split_a: Optional[str] = None
        split_b: Optional[str] = None
        obs: Optional[ObservationDataItem] = None

    rules = [
        {"rule_type": "concat", "input_fields": ["first", "last"], "delimiter": " ", "output_field": "full"},
        {"rule_type": "split", "input_field": "to_split", "delimiter": "-", "output_fields": ["split_a", "split_b"]},
        {"rule_type": "create_nested_object", "output_field": "obs", "class_name": "ObservationDataItem"},
        {"rule_type": "default_value", "output_field": "code_key", "value": "DocumentTypeCode.SpecificHealthCheckup"},
        {"rule_type": "lookup_value", "input_field": "code_key", "lookup_table_name": "$oid_catalog$", "output_field": "lookup_result"}
    ]

    data = [{"first": "John", "last": "Doe", "to_split": "A-B"}]
    models = apply_rules(data, rules, model_class=TestModel, lookup_tables={})
    m = models[0]
    assert m.full == "John Doe"
    assert m.split_a == "A" and m.split_b == "B"
    assert isinstance(m.obs, ObservationDataItem)
    assert m.lookup_result == "10"  # from oid_catalog.json


def test_nested_object_creation_and_mapping():
    from csv_to_xml_converter.models import ObservationDataItem

    @dataclass
    class ParentModel(IntermediateRecord):
        nested: Optional[ObservationDataItem] = None

    rules = [
        {"rule_type": "create_nested_object", "output_field": "nested", "class_name": "ObservationDataItem"},
        {"rule_type": "direct_mapping", "input_field": "code_in", "output_field": "nested.item_code.code"},
        {"rule_type": "direct_mapping", "input_field": "val_in", "output_field": "nested.value"},
    ]

    data = [{"code_in": "HGB", "val_in": "10.5"}]
    models = apply_rules(data, rules, model_class=ParentModel, lookup_tables={})
    m = models[0]
    assert isinstance(m.nested, ObservationDataItem)
    assert m.nested.item_code.code == "HGB"
    assert m.nested.value == "10.5"


def test_index_and_summary_rules_files():
    from csv_to_xml_converter.rule_engine import load_rules

    @dataclass
    class IndexModel(IntermediateRecord):
        interactionType: Optional[str] = None
        creationTime: Optional[str] = None
        senderIdRootOid: Optional[str] = None
        senderIdExtension: Optional[str] = None
        receiverIdRootOid: Optional[str] = None
        receiverIdExtension: Optional[str] = None
        serviceEventType: Optional[str] = None
        totalRecordCount: Optional[int] = None

    index_rules = load_rules("config_rules/index_rules.json")
    index_data = [{"creation_date": "20240101", "record_count": "5"}]
    idx_model = apply_rules(index_data, index_rules, model_class=IndexModel, lookup_tables={})[0]
    assert idx_model.interactionType == "1"
    assert idx_model.totalRecordCount == 5

    @dataclass
    class SummaryModel(IntermediateRecord):
        serviceEventTypeCode: Optional[str] = None
        serviceEventTypeCodeSystem: Optional[str] = None
        serviceEventTypeDisplayName: Optional[str] = None
        totalSubjectCount: Optional[int] = None
        totalCostAmount_value: Optional[int] = None
        totalCostAmount_currency: Optional[str] = None
        totalClaimAmount_value: Optional[int] = None
        totalClaimAmount_currency: Optional[str] = None

    summary_rules = load_rules("config_rules/summary_rules.json")
    summary_data = [{"total_subjects": "10", "total_cost": "1000", "total_claim": "800"}]
    sum_model = apply_rules(summary_data, summary_rules, model_class=SummaryModel, lookup_tables={})[0]
    assert sum_model.serviceEventTypeCode == "AGG_SUMMARY"
    assert sum_model.totalSubjectCount == 10
    assert sum_model.totalCostAmount_currency == "JPY"
