# -*- coding: utf-8 -*-
"""
Rule Engine with entry_relationship_group support.
"""
import json, os, logging, re
import sys # Required for self-test logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__) # Moved logger definition up

def _set_nested_attr(target_obj: Any, attr_path: str, value: Any):
    logger.debug(f"Setting nested attr: path='{attr_path}', value='{value}' on obj of type {type(target_obj)}")
    parts = attr_path.split('.')
    obj_to_set_on = target_obj
    try:
        for i, part in enumerate(parts[:-1]):
            next_obj = getattr(obj_to_set_on, part)
            if next_obj is None:
                logger.warning(f"Intermediate object is None at '{'.'.join(parts[:i+1])}' while trying to set '{attr_path}'. Value might not be set if parent object was None.")
                return
            obj_to_set_on = next_obj
        setattr(obj_to_set_on, parts[-1], value)
        logger.debug(f"Successfully set '{parts[-1]}' on object of type {type(obj_to_set_on)} to '{value}'")
    except AttributeError as e:
        logger.error(f"AttributeError while setting nested attribute '{attr_path}': {e}. Object path may be invalid or intermediate object not initialized.", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error while setting nested attribute '{attr_path}': {e}", exc_info=True)

# Assuming models.py is one level up
# For self-test, ensure path allows this or use try-except
try:
    from ..models import IntermediateRecord
except ImportError:
    # This allows the self-test to run if models.py is not found via relative import
    # This might happen if rule_engine is run as __main__ without the package context
    logger.warning("Could not import IntermediateRecord from ..models. Self-test will use a local definition.")
    IntermediateRecord = None # Set to None if import fails

# Calculation Helper Functions
def calculate_bmi(weight_kg: Optional[float], height_m: Optional[float]) -> Optional[float]:
    if weight_kg is None or height_m is None or height_m == 0:
        logger.warning(f"Cannot calculate BMI with weight={weight_kg}, height={height_m}")
        return None
    try:
        bmi = float(weight_kg) / (float(height_m) ** 2)
        return round(bmi, 2) # Round to 2 decimal places
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating BMI (weight={weight_kg}, height={height_m}): {e}")
        return None

CALCULATION_FUNCTIONS = {
    "bmi": calculate_bmi,
    # Add other calculation functions here as needed
}

class RuleApplicationError(Exception): pass

def to_integer(v: Any) -> Optional[int]:
    if v is None or str(v).strip() == "": return None;
    try: return int(str(v));
    except ValueError: raise RuleApplicationError(f"Int conversion error: {v}")

def to_date_yyyymmdd(v: Any) -> Optional[str]:
    s_v: Optional[str] = None # Explicitly initialize s_v
    if v is None: return None
    s_v = str(v).strip()
    if not s_v: return None
    m = re.match(r"^(\d{4})[\/-]?(\d{1,2})[\/-]?(\d{1,2})$", s_v);
    if m: y,mo,d = m.groups(); return f"{y}{mo.zfill(2)}{d.zfill(2)}";
    if re.match(r"^\d{8}$", s_v): return s_v;
    raise RuleApplicationError(f"Date conversion error: {v}")

def to_boolean(v: Any) -> Optional[bool]:
    if v is None: return None; s_v = str(v).strip().lower();
    if s_v in ["true", "1", "yes", "y"]: return True;
    elif s_v in ["false", "0", "no", "n"]: return False;
    elif s_v == "": return None;
    raise RuleApplicationError(f"Bool conversion error: {v}")

def load_rules(p: str) -> List[Dict[str, Any]]:
    try:
        with open(p, "r", encoding="utf-8") as fp: rules = json.load(fp);
        if not isinstance(rules, list): raise ValueError("Rules file must be a JSON list.")
        return rules;
    except Exception as e: logger.exception(f"Err load rules {p}"); raise RuleApplicationError(f"Load err: {e}")

def _evaluate_condition(c: Dict[str,Any], i_rec: Dict[str,Any], current_output_target: Any) -> bool:
    f=c.get("input_field")
    # v_s is the source of the data for the condition check
    v_s = current_output_target if c.get("source")=="output" else i_rec

    a_v = None
    # Check if the source is a dictionary (like input_rec or temp dicts) or a model instance
    if isinstance(v_s, dict):
        a_v = v_s.get(f)
    else: # Assumed to be a model instance
        a_v = getattr(v_s, f, None)

    op=c.get("operator","equals"); cmp_v=c.get("value")
    if op=="equals": return str(a_v)==str(cmp_v)
    elif op == "not_equals": return str(a_v) != str(cmp_v)
    elif op == "exists": return f is not None and a_v is not None
    elif op == "not_exists": return a_v is None
    elif op == "is_empty": return a_v is None or str(a_v).strip() == ""
    elif op == "is_not_empty": return a_v is not None and str(a_v).strip() != ""
    else: logger.warning(f"Unknown condition operator {op}"); return False
    # This line should ideally not be reached if all ops are covered and return.
    # Adding a default False return for safety, though it implies an unhandled case or logic error.
    return False


def _apply_single_rule(rule: Dict[str, Any], i_rec: Dict[str, Any], output_target: Any, lookups: Optional[Dict[str, Dict[str, Any]]] = None):
    rt = rule.get("rule_type"); of = rule.get("output_field"); inf = rule.get("input_field")
    is_dict_target = isinstance(output_target, dict)

    if rt in [None, "comment"]: return

    # Allow lookup_value with output_mappings to not have a primary output_field
    if rt == "lookup_value" and rule.get("output_mappings"):
        pass # Proceed, specific checks for output_mappings will handle assignment
    elif not of and rt not in ["conditional_mapping", "entry_relationship_group"]:
        logger.warning(f"Rule (type: {rt}) missing output_field (and not a special case like lookup_value with output_mappings, conditional_mapping, or entry_relationship_group). Rule: {rule}")
        return

    if rt == "direct_mapping":
        if not inf: logger.warning(f"Direct mapping for {of} missing input_field: {rule}"); return
        if inf in i_rec:
            if is_dict_target: output_target[of] = i_rec[inf]
            else: _set_nested_attr(output_target, of, i_rec[inf])
    elif rt == "default_value":
        val = rule.get("value"); cond_f = rule.get("input_field"); apply_default = True
        if cond_f:
            cond_f_val = i_rec.get(cond_f)
            apply_default = cond_f_val is None or str(cond_f_val).strip() == ""
        if apply_default:
            if is_dict_target: output_target[of] = val
            else: _set_nested_attr(output_target, of, val)

        current_val_debug = output_target.get(of) if is_dict_target else getattr(output_target, of, "NOT_SET") # This getattr might fail for nested
        logger.debug(f"DEFAULT_VALUE: rule={rule}, input_field_condition='{cond_f}', value_in_input='{i_rec.get(cond_f)}', apply_default={apply_default}, output_field='{of}', value_set='{current_val_debug}'")
    elif rt == "data_type_conversion":
        conv_type = rule.get("conversion_type"); val = i_rec.get(inf)
        converted_value = None
        if val is not None:
            if conv_type == "to_integer": converted_value = to_integer(val)
            elif conv_type == "to_date_yyyymmdd": converted_value = to_date_yyyymmdd(val)
            elif conv_type == "to_boolean": converted_value = to_boolean(val)
            else: raise RuleApplicationError(f"Unknown conversion_type: {conv_type}")
        if is_dict_target: output_target[of] = converted_value
        else: _set_nested_attr(output_target, of, converted_value)
    elif rt == "lookup_value":
        if not inf: logger.warning(f"Lookup for rule missing input_field: {rule}"); return # Removed 'of' as it might not be present

        key_s_v = output_target.get(inf) if is_dict_target else getattr(output_target, inf, None)
        if key_s_v is None and inf in i_rec : key_s_v = i_rec.get(inf)

        lookup_k = str(key_s_v) if key_s_v is not None else None
        tbl_n = rule.get("lookup_table_name")
        # Ensure 'of' is handled correctly or if output_mappings is present
        logger.debug(f"LOOKUP_VALUE: lookup_input_field='{inf}', key_source_value='{key_s_v}', final_lookup_key='{lookup_k}', table_name='{tbl_n}'")
        if not tbl_n: raise RuleApplicationError(f"Lookup rule missing table_name: {rule}")
        if not lookups: logger.error(f"Lookup tables dictionary is missing/None for rule: {rule}"); raise RuleApplicationError("Lookup tables not provided")
        actual_table = lookups.get(tbl_n)
        if actual_table is None:
            logger.warning(f"LOOKUP_VALUE: Lookup table \"{tbl_n}\" not found. Available: {list(lookups.keys())}")
            # Handle default_on_miss for single output_field if output_mappings not present
            if of and not rule.get("output_mappings"):
                if is_dict_target: output_target[of] = rule.get("default_on_miss")
                else: _set_nested_attr(output_target, of, rule.get("default_on_miss"))
            return
        logger.debug(f"LOOKUP_VALUE: Table \"{tbl_n}\" sample keys: {list(actual_table.keys())[:5] if actual_table else 'TABLE_IS_EMPTY_OR_NONE'}. Attempting to get key: \"{lookup_k}\".")
        result = actual_table.get(lookup_k, rule.get("default_on_miss"))

        output_mappings = rule.get("output_mappings")
        if output_mappings and isinstance(result, dict):
            logger.debug(f"LOOKUP_VALUE: Applying output_mappings. Lookup result: {result}")
            for mapping in output_mappings:
                source_key = mapping.get("source_key_from_lookup")
                target_prop = mapping.get("target_property")
                if source_key and target_prop:
                    value_to_set = result.get(source_key)
                    if is_dict_target: # This case is less likely for complex model mapping
                        logger.warning("output_mappings used with dict target, direct assignment to target_prop")
                        output_target[target_prop] = value_to_set
                    else:
                        _set_nested_attr(output_target, target_prop, value_to_set)
                else:
                    logger.warning(f"Invalid mapping {mapping} in rule: {rule}")
        elif of: # Original behavior: assign whole result to single output_field 'of'
            if is_dict_target:
                output_target[of] = result
            else:
                _set_nested_attr(output_target, of, result)
            logger.debug(f"LOOKUP_VALUE: output_field='{of}', looked_up_value='{result}' (single field assignment)")
        else:
            logger.warning(f"LOOKUP_VALUE: Rule for input_field '{inf}' has neither 'output_field' nor 'output_mappings'. Lookup result not assigned. Rule: {rule}")
    elif rt == "calculate":
        calculation_name = rule.get("calculation_name")
        input_mapping = rule.get("input_mapping", [])
        output_field = rule.get("output_field") # 'of' is already defined but using rule's "output_field" for clarity

        if not calculation_name or not output_field:
            logger.warning(f"Calculate rule missing calculation_name or output_field: {rule}"); return

        calc_func = CALCULATION_FUNCTIONS.get(calculation_name)
        if not calc_func:
            logger.error(f"Calculation function '{calculation_name}' not found in CALCULATION_FUNCTIONS."); return

        kwargs = {}
        try:
            for mapping_item in input_mapping: # Renamed 'mapping' to 'mapping_item' to avoid conflict
                source_field = mapping_item.get("source_field")
                param_name = mapping_item.get("param_name")
                source_type = mapping_item.get("source_type", "input_record") # Default to input_record
                data_type = mapping_item.get("data_type")

                if not source_field or not param_name:
                    logger.warning(f"Invalid input_mapping item in calculate rule: {mapping_item}. Skipping this parameter."); continue

                val_src_obj = i_rec if source_type == "input_record" else output_target

                raw_value = None
                if isinstance(val_src_obj, dict): raw_value = val_src_obj.get(source_field)
                else: raw_value = getattr(val_src_obj, source_field, None)

                if raw_value is None and "default_if_missing" in mapping_item:
                    raw_value = mapping_item["default_if_missing"]

                converted_value = raw_value
                if data_type == "float":
                    if raw_value is not None: converted_value = float(str(raw_value)) # Ensure string conversion before float
                    else: converted_value = None
                elif data_type == "integer":
                    if raw_value is not None: converted_value = to_integer(raw_value)
                    else: converted_value = None
                # Add other data_type conversions as needed

                kwargs[param_name] = converted_value

            logger.debug(f"Calling calculation function '{calculation_name}' with args: {kwargs}")
            calculated_value = calc_func(**kwargs)

            if is_dict_target: output_target[output_field] = calculated_value
            else: _set_nested_attr(output_target, output_field, calculated_value)
            logger.debug(f"CALCULATE: output_field='{output_field}', calculated_value='{calculated_value}'")

        except Exception as e:
            logger.error(f"Error during 'calculate' rule execution for '{calculation_name}': {e}", exc_info=True)
            if hasattr(output_target, 'errors') and isinstance(getattr(output_target, 'errors'), list):
                 getattr(output_target, 'errors').append(f"Calculation error for {calculation_name}: {e}")
    elif rt == "conditional_mapping":
        cond_def = rule.get("condition",{})
        if _evaluate_condition(cond_def, i_rec, output_target): # Pass output_target as current_output_target
            for sr in rule.get("then_rules",[]): _apply_single_rule(sr, i_rec, output_target, lookups)
        else:
            for sr in rule.get("else_rules",[]): _apply_single_rule(sr, i_rec, output_target, lookups)
    elif rt == "entry_relationship_group":
        of_anchor = rule.get("output_field_anchor")
        if not of_anchor: raise RuleApplicationError(f"ER group rule missing output_field_anchor: {rule}")
        if is_dict_target: raise RuleApplicationError(f"ER group rule output_field_anchor '{of_anchor}' cannot target a plain dict. Target must be a model instance.")

        er_type_code = rule.get("entry_relationship_typeCode", "COMP")
        components_def = rule.get("components", [])
        processed_components = []
        for comp_def in components_def:
            temp_comp_output_rec = {}
            component_rules = comp_def.get("rules", [])
            if component_rules:
                for sub_rule_def in component_rules:
                    _apply_single_rule(sub_rule_def, i_rec, temp_comp_output_rec, lookups)
                processed_components.append(temp_comp_output_rec)

        if not hasattr(output_target, of_anchor) or not isinstance(getattr(output_target, of_anchor, None), list):
            setattr(output_target, of_anchor, [])

        getattr(output_target, of_anchor).append({
            "entry_relationship_typeCode": er_type_code,
            "components": processed_components
        })
    elif rt not in [None, "comment"]: logger.warning(f"Unknown rule_type: {rt} in rule {rule}")

def apply_rules(data: List[Dict[str, Any]], rules: List[Dict[str, Any]], model_class: type, lookup_tables: Optional[Dict[str, Dict[str, Any]]] = None) -> List[IntermediateRecord]:
    transformed_data: List[IntermediateRecord] = []
    for rec_idx, input_rec in enumerate(data):
        model_instance = model_class()
        if isinstance(model_instance, IntermediateRecord):
            model_instance.raw_input_data = input_rec.copy()
        else:
            logger.warning(f"Model class {model_class.__name__} does not inherit from IntermediateRecord. raw_input_data and errors fields might be unavailable.")

        for rule_idx, rule_def in enumerate(rules):
            try:
                # Correctly get rule_type for the check
                current_rule_type = rule_def.get("rule_type")
                if current_rule_type == "entry_relationship_group":
                    _apply_single_rule(rule_def, input_rec, model_instance, lookup_tables)
                elif current_rule_type == "conditional_mapping":
                     _apply_single_rule(rule_def, input_rec, model_instance, lookup_tables)
                else:
                    _apply_single_rule(rule_def, input_rec, model_instance, lookup_tables)

            except Exception as e:
                error_msg = f"Err @ rec {rec_idx} rule {rule_idx} ({rule_def.get('rule_type')} for {rule_def.get('output_field', rule_def.get('output_field_anchor'))}): {e}"
                logger.error(error_msg, exc_info=False)
                # Check if model_instance has 'errors' attribute and it's a list
                if hasattr(model_instance, 'errors') and isinstance(getattr(model_instance, 'errors'), list):
                    getattr(model_instance, 'errors').append(error_msg)
                elif IntermediateRecord is not None and isinstance(model_instance, IntermediateRecord): # Fallback, less ideal if IntermediateRecord is object
                     model_instance.errors.append(error_msg)
                # Decide if to continue processing rules for this record or skip to next record
        transformed_data.append(model_instance)
    return transformed_data

if __name__ == "__main__":
    from dataclasses import dataclass, field # Ensure dataclass and field are available

    # If IntermediateRecord was not successfully imported (e.g. running as script),
    # define a local version for the self-test *before* TestERModel inherits from it.
    _IntermediateRecord_imported_check = True # Assume imported unless changed by except block
    try:
        # This check is to see if the import from the top of the file succeeded.
        # If IntermediateRecord is None, it means the import failed.
        if IntermediateRecord is None:
            _IntermediateRecord_imported_check = False
    except NameError: # IntermediateRecord itself is not defined
         _IntermediateRecord_imported_check = False

    if not _IntermediateRecord_imported_check:
        @dataclass
        class IntermediateRecord: # Minimal local definition for self-test
            raw_input_data: Dict[str, Any] = field(default_factory=dict, repr=False)
            errors: List[str] = field(default_factory=list)
            def __str__(self): return f"{self.__class__.__name__}(errors={len(self.errors)})"
        logger.info("Using local IntermediateRecord for self-test, as import failed or was None.")
    else:
        logger.info("Using imported IntermediateRecord for self-test.")

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout)

    logger.info("--- Rule Engine Self-Test for entry_relationship_group with Models ---")
    @dataclass
    class TestERModel(IntermediateRecord):
        anemia_panel_results: List[Dict[str, Any]] = field(default_factory=list)
        # Add other fields that rules might populate if necessary for tests
        # Example fields based on the rules:
        hgb_value_direct: Optional[str] = None
        rbc_value_direct: Optional[str] = None

    mock_lookups_er = {
        "$oid_catalog$": {
            "OID.JLAC10.Hgb": "1001-9",
            "OID.JLAC10.RBC": "1002-7",
            "MHLW.CodeSystem.JLAC10": "1.2.392.100495.20.2.10"
         }
    }
    er_rules = [
        {"rule_type": "entry_relationship_group",
         "output_field_anchor": "anemia_panel_results",
         "entry_relationship_typeCode": "COMP",
         "components": [
            { # Component 1: HGB
              "rules": [
                {"rule_type": "direct_mapping", "input_field": "hgb_val_csv", "output_field": "value"},
                {"rule_type": "default_value", "output_field": "unit", "value": "g/dL"},
                {"rule_type": "default_value", "output_field": "code_key", "value": "OID.JLAC10.Hgb"},
                {"rule_type": "lookup_value", "input_field": "code_key", "lookup_table_name": "$oid_catalog$", "output_field": "code"},
                {"rule_type": "default_value", "output_field": "codeSystem_key", "value": "MHLW.CodeSystem.JLAC10"},
                {"rule_type": "lookup_value", "input_field": "codeSystem_key", "lookup_table_name": "$oid_catalog$", "output_field": "codeSystem"},
                {"rule_type": "default_value", "output_field": "displayName", "value": "HGB"},
                {"rule_type": "default_value", "output_field": "value_type", "value": "PQ"}
              ]
            },
            { # Component 2: RBC
              "rules": [
                {"rule_type": "direct_mapping", "input_field": "rbc_val_csv", "output_field": "value"},
                {"rule_type": "default_value", "output_field": "unit", "value": "x10E6/uL"},
                {"rule_type": "default_value", "output_field": "code_key", "value": "OID.JLAC10.RBC"},
                {"rule_type": "lookup_value", "input_field": "code_key", "lookup_table_name": "$oid_catalog$", "output_field": "code"},
                {"rule_type": "default_value", "output_field": "codeSystem_key", "value": "MHLW.CodeSystem.JLAC10"},
                {"rule_type": "lookup_value", "input_field": "codeSystem_key", "lookup_table_name": "$oid_catalog$", "output_field": "codeSystem"},
                {"rule_type": "default_value", "output_field": "displayName", "value": "RBC"},
                {"rule_type": "default_value", "output_field": "value_type", "value": "PQ"}
              ]
            }
        ]}
    ]
    er_data = [{"hgb_val_csv": "12.5", "rbc_val_csv": "4.5"}]
    # Note: model_class=TestERModel is added here
    transformed_er_models = apply_rules(er_data, er_rules, model_class=TestERModel, lookup_tables=mock_lookups_er)

    # print(f"ER Transformed Models: {transformed_er_models}") # Printing list of model instances
    assert len(transformed_er_models) == 1, "Should transform one record into one model instance"
    model_out = transformed_er_models[0]
    assert isinstance(model_out, TestERModel), f"Output is not of type TestERModel, but {type(model_out)}"

    # Log the raw input data stored in the model for reference
    logger.debug(f"Model raw input data: {model_out.raw_input_data}")

    assert hasattr(model_out, "anemia_panel_results"), "Model instance missing 'anemia_panel_results' attribute"
    assert isinstance(model_out.anemia_panel_results, list), "'anemia_panel_results' is not a list"
    assert len(model_out.anemia_panel_results) == 1, "Should be one ER group in anemia_panel_results"

    group = model_out.anemia_panel_results[0]
    assert group["entry_relationship_typeCode"] == "COMP", "ER type code mismatch"
    assert len(group["components"]) == 2, "Should be two components"

    hgb_component = next((c for c in group["components"] if c.get("displayName") == "HGB"), None)
    rbc_component = next((c for c in group["components"] if c.get("displayName") == "RBC"), None)

    assert hgb_component is not None, "HGB component not found"
    assert hgb_component["value"] == "12.5" and hgb_component["code"] == "1001-9", f"HGB data mismatch: {hgb_component}"

    assert rbc_component is not None, "RBC component not found"
    assert rbc_component["value"] == "4.5" and rbc_component["code"] == "1002-7", f"RBC data mismatch: {rbc_component}"
    logger.info("--- Rule Engine entry_relationship_group with Models self-test PASSED. ---")

    # Add near the top of the if __name__ == "__main__" block, after TestERModel
    @dataclass
    class TestLookupModel(IntermediateRecord):
        gender_code: Optional[str] = None
        gender_oid: Optional[str] = None
        gender_display: Optional[str] = None
        birth_date_formatted: Optional[str] = None # For date format test
        status_code: Optional[str] = None # For conditional test
        status_description: Optional[str] = None # For conditional test

    logger.info("--- Rule Engine Self-Test for _set_nested_attr and 'calculate' rule ---")

    @dataclass
    class NestedObservation:
        value: Optional[Any] = None
        unit: Optional[str] = None

    @dataclass
    class TestCalcModel(IntermediateRecord): # type: ignore
        bmi_observation: Optional[NestedObservation] = None
        height_cm: Optional[float] = None # For testing direct set

        def __post_init__(self):
            # Ensure IntermediateRecord's __post_init__ is called if it has one and is not object()
            if hasattr(super(), '__post_init__'):
                super().__post_init__() # type: ignore
            if self.bmi_observation is None: self.bmi_observation = NestedObservation()

    # Test _set_nested_attr directly
    test_model_instance = TestCalcModel()
    _set_nested_attr(test_model_instance, "height_cm", 175.0)
    assert test_model_instance.height_cm == 175.0, "Direct _set_nested_attr failed"

    # Ensure bmi_observation is initialized before setting nested attribute
    if test_model_instance.bmi_observation is None: # Should have been handled by __post_init__
        test_model_instance.bmi_observation = NestedObservation()

    _set_nested_attr(test_model_instance, "bmi_observation.unit", "kg/m2")
    assert test_model_instance.bmi_observation is not None, "bmi_observation should be initialized by __post_init__"
    assert test_model_instance.bmi_observation.unit == "kg/m2", "Nested _set_nested_attr for unit failed"
    logger.info("_set_nested_attr direct tests PASSED.")

    # Test 'calculate' rule
    calc_rules = [
        {
            "rule_type": "calculate",
            "calculation_name": "bmi",
            "input_mapping": [
                { "source_field": "weight_csv", "param_name": "weight_kg", "data_type": "float" },
                # Assuming height needs to be converted to meters if CSV provides cm
                # For this test, we'll assume height_m_csv is already in meters.
                { "source_field": "height_m_csv", "param_name": "height_m", "data_type": "float" }
            ],
            "output_field": "bmi_observation.value"
        }
    ]
    calc_data = [{"weight_csv": "70", "height_m_csv": "1.75"}]

    transformed_calc_models = apply_rules(calc_data, calc_rules, model_class=TestCalcModel, lookup_tables={})

    assert len(transformed_calc_models) == 1
    calc_model_out = transformed_calc_models[0]
    assert isinstance(calc_model_out, TestCalcModel)
    assert calc_model_out.bmi_observation is not None
    expected_bmi = round(70 / (1.75**2), 2)
    assert calc_model_out.bmi_observation.value == expected_bmi, f"BMI calculation incorrect. Expected {expected_bmi}, got {calc_model_out.bmi_observation.value}"

    # Test BMI with missing data (height missing)
    calc_data_missing_h = [{"weight_csv": "70"}]
    transformed_missing_h_models = apply_rules(calc_data_missing_h, calc_rules, model_class=TestCalcModel, lookup_tables={})
    assert transformed_missing_h_models[0].bmi_observation.value is None, "BMI should be None if height input is missing."

    # Test BMI with missing data (weight missing)
    calc_data_missing_w = [{"height_m_csv": "1.75"}]
    transformed_missing_w_models = apply_rules(calc_data_missing_w, calc_rules, model_class=TestCalcModel, lookup_tables={})
    assert transformed_missing_w_models[0].bmi_observation.value is None, "BMI should be None if weight input is missing."

    # Test BMI with zero height
    calc_data_zero_height = [{"weight_csv": "70", "height_m_csv": "0"}]
    transformed_zero_h_models = apply_rules(calc_data_zero_height, calc_rules, model_class=TestCalcModel, lookup_tables={})
    assert transformed_zero_h_models[0].bmi_observation.value is None, "BMI should be None if height is zero."

    # Test with non-numeric input
    calc_data_invalid_input = [{"weight_csv": "seventy", "height_m_csv": "1.75"}]
    transformed_invalid_models = apply_rules(calc_data_invalid_input, calc_rules, model_class=TestCalcModel, lookup_tables={})
    assert transformed_invalid_models[0].bmi_observation.value is None, "BMI should be None if input is non-numeric."
    assert len(transformed_invalid_models[0].errors) > 0, "Error should be logged for invalid input type for BMI calc"
    logger.info(f"Error for invalid input: {transformed_invalid_models[0].errors[0]}")


    logger.info("--- Rule Engine 'calculate' rule self-test PASSED. ---")

    # Add this new test section
    logger.info("--- Rule Engine Self-Test: Lookup with Output Mappings ---")
    test_lookup_model_rules = [
        {
            "rule_type": "lookup_value",
            "input_field": "gender_csv",
            "lookup_table_name": "gender_map_complex",
            "output_mappings": [
                {"source_key_from_lookup": "code", "target_property": "gender_code"},
                {"source_key_from_lookup": "oid", "target_property": "gender_oid"},
                {"source_key_from_lookup": "display", "target_property": "gender_display"}
            ],
            "default_on_miss": {"code": "9", "oid": "urn:oid:unknown", "display": "Unknown"}
        }
    ]
    test_lookup_data = [
        {"gender_csv": "M"}, # Expected to map
        {"gender_csv": "F"}, # Expected to map
        {"gender_csv": "X"}  # Expected to use default_on_miss
    ]
    mock_lookup_tables_complex = {
        "gender_map_complex": {
            "M": {"code": "1", "oid": "urn:oid:1.2.3.male", "display": "Male"},
            "F": {"code": "2", "oid": "urn:oid:1.2.3.female", "display": "Female"}
        }
    }
    # Combine with existing mock_lookups_er or pass separately
    # For simplicity, let's assume it can be passed as a fresh table for this test
    # In a real scenario, Orchestrator manages the full lookup table dictionary.

    # Create a combined lookup table for this test section
    current_test_lookups = {**mock_lookups_er, **mock_lookup_tables_complex}

    mapped_lookup_models = apply_rules(test_lookup_data, test_lookup_model_rules, TestLookupModel, current_test_lookups)

    assert len(mapped_lookup_models) == 3
    assert mapped_lookup_models[0].gender_code == "1"
    assert mapped_lookup_models[0].gender_oid == "urn:oid:1.2.3.male"
    assert mapped_lookup_models[0].gender_display == "Male"
    assert mapped_lookup_models[1].gender_code == "2"
    assert mapped_lookup_models[2].gender_code == "9" # Default
    assert mapped_lookup_models[2].gender_display == "Unknown"
    logger.info("Lookup with Output Mappings Test PASSED.")

    # Add this new test section
    logger.info("--- Rule Engine Self-Test: Date Formatting ---")
    test_date_format_rules = [
        {
            "rule_type": "data_type_conversion",
            "input_field": "dob_csv",
            "output_field": "birth_date_formatted",
            "conversion_type": "to_date_yyyymmdd"
        }
    ]
    test_date_data = [
        {"dob_csv": "1990/05/15"},
        {"dob_csv": "1985-12-01"},
        {"dob_csv": "20000720"} # Already correct format
    ]
    mapped_date_models = apply_rules(test_date_data, test_date_format_rules, TestLookupModel, current_test_lookups) # Reusing model and lookups

    assert len(mapped_date_models) == 3
    assert mapped_date_models[0].birth_date_formatted == "19900515"
    assert mapped_date_models[1].birth_date_formatted == "19851201"
    assert mapped_date_models[2].birth_date_formatted == "20000720"
    logger.info("Date Formatting Test PASSED.")

    # Add this new test section
    logger.info("--- Rule Engine Self-Test: Conditional Mapping ---")
    test_conditional_rules = [
        {
            "rule_type": "direct_mapping", # First map the status code
            "input_field": "status_code_csv",
            "output_field": "status_code"
        },
        {
            "rule_type": "conditional_mapping",
            "condition": {
                "input_field": "status_code", # Check the already mapped field on the model
                "operator": "equals",
                "value": "A",
                "source": "output" # Indicate to check output_target (the model)
            },
            "then_rules": [
                {"rule_type": "default_value", "output_field": "status_description", "value": "Active Status"}
            ],
            "else_rules": [
                {"rule_type": "default_value", "output_field": "status_description", "value": "Inactive or Other Status"}
            ]
        }
    ]
    test_conditional_data = [
        {"status_code_csv": "A"},
        {"status_code_csv": "I"}
    ]
    mapped_conditional_models = apply_rules(test_conditional_data, test_conditional_rules, TestLookupModel, current_test_lookups)

    assert len(mapped_conditional_models) == 2
    assert mapped_conditional_models[0].status_code == "A"
    assert mapped_conditional_models[0].status_description == "Active Status"
    assert mapped_conditional_models[1].status_code == "I"
    assert mapped_conditional_models[1].status_description == "Inactive or Other Status"
    logger.info("Conditional Mapping Test PASSED.")
