import re
import logging

# This is the rule_engine_code that will be replaced by the actual content
rule_engine_code = """
# -*- coding: utf-8 -*-
\"\"\"
Enhanced Rule Engine with conditional logic, lookups, and proper logging.
\"\"\"

import json
import os
import logging # Added for logging
import sys # Added for self-test logging stream
from typing import List, Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class RuleApplicationError(Exception):
    \"\"\"Custom exception for errors during rule application.\"\"\"
    pass

# --- Helper functions for data type conversion (ensure they raise errors for logger) ---
def to_integer(v: Any) -> Optional[int]:
    if v is None or str(v).strip() == "": return None
    try: return int(str(v))
    except ValueError as e: raise RuleApplicationError(f"Cannot convert \"{v}\" to integer: {e}")

def to_date_yyyymmdd(v: Any) -> Optional[str]:
    if v is None: return None
    s_v = str(v).strip()
    if s_v == "": return None
    m = re.match(r"^(\\d{4})[\\/-](\\d{1,2})[\\/-](\\d{1,2})$", s_v)
    if m: y,mo,d = m.groups(); return f"{y}{mo.zfill(2)}{d.zfill(2)}"
    if re.match(r"^\\d{8}$", s_v): return s_v
    raise RuleApplicationError(f"Cannot convert \"{v}\" to YYYYMMDD.")

def to_boolean(v: Any) -> Optional[bool]:
    if v is None: return None; s_v = str(v).strip().lower()
    if s_v in ["true", "1", "yes", "y"]: return True
    if s_v in ["false", "0", "no", "n"]: return False
    if s_v == "": return None
    raise RuleApplicationError(f"Cannot convert \"{v}\" to boolean.")

# --- Main Rule Engine Functions ---
def load_rules(rules_file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(rules_file_path, "r", encoding="utf-8") as f: rules = json.load(f)
        if not isinstance(rules, list):
            raise ValueError("Rules file must be a JSON list.")
        return rules
    except Exception as e:
        logger.exception(f"Critical error loading rules from {rules_file_path}")
        raise RuleApplicationError(f"Error loading rules from {rules_file_path}: {e}")

def _evaluate_condition(condition_def: Dict[str, Any], input_record: Dict[str, Any], current_output_record: Dict[str, Any]) -> bool:
    cond_input_field = condition_def.get("input_field")
    value_source = current_output_record if condition_def.get("source", "input") == "output" else input_record
    actual_value = value_source.get(cond_input_field)
    operator = condition_def.get("operator", "equals")
    compare_value = condition_def.get("value")

    if operator == "equals": return str(actual_value) == str(compare_value)
    elif operator == "not_equals": return str(actual_value) != str(compare_value)
    elif operator == "exists": return actual_value is not None
    elif operator == "not_exists": return actual_value is None
    elif operator == "is_empty": return actual_value is None or str(actual_value).strip() == ""
    elif operator == "is_not_empty": return actual_value is not None and str(actual_value).strip() != ""
    else:
        logger.warning(f"Unknown condition operator '{operator}' in rule: {condition_def}. Condition will evaluate to False.")
        return False

def _apply_single_rule(rule: Dict[str, Any], input_record: Dict[str, Any], output_record: Dict[str, Any], lookup_tables: Optional[Dict[str, Dict[str, Any]]] = None):
    rule_type = rule.get("rule_type")
    output_field = rule.get("output_field")
    input_field = rule.get("input_field")

    if rule_type in [None, "comment"]: return

    if not output_field and rule_type not in ["conditional_mapping"]:
        logger.warning(f"Rule (type: {rule_type}) missing output_field and is not a control rule. Rule: {rule}")
        return

    current_value = input_record.get(input_field) if input_field else None

    if rule_type == "direct_mapping":
        if not input_field: logger.warning(f"Direct mapping for '{output_field}' missing input_field in rule: {rule}"); return
        if input_field in input_record: output_record[output_field] = input_record[input_field]
    elif rule_type == "default_value":
        value = rule.get("value")
        if input_field:
            if input_record.get(input_field) is None or str(input_record.get(input_field,"")).strip() == "":
                 output_record[output_field] = value
        else:
            output_record[output_field] = value
    elif rule_type == "data_type_conversion":
        if not input_field: logger.warning(f"Data type conversion for '{output_field}' missing input_field: {rule}"); return
        conversion_type = rule.get("conversion_type")
        target_type_func_name = conversion_type
        if target_type_func_name in globals() and callable(globals()[target_type_func_name]):
            if current_value is not None:
                output_record[output_field] = globals()[target_type_func_name](current_value)
            else:
                output_record[output_field] = None
        else:
            raise RuleApplicationError(f"Unknown or invalid conversion_type: {conversion_type} in rule: {rule}")

    elif rule_type == "concatenate_fields":
        fields = rule.get("input_fields", []); sep = rule.get("separator", "")
        output_record[output_field] = sep.join([str(input_record.get(f, "")) for f in fields])
    elif rule_type == "string_slice":
        if not input_field: logger.warning(f"String slice for '{output_field}' missing input_field: {rule}"); return
        s, e = rule.get("start"), rule.get("end")
        if current_value is not None: output_record[output_field] = str(current_value)[s:e]
        else: output_record[output_field] = None
    elif rule_type == "value_format":
        if not input_field: logger.warning(f"Value format for '{output_field}' missing input_field: {rule}"); return
        l,p,a = rule.get("length"),rule.get("pad_char"," "),rule.get("align","left")
        if current_value is not None and isinstance(l,int):
            s_val=str(current_value)
            output_record[output_field]=s_val[:l] if len(s_val)>l else (s_val.rjust(l,p) if a=="right" else s_val.ljust(l,p))
        elif current_value is not None: output_record[output_field] = str(current_value)
        else: output_record[output_field] = None
    elif rule_type == "conditional_mapping":
        cond_def = rule.get("condition")
        if not cond_def: raise RuleApplicationError(f"Conditional mapping rule missing condition: {rule}")
        if _evaluate_condition(cond_def, input_record, output_record):
            for sub_r in rule.get("then_rules", []): _apply_single_rule(sub_r, input_record, output_record, lookup_tables)
        else:
            for sub_r in rule.get("else_rules", []): _apply_single_rule(sub_r, input_record, output_record, lookup_tables)
    elif rule_type == "lookup_value":
        if not input_field: logger.warning(f"Lookup for '{output_field}' missing input_field: {rule}"); return
        tbl_name = rule.get("lookup_table_name")
        if not tbl_name: raise RuleApplicationError(f"Lookup for '{output_field}' missing table_name: {rule}")
        if not lookup_tables or tbl_name not in lookup_tables:
            if "default_on_miss" in rule:
                output_record[output_field] = rule.get("default_on_miss")
                logger.warning(f"Lookup table \"{tbl_name}\" not found. Using default_on_miss for '{output_field}'.")
                return
            raise RuleApplicationError(f"Lookup table \"{tbl_name}\" not found and no default_on_miss specified.")

        key_to_lookup = str(current_value)
        output_record[output_field] = lookup_tables[tbl_name].get(key_to_lookup, rule.get("default_on_miss"))
    else:
        logger.warning(f"Unknown rule_type: '{rule_type}' in rule: {rule}")

def apply_rules(data: List[Dict[str, Any]], rules: List[Dict[str, Any]], lookup_tables: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    transformed_data = []
    for rec_idx, input_rec in enumerate(data):
        out_rec = {}
        for rule_idx, rule_def in enumerate(rules):
            try:
                _apply_single_rule(rule_def, input_rec, out_rec, lookup_tables)
            except RuleApplicationError as e_rule:
                logger.error(f"RuleAppError at record {rec_idx}, rule {rule_idx} (Type:{rule_def.get('rule_type')}, Out:{rule_def.get('output_field')}): {e_rule}")
            except Exception as e_gen:
                logger.exception(f"Generic error at record {rec_idx}, rule {rule_idx} (Type:{rule_def.get('rule_type')}, Out:{rule_def.get('output_field')}): {e_gen}")
        transformed_data.append(out_rec)
    return transformed_data

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(levelname)s - %(name)s - %(message)s")
    logger.info("Rule Engine Self-Test with Logging Refactor Running...")

    mock_lookup_tables = {
        "gender_map": {"M": "Male", "F": "Female"},
        "$oid_catalog$": {"sample_oid_key": "1.2.3.4.5"}
        }
    test_rules = [
        {"rule_type": "direct_mapping", "input_field": "name", "output_field": "out_name"},
        {"rule_type": "lookup_value", "input_field": "gender", "lookup_table_name": "gender_map", "output_field": "gender_full", "default_on_miss": "U"},
        {"rule_type": "lookup_value", "input_field": "oid_key", "lookup_table_name": "$oid_catalog$", "output_field": "actual_oid"},
        {"rule_type": "data_type_conversion", "input_field": "age", "output_field": "age_int", "conversion_type": "to_integer"},
        {"rule_type": "data_type_conversion", "input_field": "bad_age", "output_field": "bad_age_int", "conversion_type": "to_integer"},
        {"rule_type": "unknown_rule", "output_field": "should_not_appear"}
        ]
    test_data = [
        {"name": "Test", "gender": "M", "oid_key": "sample_oid_key", "age": "30", "bad_age": "thirty"},
        {"name": "Fail", "gender": "X", "oid_key": "missing_key", "age": "NaN", "bad_age": "forty"}
        ]

    logger.info(f"Test Data: {test_data}")
    logger.info(f"Test Rules: {test_rules}")
    logger.info(f"Lookup Tables: {mock_lookup_tables}")

    transformed = apply_rules(test_data, test_rules, mock_lookup_tables)

    print(f"Self-test transformed output: {transformed}")

    assert transformed[0]["out_name"] == "Test"
    assert transformed[0]["gender_full"] == "Male"
    assert transformed[0]["actual_oid"] == "1.2.3.4.5"
    assert transformed[0]["age_int"] == 30
    assert "bad_age_int" not in transformed[0]

    assert transformed[1]["out_name"] == "Fail"
    assert transformed[1]["gender_full"] == "U"
    assert transformed[1]["actual_oid"] is None
    assert "age_int" not in transformed[1]
    assert "bad_age_int" not in transformed[1]
    assert "should_not_appear" not in transformed[1]

    logger.info("Rule Engine Self-Test with Logging Refactor PASSED.")
"""

