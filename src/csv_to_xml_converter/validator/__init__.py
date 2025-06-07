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

