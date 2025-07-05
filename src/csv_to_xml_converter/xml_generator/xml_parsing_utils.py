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

# Map XML root tags to the XPath where their claim amounts are located.
# This centralizes the mapping used by ``get_claim_amount``.
CLAIM_AMOUNT_XPATHS = {
    f"{{{NAMESPACES['mhlw']}}}checkupClaim":
        "/mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value",
    f"{{{NAMESPACES['gc']}}}GuidanceClaimDocument":
        "/gc:GuidanceClaimDocument/gc:settlementDetails/gc:claimAmount/@value",
}


def _parse_xml(xml_path: str) -> Optional[etree._ElementTree]:
    """Return an ``ElementTree`` for ``xml_path`` or ``None`` on error."""
    try:
        return etree.parse(xml_path)
    except etree.XMLSyntaxError as exc:
        logger.error("XMLSyntaxError parsing %s: %s", xml_path, exc)
        return None
    except Exception as exc:  # pragma: no cover - unexpected errors
        logger.error("Unexpected error parsing %s: %s", xml_path, exc)
        return None


def _extract_claim_amount(tree: etree._ElementTree, xpath: str) -> Optional[float]:
    """Return the claim amount using ``xpath`` on a parsed tree."""
    try:
        values = tree.xpath(xpath, namespaces=NAMESPACES)
        if values:
            return float(values[0])
        logger.warning("Could not find claimAmount using XPath %s", xpath)
        return None
    except ValueError as exc:
        logger.error("ValueError converting claim amount: %s", exc)
        return None


def get_claim_amount_from_cc08(xml_path: str) -> Optional[float]:
    """Return the claim amount from a CC08 XML file."""
    tree = _parse_xml(xml_path)
    if tree is None:
        return None
    return _extract_claim_amount(
        tree,
        "/mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value",
    )

def get_claim_amount_from_gc08(xml_path: str) -> Optional[float]:
    """Return the claim amount from a GC08 XML file."""
    tree = _parse_xml(xml_path)
    if tree is None:
        return None
    return _extract_claim_amount(
        tree,
        "/gc:GuidanceClaimDocument/gc:settlementDetails/gc:claimAmount/@value",
    )


def get_claim_amount(xml_path: str) -> Optional[float]:
    """Return the claim amount from either a CC08 or GC08 XML file."""
    tree = _parse_xml(xml_path)
    if tree is None:
        return None

    root_tag = tree.getroot().tag
    xpath = CLAIM_AMOUNT_XPATHS.get(root_tag)
    if not xpath:
        logger.warning("Unsupported claim XML root %s in %s", root_tag, xml_path)
        return None

    return _extract_claim_amount(tree, xpath)

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