# Ensure logger is available for the replacement string
logger = logging.getLogger(__name__)

pattern = re.compile(
    r"(elif rule_type == \"lookup_value\":.*?)(output_record\[output_field\] = lookup_tables\[tbl_name\]\.get\(key_to_lookup, rule\.get\(\"default_on_miss\"\)\))",
    re.DOTALL
)

replacement_code = r"""\1
        # Injected detailed logging for lookup_value
        logger.debug(f"LOOKUP_VALUE: rule='{rule}', input_field='{input_field}', current_value (key_to_lookup)='{key_to_lookup}', table_name='{tbl_name}'")
        if lookup_tables and tbl_name == "$oid_catalog$" and tbl_name in lookup_tables:
            catalog_keys_sample = list(lookup_tables[tbl_name].keys())[:5] # Log only a few keys
            logger.debug(f"LOOKUP_VALUE: OID Catalog ('$oid_catalog$') sample keys: {catalog_keys_sample}. Attempting to get: '{key_to_lookup}'.")
        elif lookup_tables and tbl_name in lookup_tables:
            table_keys_sample = list(lookup_tables[tbl_name].keys())[:5]
            logger.debug(f"LOOKUP_VALUE: Lookup table '{tbl_name}' sample keys: {table_keys_sample}. Attempting to get: '{key_to_lookup}'.")
        elif not lookup_tables:
            logger.warning(f"LOOKUP_VALUE: lookup_tables dictionary is None or empty.")
        else: # lookup_tables exists but tbl_name not in it
            logger.warning(f"LOOKUP_VALUE: table_name '{tbl_name}' not found in lookup_tables. Available tables: {list(lookup_tables.keys())}")

        \2

        logger.debug(f"LOOKUP_VALUE: output_field='{output_field}', looked_up_value='{output_record.get(output_field)}'")
"""

