# -*- coding: utf-8 -*-
"""
XML Parsing Utilities to extract specific data from generated XML files.
"""
from __future__ import annotations

import logging
from typing import Optional
from lxml import etree

from ..utils import parse_xml

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
    return parse_xml(xml_path)


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


def _get_claim_amount_by_xpath(xml_path: str, xpath: str) -> Optional[float]:
    """Return the claim amount for ``xml_path`` using ``xpath``."""
    tree = _parse_xml(xml_path)
    if tree is None:
        return None
    return _extract_claim_amount(tree, xpath)


def get_claim_amount_from_cc08(xml_path: str) -> Optional[float]:
    """Return the claim amount from a CC08 XML file."""
    return _get_claim_amount_by_xpath(
        xml_path,
        "/mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value",
    )

def get_claim_amount_from_gc08(xml_path: str) -> Optional[float]:
    """Return the claim amount from a GC08 XML file."""
    return _get_claim_amount_by_xpath(
        xml_path,
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
    """Return the subject count from a CDA XML file."""
    tree = parse_xml(xml_path)
    if tree is None:
        return 0

    if tree.xpath("/cda:ClinicalDocument", namespaces=NAMESPACES):
        return 1

    logger.warning(
        "File %s does not appear to be a valid CDA XML for subject counting.",
        xml_path,
    )
    return 0



__all__ = [
    'get_claim_amount_from_cc08',
    'get_claim_amount_from_gc08',
    'get_claim_amount',
    'get_subject_count_from_cda',
]
