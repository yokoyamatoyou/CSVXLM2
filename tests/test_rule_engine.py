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