# Read the actual rule engine file content
try:
    with open("src/csv_to_xml_converter/rule_engine/__init__.py", "r", encoding="utf-8") as f:
        rule_engine_code_actual = f.read()
except Exception as e:
    print(f"ERROR: Could not read src/csv_to_xml_converter/rule_engine/__init__.py: {e}")
    print("SCRIPT_ABORTED_READ_FAIL")
    rule_engine_code_actual = None

if rule_engine_code_actual:
    new_code, count = pattern.subn(replacement_code, rule_engine_code_actual)

    if count > 0:
        try:
            with open("src/csv_to_xml_converter/rule_engine/__init__.py", "w", encoding="utf-8") as f:
                f.write(new_code)
            print("SUCCESS: Added detailed logging to lookup_value rule in rule_engine.")
        except Exception as e:
            print(f"ERROR: Could not write to src/csv_to_xml_converter/rule_engine/__init__.py: {e}")
            print("SCRIPT_ABORTED_WRITE_FAIL")
    else:
        print("ERROR: Failed to inject logging into lookup_value. Pattern not found. Check rule_engine code structure and regex.")
        try:
            with open("src/csv_to_xml_converter/rule_engine/__init__.py", "w", encoding="utf-8") as f:
                f.write(rule_engine_code_actual)
            print("Original rule_engine code restored due to injection pattern not found.")
        except Exception as e_restore: # Corrected syntax here
             print(f"ERROR: Could not restore original rule_engine code: {e_restore}")
        print("SCRIPT_ABORTED_PATTERN_FAIL")
else:
    pass
