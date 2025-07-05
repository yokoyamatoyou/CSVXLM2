# -*- coding: utf-8 -*-
"""
Rule Engine with entry_relationship_group support.
"""
import json, os, logging, re
import sys  # Required for self-test logging
from typing import List, Dict, Any, Optional
from pathlib import Path

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

def round_number(v: Any, digits: int = 0) -> Optional[float]:
    """Round numeric values according to specification.

    Parameters
    ----------
    v : Any
        The value to round. Will be converted to ``float`` if possible.
    digits : int, optional
        Number of digits after the decimal point.

    Returns
    -------
    Optional[float]
        The rounded number or ``None`` if ``v`` is ``None`` or empty.
    """
    if v is None or str(v).strip() == "":
        return None
    try:
        return round(float(str(v)), digits)
    except (ValueError, TypeError) as e:
        raise RuleApplicationError(f"Round conversion error: {v}") from e

class RuleApplicationError(Exception):
    """Raised when a rule fails to apply."""
    pass

def to_integer(v: Any) -> Optional[int]:
    """Convert ``v`` to ``int`` if possible."""
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(str(v))
    except ValueError as exc:
        raise RuleApplicationError(f"Int conversion error: {v}") from exc

def to_date_yyyymmdd(v: Any) -> Optional[str]:
    """Convert various date formats to ``YYYYMMDD``."""
    if v is None:
        return None

    s_v = str(v).strip()
    if not s_v:
        return None

    match = re.match(r"^(\d{4})[\/-]?(\d{1,2})[\/-]?(\d{1,2})$", s_v)
    if match:
        y, mo, d = match.groups()
        return f"{y}{mo.zfill(2)}{d.zfill(2)}"

    if re.match(r"^\d{8}$", s_v):
        return s_v

    raise RuleApplicationError(f"Date conversion error: {v}")

def to_boolean(v: Any) -> Optional[bool]:
    """Convert truthy/falsey strings to ``bool``."""
    if v is None:
        return None

    s_v = str(v).strip().lower()
    if s_v in ["true", "1", "yes", "y"]:
        return True
    if s_v in ["false", "0", "no", "n"]:
        return False
    if s_v == "":
        return None

    raise RuleApplicationError(f"Bool conversion error: {v}")

def load_rules(p: str) -> List[Dict[str, Any]]:
    """Load rule definitions from the given JSON file."""
    try:
        with open(p, "r", encoding="utf-8") as fp:
            rules = json.load(fp)
        if not isinstance(rules, list):
            raise ValueError("Rules file must be a JSON list.")
        return rules
    except Exception as exc:  # pragma: no cover - configuration errors
        logger.exception("Err load rules %s", p)
        raise RuleApplicationError(f"Load err: {exc}") from exc

def _evaluate_condition(
    c: Dict[str, Any],
    i_rec: Dict[str, Any],
    current_output_target: Any,
) -> bool:
    """Evaluate a conditional mapping rule."""

    field = c.get("input_field")

    # v_s is the source of the data for the condition check
    v_s = current_output_target if c.get("source") == "output" else i_rec

    a_v = None
    # Check if the source is a dictionary (like input_rec or temp dicts) or a model instance
    if isinstance(v_s, dict):
        a_v = v_s.get(field)
    else:  # Assumed to be a model instance
        a_v = getattr(v_s, field, None)

    op = c.get("operator", "equals")
    cmp_v = c.get("value")

    if op == "equals":
        return str(a_v) == str(cmp_v)
    if op == "not_equals":
        return str(a_v) != str(cmp_v)
    if op == "exists":
        return field is not None and a_v is not None
    if op == "not_exists":
        return a_v is None
    if op == "is_empty":
        return a_v is None or str(a_v).strip() == ""
    if op == "is_not_empty":
        return a_v is not None and str(a_v).strip() != ""

    logger.warning("Unknown condition operator %s", op)
    # Default False return for unhandled cases
    return False


