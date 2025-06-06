# -*- coding: utf-8 -*-
"""
Rule Engine with entry_relationship_group support.
"""
import json, os, logging, re
import sys # Required for self-test logging
from typing import List, Dict, Any, Optional
logger = logging.getLogger(__name__)
class RuleApplicationError(Exception): pass

def to_integer(v: Any) -> Optional[int]:
    if v is None or str(v).strip() == "": return None;
    try: return int(str(v));
    except ValueError: raise RuleApplicationError(f"Int conversion error: {v}")

def to_date_yyyymmdd(v: Any) -> Optional[str]:
    if v is None: return None; s_v = str(v).strip();
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

def _evaluate_condition(c: Dict[str,Any], i_rec: Dict[str,Any], o_rec: Dict[str,Any]) -> bool:
    f=c.get("input_field"); v_s=o_rec if c.get("source")=="output" else i_rec; a_v=v_s.get(f); op=c.get("operator","equals"); cmp_v=c.get("value")
    if op=="equals": return str(a_v)==str(cmp_v)
    elif op == "not_equals": return str(a_v) != str(cmp_v)
    elif op == "exists": return f is not None and a_v is not None
    elif op == "not_exists": return a_v is None
    elif op == "is_empty": return a_v is None or str(a_v).strip() == ""
    elif op == "is_not_empty": return a_v is not None and str(a_v).strip() != ""
    else: logger.warning(f"Unknown condition operator {op}"); return False
    return False # Should not be reached if all ops are covered

def _apply_single_rule(rule: Dict[str, Any], i_rec: Dict[str, Any], o_rec: Dict[str, Any], lookups: Optional[Dict[str, Dict[str, Any]]] = None):
    rt = rule.get("rule_type"); of = rule.get("output_field"); inf = rule.get("input_field")
    if rt in [None, "comment"]: return
    # Allow 'entry_relationship_group' to proceed if 'output_field' is missing but 'output_field_anchor' is present
    if not of and rt not in ["conditional_mapping", "entry_relationship_group"]:
        logger.warning(f"Rule (type: {rt}) missing output_field and is not 'conditional_mapping' or 'entry_relationship_group'. Rule: {rule}")
        return

    if rt == "direct_mapping":
        if not inf: logger.warning(f"Direct mapping for {of} missing input_field: {rule}"); return
        if inf in i_rec: o_rec[of] = i_rec[inf]
    elif rt == "default_value":
        val = rule.get("value"); cond_f = rule.get("input_field"); apply_default = True
        if cond_f:
            cond_f_val = i_rec.get(cond_f)
            apply_default = cond_f_val is None or str(cond_f_val).strip() == ""
        if apply_default: o_rec[of] = val
        logger.debug(f"DEFAULT_VALUE: rule={rule}, input_field_condition='{cond_f}', value_in_input='{i_rec.get(cond_f)}', apply_default={apply_default}, output_field='{of}', value_set='{o_rec.get(of)}'")
    elif rt == "data_type_conversion":
        conv_type = rule.get("conversion_type"); val = i_rec.get(inf)
        if val is not None:
            if conv_type == "to_integer": o_rec[of] = to_integer(val)
            elif conv_type == "to_date_yyyymmdd": o_rec[of] = to_date_yyyymmdd(val)
            elif conv_type == "to_boolean": o_rec[of] = to_boolean(val)
            else: raise RuleApplicationError(f"Unknown conversion_type: {conv_type}")
        else: o_rec[of] = None
    elif rt == "lookup_value":
        if not inf: logger.warning(f"Lookup for \"{of}\" missing input_field: {rule}"); return
        key_s_v = o_rec.get(inf)
        if key_s_v is None and inf in i_rec : key_s_v = i_rec.get(inf)
        lookup_k = str(key_s_v) if key_s_v is not None else None
        tbl_n = rule.get("lookup_table_name")
        logger.debug(f"LOOKUP_VALUE: rule_output_field='{of}', lookup_input_field='{inf}', key_source_value_from_o_rec_or_i_rec='{key_s_v}', final_lookup_key='{lookup_k}', table_name='{tbl_n}'")
        if not tbl_n: raise RuleApplicationError(f"Lookup for \"{of}\" missing table_name: {rule}")
        if not lookups: logger.error(f"Lookup tables dictionary is missing/None for rule: {rule}"); raise RuleApplicationError("Lookup tables not provided")
        actual_table = lookups.get(tbl_n)
        if actual_table is None:
            logger.warning(f"LOOKUP_VALUE: Lookup table \"{tbl_n}\" not found in provided lookup_tables for rule: {rule}. Available tables: {list(lookups.keys())}")
            o_rec[of] = rule.get("default_on_miss")
            return
        logger.debug(f"LOOKUP_VALUE: Table \"{tbl_n}\" sample keys: {list(actual_table.keys())[:5] if actual_table else 'TABLE_IS_EMPTY_OR_NONE'}. Attempting to get key: \"{lookup_k}\".")
        result = actual_table.get(lookup_k, rule.get("default_on_miss"))
        o_rec[of] = result
        logger.debug(f"LOOKUP_VALUE: output_field='{of}', looked_up_value='{result}'")
    elif rt == "conditional_mapping":
        cond_def = rule.get("condition",{})
        if _evaluate_condition(cond_def, i_rec, o_rec):
            for sr in rule.get("then_rules",[]): _apply_single_rule(sr, i_rec, o_rec, lookups)
        else:
            for sr in rule.get("else_rules",[]): _apply_single_rule(sr, i_rec, o_rec, lookups)
    elif rt == "entry_relationship_group":
        # Use output_field_anchor for this rule type
        of_anchor = rule.get("output_field_anchor")
        if not of_anchor: raise RuleApplicationError(f"Entry relationship group rule missing output_field_anchor: {rule}")
        er_type_code = rule.get("entry_relationship_typeCode", "COMP")
        components_def = rule.get("components", [])
        processed_components = []
        for comp_def in components_def:
            comp_data_transformed = {}
            # Apply rules within component_def to i_rec to populate comp_data_transformed
            # This assumes component_def.rules is a list of rule definitions
            component_rules = comp_def.get("rules", [])
            if component_rules: # If there are specific rules for this component
                 # Create a temporary output record for this component's transformation
                temp_comp_output_rec = {}
                for sub_rule_def in component_rules:
                    _apply_single_rule(sub_rule_def, i_rec, temp_comp_output_rec, lookups)
                comp_data_transformed = temp_comp_output_rec # Use the result of these rules
            else: # Fallback to direct mapping from component_def if no sub-rules (legacy or simple case)
                comp_data_transformed["value"] = i_rec.get(comp_def.get("value_input_field"))
                comp_data_transformed["unit"] = comp_def.get("unit")
                comp_data_transformed["code"] = comp_def.get("code")
                comp_data_transformed["codeSystem"] = comp_def.get("codeSystem")
                comp_data_transformed["displayName"] = comp_def.get("displayName")
                comp_data_transformed["value_type"] = comp_def.get("value_type", "PQ")
                if comp_data_transformed["value_type"] == "CD":
                    comp_data_transformed["value_code"] = i_rec.get(comp_def.get("value_code_input_field"))
                    comp_data_transformed["value_codeSystem"] = comp_def.get("value_codeSystem")
                    comp_data_transformed["value_displayName"] = comp_def.get("value_displayName")

            processed_components.append(comp_data_transformed)

        if not of_anchor in o_rec or not isinstance(o_rec[of_anchor], list): o_rec[of_anchor] = []
        o_rec[of_anchor].append({
            "entry_relationship_typeCode": er_type_code,
            "components": processed_components
        })
    elif rt not in [None, "comment"]: logger.warning(f"Unknown rule_type: {rt} in rule {rule}")

