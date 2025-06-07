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

def get_claim_amount_from_cc08(xml_path: str) -> Optional[float]:
    """
    Parses a CC08 XML file and extracts the total claim amount.
    Placeholder: Actual XPath will depend on CC08 structure.
    """
    try:
        tree = etree.parse(xml_path)
        # XPath based on structure from generate_checkup_settlement_xml:
        # /mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value
        # Note: xpath() returns a list of attribute values (strings), so take the first one.
        amount_values = tree.xpath("/mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value", namespaces=NAMESPACES)
        if amount_values:
            return float(amount_values[0])

        logger.warning(f"Could not find claimAmount attribute in CC08 XML {xml_path} using XPath /mhlw:checkupClaim/mhlw:settlement/mhlw:claimAmount/@value")
        return None
    except etree.XMLSyntaxError as e:
        logger.error(f"XMLSyntaxError parsing CC08 {xml_path}: {e}")
        return None
    except ValueError as e:
        logger.error(f"ValueError converting claim amount in {xml_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing CC08 {xml_path}: {e}")
        return None

def get_claim_amount_from_gc08(xml_path: str) -> Optional[float]:
    """
    Parses a GC08 XML file and extracts the total claim amount.
    XPath needs to be verified with actual GC08 structure.
    """
    try:
        tree = etree.parse(xml_path)
        # XPath based on actual GC08 structure:
        # /gc:GuidanceClaimDocument/gc:settlementDetails/gc:claimAmount/@value
        amount_values = tree.xpath("/gc:GuidanceClaimDocument/gc:settlementDetails/gc:claimAmount/@value", namespaces=NAMESPACES)
        if amount_values:
            return float(amount_values[0])

        logger.warning(f"Could not find claimAmount attribute in GC08 XML {xml_path} using XPath /gc:GuidanceClaimDocument/gc:settlementDetails/gc:claimAmount/@value")
        return None
    except etree.XMLSyntaxError as e:
        logger.error(f"XMLSyntaxError parsing {xml_path}: {e}")
        return None
    except ValueError as e:
        logger.error(f"ValueError converting claim amount in {xml_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing GC08 {xml_path}: {e}")
        return None

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

if __name__ == '__main__':
    # Basic self-test (requires lxml and dummy files)
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Running self-test for xml_parsing_utils.py")

    # Create dummy XML files for testing
    # Dummy CC08
    cc08_content = """
    <root xmlns:cc="urn:MHLW:guidance:claim:CC:2021">
        <data>
            <cc:ClaimInformation>
                <cc:TotalAmount>12345.67</cc:TotalAmount>
            </cc:ClaimInformation>
        </data>
    </root>
    """
    with open("dummy_cc08.xml", "w") as f: f.write(cc08_content)

    # Dummy GC08
    gc08_content = """
    <root xmlns:gc="urn:MHLW:guidance:claim:GC:2021">
        <gc:GuidanceClaim>
            <gc:TotalClaimAmount>5000</gc:TotalClaimAmount>
        </gc:GuidanceClaim>
    </root>
    """
    with open("dummy_gc08.xml", "w") as f: f.write(gc08_content)

    # Dummy CDA
    cda_content = """
    <cda:ClinicalDocument xmlns:cda="urn:hl7-org:v3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <cda:recordTarget>
            <cda:patientRole>
                <!-- ... patient data ... -->
            </cda:patientRole>
        </cda:recordTarget>
    </cda:ClinicalDocument>
    """
    with open("dummy_cda.xml", "w") as f: f.write(cda_content)

    # Test parsing
    cc08_amount = get_claim_amount_from_cc08("dummy_cc08.xml")
    logger.info(f"CC08 Claim Amount: {cc08_amount}")
    assert cc08_amount == 12345.67

    gc08_amount = get_claim_amount_from_gc08("dummy_gc08.xml")
    logger.info(f"GC08 Claim Amount: {gc08_amount}")
    assert gc08_amount == 5000.0

    cda_subjects = get_subject_count_from_cda("dummy_cda.xml")
    logger.info(f"CDA Subject Count: {cda_subjects}")
    assert cda_subjects == 1

    cda_subjects_invalid = get_subject_count_from_cda("dummy_cc08.xml") # Not a CDA
    logger.info(f"CDA Subject Count (invalid file): {cda_subjects_invalid}")
    assert cda_subjects_invalid == 0

    logger.info("Self-test finished. Cleaning up dummy files.")
    import os
    os.remove("dummy_cc08.xml")
    os.remove("dummy_gc08.xml")
    os.remove("dummy_cda.xml")
    logger.info("xml_parsing_utils.py self-test PASSED.")
