# -*- coding: utf-8 -*-
"""
XML Parsing Utilities to extract specific data from generated XML files.
"""
from __future__ import annotations

import logging
from typing import Optional
from lxml import etree

logger = logging.getLogger(__name__)

# Define common namespaces that might be used in XPath expressions
# These are examples and might need adjustment based on actual XML structures
NAMESPACES = {
    'mhlw': 'https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000161103.html', # Common MHLW namespace
    'hc': 'urn:MHLW:guidance:claim:HC:2021', # For HC08 (Health Checkup)
    'gc': 'urn:MHLW:guidance:claim:GC:2021', # For GC08 (Guidance Checkup)
    'cc': 'urn:MHLW:guidance:claim:CC:2021', # For CC08 (Claim Common) - placeholder if needed
    # Add other namespaces as identified from specific XML files (e.g., CDA)
    'cda': 'urn:hl7-org:v3', # Example for CDA
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
}

def _get_claim_amount(xml_path: str, xpath: str) -> Optional[float]:
    """Helper to fetch a claim amount from an XML using the given XPath."""
    try:
        tree = etree.parse(xml_path)
        amount_values = tree.xpath(xpath, namespaces=NAMESPACES)
        if amount_values:
            return float(amount_values[0])
        logger.warning(
            "Could not find claimAmount attribute in %s using XPath %s",
            xml_path,
            xpath,
        )
        return None
    except etree.XMLSyntaxError as e:
        logger.error("XMLSyntaxError parsing %s: %s", xml_path, e)
        return None
    except ValueError as e:
        logger.error("ValueError converting claim amount in %s: %s", xml_path, e)
        return None
    except Exception as e:  # pragma: no cover - unexpected errors
        logger.error("Unexpected error parsing %s: %s", xml_path, e)
        return None


def get_claim_amount_from_cc08(xml_path: str) -> Optional[float]:
    """Return the claim amount from a CC08 XML file."""
    return _get_claim_amount(
        xml_path,
        "/mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value",
    )

def get_claim_amount_from_gc08(xml_path: str) -> Optional[float]:
    """Return the claim amount from a GC08 XML file."""
    return _get_claim_amount(
        xml_path,
        "/gc:GuidanceClaimDocument/gc:settlementDetails/gc:claimAmount/@value",
    )

def get_subject_count_from_cda(xml_path: str) -> int:
    """
    Returns the subject count from a CDA XML file.
    For now, assumes each CDA file represents exactly one subject.
    Actual parsing might involve checking for a specific element if a CDA could represent multiple.
    """
    # To make this robust, one might check for the presence of a root CDA element
    # or a patient role element, but for now, the spec says "typically 1 per CDA".
    try:
        tree = etree.parse(xml_path)
        # Check for a ClinicalDocument root to ensure it's a CDA
        # This is a basic validation, not a full CDA conformance check.
        if tree.xpath("/cda:ClinicalDocument", namespaces=NAMESPACES):
            return 1
        logger.warning(f"File {xml_path} does not appear to be a valid CDA XML for subject counting.")
        return 0
    except etree.XMLSyntaxError as e:
        logger.error(f"XMLSyntaxError parsing CDA {xml_path} for subject count: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error parsing CDA {xml_path} for subject count: {e}")
        return 0