def _apply_single_rule(
    rule: Dict[str, Any],
    i_rec: Dict[str, Any],
    output_target: Any,
    lookups: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Apply a single transformation rule to ``output_target``."""

    rt = rule.get("rule_type")
    of = rule.get("output_field")
    inf = rule.get("input_field")
    is_dict_target = isinstance(output_target, dict)

    if rt in [None, "comment"]:
        return

    # Allow lookup_value with output_mappings to not have a primary output_field
    if rt == "lookup_value" and rule.get("output_mappings"):
        pass # Proceed, specific checks for output_mappings will handle assignment
    elif not of and rt not in ["conditional_mapping", "entry_relationship_group", "split"]:
        logger.warning(f"Rule (type: {rt}) missing output_field (and not a special case like lookup_value with output_mappings, conditional_mapping, or entry_relationship_group). Rule: {rule}")
        return

    if rt == "direct_mapping":
        if not inf:
            logger.warning("Direct mapping for %s missing input_field: %s", of, rule)
            return
        if inf in i_rec:
            if is_dict_target:
                output_target[of] = i_rec[inf]
            else:
                _set_nested_attr(output_target, of, i_rec[inf])
    elif rt == "default_value":
        val = rule.get("value")
        cond_f = rule.get("input_field")
        apply_default = True
        if cond_f:
            cond_f_val = i_rec.get(cond_f)
            apply_default = cond_f_val is None or str(cond_f_val).strip() == ""
        if apply_default:
            if is_dict_target:
                output_target[of] = val
            else:
                _set_nested_attr(output_target, of, val)

        current_val_debug = output_target.get(of) if is_dict_target else getattr(output_target, of, "NOT_SET") # This getattr might fail for nested
        logger.debug(f"DEFAULT_VALUE: rule={rule}, input_field_condition='{cond_f}', value_in_input='{i_rec.get(cond_f)}', apply_default={apply_default}, output_field='{of}', value_set='{current_val_debug}'")
    elif rt == "data_type_conversion":
        conv_type = rule.get("conversion_type")
        val = i_rec.get(inf)
        converted_value = None
        if val is not None:
            if conv_type == "to_integer":
                converted_value = to_integer(val)
            elif conv_type == "to_date_yyyymmdd":
                converted_value = to_date_yyyymmdd(val)
            elif conv_type == "to_boolean":
                converted_value = to_boolean(val)
            else:
                raise RuleApplicationError(f"Unknown conversion_type: {conv_type}")
        if is_dict_target:
            output_target[of] = converted_value
        else:
            _set_nested_attr(output_target, of, converted_value)
    elif rt == "round_number":
        digits = int(rule.get("digits", 0))
        val = i_rec.get(inf)
        converted_value = None
        if val is not None and str(val).strip() != "":
            converted_value = round_number(val, digits)
        if is_dict_target:
            output_target[of] = converted_value
        else:
            _set_nested_attr(output_target, of, converted_value)
    elif rt == "map_missing_values":
        val = i_rec.get(inf)
        missing = rule.get("missing_values", [])
        mapped_val = rule.get("mapped_value")
        if val is None or str(val).strip() == "" or str(val) in missing:
            result_val = mapped_val
        else:
            result_val = val
        if is_dict_target:
            output_target[of] = result_val
        else:
            _set_nested_attr(output_target, of, result_val)
    elif rt == "lookup_value":
        if not inf:
            logger.warning("Lookup for rule missing input_field: %s", rule)
            return  # Removed 'of' as it might not be present

        key_s_v = output_target.get(inf) if is_dict_target else getattr(output_target, inf, None)
        if key_s_v is None and inf in i_rec : key_s_v = i_rec.get(inf)

        lookup_k = str(key_s_v) if key_s_v is not None else None
        tbl_n = rule.get("lookup_table_name")
        # Ensure 'of' is handled correctly or if output_mappings is present
        logger.debug(f"LOOKUP_VALUE: lookup_input_field='{inf}', key_source_value='{key_s_v}', final_lookup_key='{lookup_k}', table_name='{tbl_n}'")
        if not tbl_n:
            raise RuleApplicationError(f"Lookup rule missing table_name: {rule}")
        if not lookups:
            logger.error(
                "Lookup tables dictionary is missing/None for rule: %s", rule
            )
            raise RuleApplicationError("Lookup tables not provided")
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
    elif rt == "concat":
        inputs = rule.get("input_fields", [])
        delim = rule.get("delimiter", "")
        values = [str(i_rec.get(f, "")) for f in inputs]
        concatenated = delim.join(values)
        if is_dict_target:
            output_target[of] = concatenated
        else:
            _set_nested_attr(output_target, of, concatenated)
    elif rt == "split":
        if not inf:
            logger.warning(f"Split rule missing input_field: {rule}")
            return
        delim = rule.get("delimiter", "")
        parts = str(i_rec.get(inf, "")).split(delim)
        out_fields = rule.get("output_fields", [])
        for idx, field in enumerate(out_fields):
            val = parts[idx] if idx < len(parts) else None
            if is_dict_target:
                output_target[field] = val
            else:
                _set_nested_attr(output_target, field, val)
    elif rt == "create_nested_object":
        class_name = rule.get("class_name")
        if not class_name:
            logger.warning(f"create_nested_object rule missing class_name: {rule}")
            return
        try:
            from .. import models
            cls = getattr(models, class_name)
            instance = cls()
            if is_dict_target:
                output_target[of] = instance
            else:
                _set_nested_attr(output_target, of, instance)
        except Exception as e:
            logger.error(f"Failed to create instance for {class_name}: {e}")
    elif rt == "calculate":
        calculation_name = rule.get("calculation_name")
        input_mapping = rule.get("input_mapping", [])
        output_field = rule.get("output_field") # 'of' is already defined but using rule's "output_field" for clarity

        if not calculation_name or not output_field:
            logger.warning(
                "Calculate rule missing calculation_name or output_field: %s",
                rule,
            )
            return

        calc_func = CALCULATION_FUNCTIONS.get(calculation_name)
        if not calc_func:
            logger.error(
                "Calculation function '%s' not found in CALCULATION_FUNCTIONS.",
                calculation_name,
            )
            return

        kwargs = {}
        try:
            for mapping_item in input_mapping: # Renamed 'mapping' to 'mapping_item' to avoid conflict
                source_field = mapping_item.get("source_field")
                param_name = mapping_item.get("param_name")
                source_type = mapping_item.get("source_type", "input_record") # Default to input_record
                data_type = mapping_item.get("data_type")

                if not source_field or not param_name:
                    logger.warning(
                        "Invalid input_mapping item in calculate rule: %s. Skipping this parameter.",
                        mapping_item,
                    )
                    continue

                val_src_obj = i_rec if source_type == "input_record" else output_target

                raw_value = None
                if isinstance(val_src_obj, dict):
                    raw_value = val_src_obj.get(source_field)
                else:
                    raw_value = getattr(val_src_obj, source_field, None)

                if raw_value is None and "default_if_missing" in mapping_item:
                    raw_value = mapping_item["default_if_missing"]

                converted_value = raw_value
                if data_type == "float":
                    if raw_value is not None:
                        converted_value = float(str(raw_value))  # Ensure string conversion before float
                    else:
                        converted_value = None
                elif data_type == "integer":
                    if raw_value is not None:
                        converted_value = to_integer(raw_value)
                    else:
                        converted_value = None
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
    if lookup_tables is None:
        lookup_tables = {}
    if "$oid_catalog$" not in lookup_tables:
        try:
            oid_path = Path(__file__).resolve().parents[3] / "config_rules/oid_catalog.json"
            if oid_path.exists():
                with open(oid_path, "r", encoding="utf-8") as fp:
                    lookup_tables["$oid_catalog$"] = json.load(fp)
        except Exception as e:  # pragma: no cover - loading should be best effort
            logger.warning(f"Failed loading OID catalog: {e}")

    transformed_data: List[IntermediateRecord] = []
    for rec_idx, input_rec in enumerate(data):
        model_instance = model_class()
        if isinstance(model_instance, IntermediateRecord):
            model_instance.raw_input_data = input_rec.copy()
        else:
            logger.warning(f"Model class {model_class.__name__} does not inherit from IntermediateRecord. raw_input_data and errors fields might be unavailable.")

        for rule_idx, rule_def in enumerate(rules):
            try:
                # Apply the rule directly; _apply_single_rule handles the specifics
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