def apply_rules(data: List[Dict[str, Any]], rules: List[Dict[str, Any]], lookup_tables: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    transformed_data = []
    for rec_idx, input_rec in enumerate(data):
        output_rec = {}
        for rule_idx, rule_def in enumerate(rules):
            try: _apply_single_rule(rule_def, input_rec, output_rec, lookup_tables)
            except Exception as e: logger.error(f"Err @ rec {rec_idx} rule {rule_idx} ({rule_def.get('rule_type')} for {rule_def.get('output_field')}): {e}", exc_info=False) # exc_info=False for cleaner logs unless needed
        transformed_data.append(output_rec)
    return transformed_data

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout)
    logger.info("Rule Engine Self-Test for entry_relationship_group...")
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
    transformed_er = apply_rules(er_data, er_rules, mock_lookups_er)

    print(f"ER Transformed: {json.dumps(transformed_er, indent=2)}")
    assert len(transformed_er[0]["anemia_panel_results"]) == 1, "Should be one ER group"
    group = transformed_er[0]["anemia_panel_results"][0]
    assert group["entry_relationship_typeCode"] == "COMP", "ER type code mismatch"
    assert len(group["components"]) == 2, "Should be two components"
    assert group["components"][0]["value"] == "12.5" and group["components"][0]["code"] == "1001-9", "HGB data mismatch"
    assert group["components"][1]["value"] == "4.5" and group["components"][1]["code"] == "1002-7", "RBC data mismatch"
    logger.info("Rule Engine entry_relationship_group self-test PASSED.")
