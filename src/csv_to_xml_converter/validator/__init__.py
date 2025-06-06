# -*- coding: utf-8 -*-
"""
XML Validator module using lxml.etree.XMLSchema.
"""
import logging
logger = logging.getLogger(__name__)

from lxml import etree
from typing import Tuple, List, Optional
import os
import sys

class XMLValidationError(Exception):
    """Custom exception for XML validation specific issues like XSD loading failure."""
    pass

def validate_xml(xml_string: str, xsd_file_path: str) -> Tuple[bool, List[str]]:
    error_messages = []
    try:
        if not os.path.exists(xsd_file_path):
            raise XMLValidationError(f"XSD file not found: {xsd_file_path}")
        xsd_doc = etree.parse(xsd_file_path)
        xmlschema = etree.XMLSchema(xsd_doc)
        xml_doc_tree = etree.fromstring(xml_string.encode("utf-8"))
        is_valid = xmlschema.validate(xml_doc_tree)
        if not is_valid:
            for error in xmlschema.error_log:
                error_messages.append(f"Validation Error: Line {error.line}, Column {error.column} - {error.message} (Domain: {error.domain_name}, Type: {error.type_name})")
        return is_valid, error_messages
    except etree.XMLSchemaParseError as e:
        raise XMLValidationError(f"Failed to parse XSD schema {xsd_file_path}: {e}")
    except etree.XMLSyntaxError as e:
        return False, [f"Invalid XML syntax: {e}"]
    except Exception as e:
        return False, [f"An unexpected error occurred during validation: {e}"]

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")
    logger.info("XML Validator Self-Test Running...")

    module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if module_path not in sys.path:
        sys.path.append(module_path)

    generate_index_xml_for_test = None
    try:
        from xml_generator import generate_index_xml as gen_ix_for_test
        generate_index_xml_for_test = gen_ix_for_test
    except ImportError:
        logger.warning("Failed to import generate_index_xml. Ensure xml_generator module is accessible.")
        logger.warning("Skipping self-test that depends on xml_generator.")

    # Define path to dummy XSD for index.xml (ix08_V08.xsd)
    dummy_xsd_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "xsd_schemas", "ix08_V08.xsd"))
    if not os.path.exists(dummy_xsd_path):
        dummy_xsd_path = os.path.join("data", "xsd_schemas", "ix08_V08.xsd") # Fallback for running from /app

    if not os.path.exists(dummy_xsd_path):
        logger.error(f"Critical Error: Dummy XSD file '{dummy_xsd_path}' not found. Cannot run validation tests.")
    # generate_index_xml_for_test is not actually used in this version of self-test,
    # as it was building a specific XML for the dummy ix08.
    # The original self-test for validator was focused on validating against a known simple ix08.
    # We will proceed with that original intent.
    else:
        logger.info(f"Using XSD: {dummy_xsd_path}")

        # Import specific items needed from xml_generator for constructing test XML
        try:
            from xml_generator import MHLW_NS as XML_GEN_MHLW_NS, XSI_NS as XML_GEN_XSI_NS
            from xml_generator import NSMAP_MHLW_DEFAULT as XML_GEN_NSMAP # Corrected NSMAP
        except ImportError:
            logger.error("Failed to import necessary components from xml_generator for test XML construction. Skipping tests.")
            XML_GEN_MHLW_NS, XML_GEN_XSI_NS, XML_GEN_NSMAP = None, None, None

        if XML_GEN_MHLW_NS: # Proceed only if imports were successful
            # Test Case 1: Valid XML (custom built for dummy ix08_V08.xsd)
            root = etree.Element(f"{{{XML_GEN_MHLW_NS}}}index", nsmap=XML_GEN_NSMAP)
            root.set(f"{{{XML_GEN_XSI_NS}}}schemaLocation", f"{XML_GEN_MHLW_NS} ix08_V08.xsd")
            etree.SubElement(root, f"{{{XML_GEN_MHLW_NS}}}interactionType").set("code", "1")
            etree.SubElement(root, f"{{{XML_GEN_MHLW_NS}}}creationTime").set("value", "20230101")
            s_el = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS}}}sender"); sid_el = etree.SubElement(s_el, f"{{{XML_GEN_MHLW_NS}}}id")
            sid_el.set("root", "1.2.3"); sid_el.set("extension", "sender")
            # The dummy ix08_V08.xsd was updated to include receiver and serviceEventType before totalRecordCount
            r_el = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS}}}receiver"); rid_el = etree.SubElement(r_el, f"{{{XML_GEN_MHLW_NS}}}id")
            rid_el.set("root", "1.2.4"); rid_el.set("extension", "receiver")
            se_el_ix = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS}}}serviceEventType"); se_el_ix.set("code", "1")
            trc_el = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS}}}totalRecordCount"); trc_el.set("value", "10") # countType expects positiveInteger
            valid_xml_str_for_dummy_xsd = etree.tostring(root, xml_declaration=True, encoding="utf-8").decode('utf-8')

            logger.info("--- Testing VALID XML (custom built for dummy XSD) ---")
            is_valid, errors = validate_xml(valid_xml_str_for_dummy_xsd, dummy_xsd_path)
            logger.info(f"Validation result: {'VALID' if is_valid else 'INVALID'}")
            if errors: logger.error("Errors:"); [logger.error(f"  - {err}") for err in errors]
            assert is_valid == True, "Valid XML (custom for dummy XSD) failed validation."

            # Test Case 2 & 3 (as before, using logger for output)
            # For Test Case 2 (data type error), we'll make totalRecordCount invalid
            trc_el.set("value", "ABC") # countType (positiveInteger) expects numeric
            invalid_xml_str_type_error = etree.tostring(root, xml_declaration=True, encoding="utf-8").decode('utf-8')
            logger.info("--- Testing INVALID XML (data type issues) ---")
            is_valid, errors = validate_xml(invalid_xml_str_type_error, dummy_xsd_path)
            logger.info(f"Validation result: {'VALID' if is_valid else 'INVALID'}")
            if errors: logger.error("Errors:"); [logger.error(f"  - {err}") for err in errors]
            assert is_valid == False, "Invalid XML (data type) passed validation."

            # Reset totalRecordCount for next test
            trc_el.set("value", "10")
            # For Test Case 3 (structural error), remove a required element (e.g. sender)
            # Need to re-get element before removing if it was changed
            s_el_to_remove = root.find(f"{{{XML_GEN_MHLW_NS}}}sender")
            if s_el_to_remove is not None: root.remove(s_el_to_remove)
            structurally_invalid_xml_str = etree.tostring(root, xml_declaration=True, encoding="utf-8").decode('utf-8')
            logger.info("--- Testing INVALID XML (missing element) ---")
            is_valid, errors = validate_xml(structurally_invalid_xml_str, dummy_xsd_path)
            logger.info(f"Validation result: {'VALID' if is_valid else 'INVALID'}")
            if errors: logger.error("Errors:"); [logger.error(f"  - {err}") for err in errors]
            assert is_valid == False, "Invalid XML (structural) passed validation."

    logger.info("XML Validator self-test completed.")
