# -*- coding: utf-8 -*-
"""
XML Generator with entryRelationship support for CDA and restored full generators.
"""
from lxml import etree
from typing import Dict, Any, Optional, List
import os # Make sure os is imported
import sys
import uuid
import logging

logger = logging.getLogger(__name__)
logger.info(f"xml_generator/__init__.py loaded from: {os.path.abspath(__file__)}")

# Import the new parsing utilities so they are accessible via the package
from . import xml_parsing_utils
from .xml_parsing_utils import (
    get_claim_amount_from_cc08,
    get_claim_amount_from_gc08,
    get_subject_count_from_cda
)


logger = logging.getLogger(__name__)

# --- Namespaces (Consistent with successful prior states) ---
MHLW_NS_URL = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000161103.html"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
HL7_V3_NS = "urn:hl7-org:v3"
MHLW_DATATYPE_NS = "urn:MHLW:share:datatype:2021"
MHLW_GUIDANCE_CLAIM_NS = "urn:MHLW:guidance:claim:GC:2021"

NSMAP_MHLW_DEFAULT = {None: MHLW_NS_URL, "xsi": XSI_NS}
NSMAP_HL7_DEFAULT = {None: HL7_V3_NS, "xsi": XSI_NS, "dt": MHLW_NS_URL}
NSMAP_MHLW_GUIDANCE_CLAIM = {None: MHLW_GUIDANCE_CLAIM_NS, "xsi": XSI_NS, "dt": MHLW_DATATYPE_NS}

def _str_or_default(value: Any, default_str: str = "") -> str:
    return str(value) if value is not None else default_str

# --- Fully Restored MHLW DataType Helper Functions ---
def _create_ii_element(parent_el: etree._Element, el_name: str, item_data: Dict[str, Any], id_prefix: str) -> Optional[etree._Element]:
    logger.debug(f"Attempting to create II element: el_name='{el_name}', id_prefix='{id_prefix}' with data: { {k: v for k, v in item_data.items() if k.startswith(id_prefix)} }")
    root_val = item_data.get(f"{id_prefix}RootOid")
    # Fallback to check for key without "Oid" suffix for backward compatibility or rule variations
    if root_val is None:
        root_val = item_data.get(f"{id_prefix}Root")
        if root_val is not None:
            logger.debug(f"Used fallback key '{id_prefix}Root' for element '{el_name}' as '{id_prefix}RootOid' was not found.")

    extension_val = item_data.get(f"{id_prefix}Extension")
    if root_val is None and extension_val is None: return None
    ii_el = etree.SubElement(parent_el, el_name)
    if root_val is not None: ii_el.set("root", _str_or_default(root_val))
    if extension_val is not None: ii_el.set("extension", _str_or_default(extension_val))
    return ii_el

def _create_cd_element(parent_el: etree._Element, el_name: str, item_data: Dict[str, Any], cd_prefix: str) -> Optional[etree._Element]:
    code_key = f"{cd_prefix}Code" if cd_prefix else "code"
    cs_key = f"{cd_prefix}CodeSystem" if cd_prefix else "codeSystem"
    dn_key = f"{cd_prefix}DisplayName" if cd_prefix else "displayName"
    code_val = item_data.get(code_key)
    cd_el = etree.SubElement(parent_el, el_name)
    if code_val is not None: cd_el.set("code", _str_or_default(code_val))
    if item_data.get(cs_key) is not None: cd_el.set("codeSystem", _str_or_default(item_data.get(cs_key)))
    if item_data.get(dn_key) is not None: cd_el.set("displayName", _str_or_default(item_data.get(dn_key)))
    return cd_el

def _create_int_element(parent_el: etree._Element, el_name: str, item_data: Dict[str, Any], val_key_prefix: str) -> Optional[etree._Element]:
    val_key = f"{val_key_prefix}_value" if val_key_prefix else "value"
    val = item_data.get(val_key)
    if val is not None:
        int_el = etree.SubElement(parent_el, el_name); int_el.set("value", _str_or_default(val))
        return int_el
    return None

def _create_mo_element(parent_el: etree._Element, el_name: str, item_data: Dict[str, Any], val_key_prefix: str, currency_key_suffix:str = "currency", default_currency: str = "JPY") -> Optional[etree._Element]:
    val_key = f"{val_key_prefix}Value" if val_key_prefix else "value"
    currency_key = f"{val_key_prefix}{currency_key_suffix.capitalize()}" if val_key_prefix else currency_key_suffix
    val = item_data.get(val_key)
    if val is not None:
        mo_el = etree.SubElement(parent_el, el_name); mo_el.set("value", _str_or_default(val))
        mo_el.set("currency", _str_or_default(item_data.get(currency_key), default_currency))
        return mo_el
    return None

# --- Fully Restored XML Generators ---
def generate_index_xml(transformed_data: Dict[str, Any]) -> str:
    schema_loc_val = f"{MHLW_NS_URL} ix08_V08.xsd"
    root = etree.Element("index", nsmap=NSMAP_MHLW_DEFAULT)
    root.set(f"{{{XSI_NS}}}schemaLocation", schema_loc_val)
    etree.SubElement(root, "interactionType").set("code", _str_or_default(transformed_data.get("interactionType"), "1"))
    etree.SubElement(root, "creationTime").set("value", _str_or_default(transformed_data.get("creationTime")))
    sender_el = etree.SubElement(root, "sender")
    _create_ii_element(sender_el, "id", transformed_data, "senderId")
    receiver_el = etree.SubElement(root, "receiver")
    _create_ii_element(receiver_el, "id", transformed_data, "receiverId")
    etree.SubElement(root, "serviceEventType").set("code", _str_or_default(transformed_data.get("serviceEventType"), "1"))
    etree.SubElement(root, "totalRecordCount").set("value", _str_or_default(transformed_data.get("totalRecordCount"), "0"))
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")

def generate_summary_xml(transformed_data: Dict[str, Any]) -> str:
    schema_loc_val = f"{MHLW_NS_URL} su08_V08.xsd"
    root = etree.Element("summary", nsmap=NSMAP_MHLW_DEFAULT)
    root.set(f"{{{XSI_NS}}}schemaLocation", schema_loc_val)

    set_code = transformed_data.get("serviceEventTypeCode")
    if set_code is not None:
        set_el = etree.SubElement(root, "serviceEventType")
        set_el.set("code", _str_or_default(set_code))

    _create_int_element(root, "totalSubjectCount", transformed_data, "totalSubjectCount")
    _create_mo_element(root, "totalCostAmount", transformed_data, "totalCostAmount", currency_key_suffix="_currency")
    _create_mo_element(root, "totalPaymentAmount", transformed_data, "totalPaymentAmount", currency_key_suffix="_currency")
    _create_mo_element(root, "totalClaimAmount", transformed_data, "totalClaimAmount", currency_key_suffix="_currency")
    if transformed_data.get("totalPaymentByOtherProgramValue") is not None:
         _create_mo_element(root, "totalPaymentByOtherProgram", transformed_data, "totalPaymentByOtherProgram", currency_key_suffix="_currency")
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")

def _populate_cda_header(doc: etree._Element, transformed_data: Dict[str, Any], document_profile_type: Optional[str] = None):
    logger.debug(f"Entering _populate_cda_header for profile: {document_profile_type}. Data keys: {list(transformed_data.keys())}")
    try:
        _create_ii_element(doc, "typeId", transformed_data, "typeId")
        _create_ii_element(doc, "id", transformed_data, "documentId")
        _create_cd_element(doc, "code", transformed_data, "documentType")
        etree.SubElement(doc, "title").text = _str_or_default(transformed_data.get("documentTitle"))
        etree.SubElement(doc, "effectiveTime").set("value", _str_or_default(transformed_data.get("documentEffectiveTime")))
        _create_cd_element(doc, "confidentialityCode", transformed_data, "confidentiality")
        etree.SubElement(doc, "languageCode").set("code", _str_or_default(transformed_data.get("languageCode"), "ja-JP"))

        rt_el = etree.SubElement(doc, "recordTarget"); pr_el = etree.SubElement(rt_el, "patientRole")
        _create_ii_element(pr_el, "id", transformed_data, "patientIdMrn")
        if transformed_data.get("patientIdInsuranceNoRootOid") or transformed_data.get("patientIdInsuranceNoExtension"):
            _create_ii_element(pr_el, "id", transformed_data, "patientIdInsuranceNo")
        patient_el = etree.SubElement(pr_el, "patient")
        name_el = etree.SubElement(patient_el, "name")
        etree.SubElement(name_el, f"{{{MHLW_NS_URL}}}family").text = _str_or_default(transformed_data.get("patientNameFamily"))
        etree.SubElement(name_el, f"{{{MHLW_NS_URL}}}given").text = _str_or_default(transformed_data.get("patientNameGiven"))
        _create_cd_element(patient_el, "administrativeGenderCode", transformed_data, "patientGender")
        etree.SubElement(patient_el, "birthTime").set("value", _str_or_default(transformed_data.get("patientBirthTimeValue")))

        auth_el = etree.SubElement(doc, "author"); asgn_auth_el = etree.SubElement(auth_el, "assignedAuthor")
        _create_ii_element(asgn_auth_el, "id", transformed_data, "authorId")

        cust_el = etree.SubElement(doc, "custodian"); asgn_cust_el = etree.SubElement(cust_el, "assignedCustodian")
        rep_cust_org_el = etree.SubElement(asgn_cust_el, "representedCustodianOrganization")
        _create_ii_element(rep_cust_org_el, "id", transformed_data, "custodianId")

        # Moved documentationOf block to the end of header population, before exception handling # This comment is now outdated. documentationOf is after custodian.

        if document_profile_type != "HC08": # Skip documentationOf entirely for HC08
            logger.debug(f"Profile {document_profile_type}: Generating documentationOf section.")
            # --- documentationOf section START ---
            doc_of_el = etree.SubElement(doc, "documentationOf")

            if document_profile_type == "HG08":
                # For HG08, documentationOf has no typeCode as per previous findings
                pass # No typeCode attribute
            else: # For other profiles (if any in future) or a default if not HG08 (and not HC08)
                doc_of_el.set("typeCode", "DOC")

            se_el = etree.SubElement(doc_of_el, "serviceEvent")
            if document_profile_type == "HG08":
                # For HG08, serviceEvent has no classCode/moodCode as per previous findings
                pass # No classCode or moodCode attributes
            else: # For other profiles or a default (and not HC08)
                se_el.set("classCode", "ACT")
                se_el.set("moodCode", "EVN")

            # Optional: Add id to serviceEvent (still commented as per previous findings)
            # _create_ii_element(se_el, "id", transformed_data, "serviceEventId")

            se_eff_time_el = etree.SubElement(se_el, "effectiveTime")
            low_val = transformed_data.get("serviceEventEffectiveTimeLow")
            high_val = transformed_data.get("serviceEventEffectiveTimeHigh")

            if low_val and high_val and low_val == high_val:
                se_eff_time_el.set("value", _str_or_default(low_val))
            else:
                if document_profile_type == "HG08":
                    logger.debug(f"HG08 profile: Using MHLW namespace for low/high. Low: {low_val}, High: {high_val}")
                    if low_val:
                        etree.SubElement(se_eff_time_el, f"{{{MHLW_NS_URL}}}low").set("value", _str_or_default(low_val))
                    if high_val:
                        etree.SubElement(se_eff_time_el, f"{{{MHLW_NS_URL}}}high").set("value", _str_or_default(high_val))
                else: # For other profiles (e.g. future ones, or if HC08 were to include it differently)
                    logger.debug(f"Non-HG08/Non-HC08 profile: Using default namespace for low/high. Low: {low_val}, High: {high_val}")
                    if low_val:
                        etree.SubElement(se_eff_time_el, "low").set("value", _str_or_default(low_val))
                    if high_val:
                        etree.SubElement(se_eff_time_el, "high").set("value", _str_or_default(high_val))
            # --- documentationOf section END ---
        else:
            logger.debug(f"Profile {document_profile_type}: Skipping documentationOf section.")

    except Exception as e:
        logger.error(f"Error in _populate_cda_header (profile: {document_profile_type}): {e}", exc_info=True)
        raise

# --- CDA Observation Helper Functions ---
def _create_observation_pq(parent_el: etree._Element, item_data: Dict[str, Any], item_prefix: str):
    code_key=f"{item_prefix}Code" if item_prefix else "code"; val_key=f"{item_prefix}_value" if item_prefix else "value"
    if item_data.get(val_key) is None and item_data.get(code_key) is None : return
    obs_el = etree.SubElement(parent_el, "observation", classCode="OBS", moodCode="EVN")
    _create_cd_element(obs_el, "code", item_data, item_prefix)
    if item_data.get(val_key) is not None:
        val_el = etree.SubElement(obs_el, "value"); val_el.set(f"{{{XSI_NS}}}type", "dt:PQ")
        val_el.set("value", _str_or_default(item_data.get(val_key)))
        val_el.set("unit", _str_or_default(item_data.get(f"{item_prefix}_unit" if item_prefix else "unit")))

def _create_observation_cd(parent_el: etree._Element, item_data: Dict[str, Any], item_prefix: str):
    obs_code_key=f"{item_prefix}_item_code" if item_prefix else "code"; val_code_key=f"{item_prefix}_code" if item_prefix else "value_code"
    if item_data.get(val_code_key) is None and item_data.get(obs_code_key) is None: return
    obs_el = etree.SubElement(parent_el, "observation", classCode="OBS", moodCode="EVN")
    _create_cd_element(obs_el, "code", {"code":item_data.get(obs_code_key), "codeSystem":item_data.get(f"{item_prefix}_item_codeSystem" if item_prefix else "codeSystem"), "displayName":item_data.get(f"{item_prefix}_item_displayName" if item_prefix else "displayName")}, "")
    if item_data.get(val_code_key) is not None:
        val_el = etree.SubElement(obs_el, "value"); val_el.set(f"{{{XSI_NS}}}type", "dt:CD")
        _create_cd_element(val_el, "", {"code":item_data.get(val_code_key), "codeSystem":item_data.get(f"{item_prefix}_codeSystem" if item_prefix else "value_codeSystem"), "displayName":item_data.get(f"{item_prefix}_displayName" if item_prefix else "value_displayName")}, "")


def _create_observation_int(parent_el: etree._Element, item_data: Dict[str, Any], item_prefix: str):
    code_key=f"{item_prefix}_code" if item_prefix else "code"; val_key=f"{item_prefix}_value" if item_prefix else "value"
    if item_data.get(val_key) is None and item_data.get(code_key) is None : return
    obs_el = etree.SubElement(parent_el, "observation", classCode="OBS", moodCode="EVN")
    _create_cd_element(obs_el, "code", item_data, item_prefix)
    if item_data.get(val_key) is not None:
        val_el = etree.SubElement(obs_el, "value"); val_el.set(f"{{{XSI_NS}}}type", "dt:INT")
        val_el.set("value", _str_or_default(item_data.get(val_key)))

def generate_health_checkup_cda(transformed_data: Dict[str, Any]) -> etree._Element: # Merged with ER logic
    doc = etree.Element("ClinicalDocument", nsmap=NSMAP_HL7_DEFAULT)
    doc.set(f"{{{XSI_NS}}}schemaLocation", f"{HL7_V3_NS} hc08_V08.xsd {MHLW_NS_URL} coreschemas/datatypes_hcgv08.xsd")
    _populate_cda_header(doc, transformed_data, document_profile_type="HC08")
    body_comp = etree.SubElement(doc, "component", typeCode="COMP"); structured_body = etree.SubElement(body_comp, "structuredBody")

    # Assume one main section for results for now
    results_sect_comp = etree.SubElement(structured_body, "component")
    results_sect = etree.SubElement(results_sect_comp, "section")
    _create_cd_element(results_sect, "code", transformed_data, "section_Results") # Example: section_ResultsCode, section_ResultsCodeSystem etc.
    etree.SubElement(results_sect, "title").text = _str_or_default(transformed_data.get("section_ResultsTitle"), "検査結果")
    etree.SubElement(results_sect, "text").text = "特定健診の検査結果を以下に示す。"

    # Process ER groups first
    for key, value in transformed_data.items():
        if isinstance(value, list) and key.endswith("_er_group"): # Convention
            logger.debug(f"Processing ER group: {key}")
            for group_instance in value:
                parent_obs_data = group_instance.get("parent_obs_data")
                current_parent_for_er = results_sect
                if parent_obs_data:
                    master_entry_el = etree.SubElement(results_sect, "entry", typeCode="DRIV")
                    panel_obs_el = etree.SubElement(master_entry_el, "observation", classCode=_str_or_default(parent_obs_data.get("classCode"),"CLUSTER"), moodCode="EVN")
                    _create_cd_element(panel_obs_el, "code", parent_obs_data, "") # empty prefix -> direct keys
                    current_parent_for_er = panel_obs_el

                er_type_code = group_instance.get("entry_relationship_typeCode", "COMP")
                for comp_data in group_instance.get("components", []):
                    er_el = etree.SubElement(current_parent_for_er, "entryRelationship", typeCode=er_type_code)
                    comp_value_type = comp_data.get("value_type", "PQ")
                    if comp_value_type == "PQ": _create_observation_pq(er_el, comp_data, "")
                    elif comp_value_type == "CD": _create_observation_cd(er_el, comp_data, "") # Assume direct keys for CD value too
                    elif comp_value_type == "INT": _create_observation_int(er_el, comp_data, "")

    # Process standalone observations (ensure they are not already part of ER groups by checking a flag or specific keys)
    # This part needs to be robust to avoid duplicating data already processed by ER groups.
    # For now, using a simple check for common standalone items if their specific keys exist.
    if "item_height_value" in transformed_data and not any(g.get("parent_obs_data",{}).get("code") == "SOME_HEIGHT_PANEL_CODE" for g in transformed_data.get("examination_results_er_group",[])): # Example check
        entry_el = etree.SubElement(results_sect, "entry", typeCode="DRIV"); _create_observation_pq(entry_el, transformed_data, "item_height")
    if "item_weight_value" in transformed_data: # similar check
        entry_el = etree.SubElement(results_sect, "entry", typeCode="DRIV"); _create_observation_pq(entry_el, transformed_data, "item_weight")
    # ... and so on for other known single items ...

    return doc

def generate_health_guidance_cda(transformed_data: Dict[str, Any]) -> etree._Element: # Full version
    doc = etree.Element("ClinicalDocument", nsmap=NSMAP_HL7_DEFAULT)
    doc.set(f"{{{XSI_NS}}}schemaLocation", f"{HL7_V3_NS} hg08_V08.xsd {MHLW_NS_URL} coreschemas/datatypes_hcgv08.xsd")
    _populate_cda_header(doc, transformed_data, document_profile_type="HG08")
    # Simplified body for now -  needs full structure similar to HC CDA if ER groups are used here too
    body_comp = etree.SubElement(doc, "component", typeCode="COMP"); structured_body = etree.SubElement(body_comp, "structuredBody")
    common_info_sect_comp = etree.SubElement(structured_body, "component") # Example section
    common_info_sect = etree.SubElement(common_info_sect_comp, "section")
    _create_cd_element(common_info_sect, "code", transformed_data, "sectionCode_HGCommonInfo")
    return doc

def generate_checkup_settlement_xml(transformed_data: Dict[str, Any]) -> str: # Full version
    schema_loc_val = f"{MHLW_NS_URL} cc08_V08.xsd"
    root = etree.Element(f"{{{MHLW_NS_URL}}}checkupClaim", nsmap=NSMAP_MHLW_DEFAULT)
    root.set(f"{{{XSI_NS}}}schemaLocation", schema_loc_val)
    root.set("docId", _str_or_default(transformed_data.get("documentId")))
    etree.SubElement(root, f"{{{MHLW_NS_URL}}}encounter").text = _str_or_default(transformed_data.get("encounterDetails", "Checkup Encounter"))
    sp_el = etree.SubElement(root, f"{{{MHLW_NS_URL}}}subjectPerson")
    _create_ii_element(sp_el, f"{{{MHLW_NS_URL}}}patientId", transformed_data, "patientIdMrn")
    _create_ii_element(sp_el, f"{{{MHLW_NS_URL}}}checkupOrgId", transformed_data, "checkupOrgId")
    _create_ii_element(sp_el, f"{{{MHLW_NS_URL}}}insurerId", transformed_data, "insurerId")
    if transformed_data.get("copaymentTypeCode"):
        card_el = etree.SubElement(root, f"{{{MHLW_NS_URL}}}checkupCard")
        _create_cd_element(card_el, f"{{{MHLW_NS_URL}}}copaymentType", transformed_data, "copaymentType")
    settlement_el = etree.SubElement(root, f"{{{MHLW_NS_URL}}}settlement")
    _create_cd_element(settlement_el, f"{{{MHLW_NS_URL}}}claimType", transformed_data, "claimType")
    if transformed_data.get("commissionTypeCode"):
        _create_cd_element(settlement_el, f"{{{MHLW_NS_URL}}}commissionType", transformed_data, "commissionType")
    _create_int_element(settlement_el, f"{{{MHLW_NS_URL}}}totalPoints", transformed_data, "totalPoints") # Use prefix

    # Manual creation for MO-like fields in CC08 that don't allow @currency
    total_cost_val = transformed_data.get("totalCostValue")
    if total_cost_val is not None:
        tc_el = etree.SubElement(settlement_el, f"{{{MHLW_NS_URL}}}totalCost"); tc_el.set("value", _str_or_default(total_cost_val))

    copay_val = transformed_data.get("copaymentAmountValue")
    if copay_val is not None:
        cp_el = etree.SubElement(settlement_el, f"{{{MHLW_NS_URL}}}copaymentAmount"); cp_el.set("value", _str_or_default(copay_val))

    claim_val = transformed_data.get("claimAmountValue")
    if claim_val is not None:
        ca_el = etree.SubElement(settlement_el, f"{{{MHLW_NS_URL}}}claimAmount"); ca_el.set("value", _str_or_default(claim_val))

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")

def generate_guidance_settlement_xml(transformed_data: Dict[str, Any], current_time_iso: str) -> str: # Full version
    schema_loc_val = f"{MHLW_GUIDANCE_CLAIM_NS} gc08_V08.xsd {MHLW_DATATYPE_NS} datatypes_hcgv08.xsd"
    root = etree.Element(f"{{{MHLW_GUIDANCE_CLAIM_NS}}}GuidanceClaimDocument", nsmap=NSMAP_MHLW_GUIDANCE_CLAIM)
    root.set(f"{{{XSI_NS}}}schemaLocation", schema_loc_val)
    _create_ii_element(root, "documentId", transformed_data, "documentId")
    etree.SubElement(root, "creationTime").set("value", current_time_iso)
    author_inst_el = etree.SubElement(root, "authorInstitution")
    _create_ii_element(author_inst_el, f"{{{MHLW_DATATYPE_NS}}}id", transformed_data, "guidanceOrgId")
    patient_el = etree.SubElement(root, "patient")
    _create_ii_element(patient_el, "id", transformed_data, "patientIdMrn")
    insurance_el = etree.SubElement(root, "healthInsurance")
    insurer_el = etree.SubElement(insurance_el, "insurer")
    _create_ii_element(insurer_el, f"{{{MHLW_DATATYPE_NS}}}id", transformed_data, "insurerId")
    encounter_el = etree.SubElement(root, "encounter")
    guidance_org_el_in_encounter = etree.SubElement(encounter_el, "guidanceOrg")
    _create_ii_element(guidance_org_el_in_encounter, f"{{{MHLW_DATATYPE_NS}}}id", transformed_data, "guidanceOrgId")
    _create_cd_element(encounter_el, "guidanceLevel", transformed_data, "guidanceLevel")
    _create_cd_element(encounter_el, "timing", transformed_data, "timing")
    hg_card_el = etree.SubElement(root, "healthGuidanceCard")
    _create_cd_element(hg_card_el, "copaymentType", transformed_data, "copaymentType")

    pc_val = transformed_data.get("pointsCompletedValue")
    pc_el = etree.SubElement(hg_card_el, "pointsCompleted")
    pc_el.set("value", _str_or_default(pc_val, "0"))

    _create_int_element(hg_card_el, "pointsIntended", transformed_data, "pointsIntended") # Use prefix
    settlement_el = etree.SubElement(root, "settlementDetails")
    _create_mo_element(settlement_el, "totalCost", transformed_data, "totalCost") # Use prefix
    _create_mo_element(settlement_el, "copaymentAmount", transformed_data, "copaymentAmount") # Use prefix
    _create_mo_element(settlement_el, "claimAmount", transformed_data, "claimAmount") # Use prefix
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")

if __name__ == "__main__":
    if not logger.hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout)
    logger.info("XML Gen Self-Test with EntryRelationship...")
    er_test_data = {
        "documentIdExtension": "ER_TEST_DOC", "documentEffectiveTime": "20230101",
        "typeIdRootOid": "2.16.840.1.113883.1.3", "typeIdExtension": "POCD_HD000040",
        "documentTypeCode": "10", "documentTypeCodeSystem": "1.2.392.200119.6.1001", "documentTypeDisplayName": "特定健診情報",
        "documentIdRootOid": "1.2.3.4.5.6.7",
        "section_ResultsCode": "RESULTS_SECTION", "section_ResultsCodeSystem": "LOCAL_SYS", "section_ResultsTitle":"検査結果セクション",
        "examination_results_er_group": [
            {
                "parent_obs_data": { "code": "PANEL_ANEMIA", "codeSystem": "LOCAL_CODES", "displayName": "貧血検査パネル", "classCode": "CLUSTER"},
                "entry_relationship_typeCode": "COMP",
                "components": [
                    {"code": "HGB", "codeSystem": "JLAC10", "displayName": "ヘモグロビン", "value": "10.5", "unit": "g/dL", "value_type": "PQ"},
                    {"code": "RBC", "codeSystem": "JLAC10", "displayName": "赤血球数", "value": "350", "unit": "x10E4/uL", "value_type": "PQ"}
                ]
            }
        ],
        "item_heightCode": "HGT_C", "item_heightCodeSystem": "SYS_H", "item_heightDisplayName": "Height",
        "item_height_value": "175", "item_height_unit":"cm"
    }
    generated_cda_er_el = generate_health_checkup_cda(er_test_data)
    generated_cda_er_xml = etree.tostring(generated_cda_er_el, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")
    print("--- CDA with EntryRelationship Group ---"); print(generated_cda_er_xml)
    assert "<observation classCode=\"CLUSTER\" moodCode=\"EVN\">" in generated_cda_er_xml, "Parent observation for panel not found or classCode wrong."
    assert "<code code=\"PANEL_ANEMIA\"" in generated_cda_er_xml, "Panel code missing."
    assert "<entryRelationship typeCode=\"COMP\">" in generated_cda_er_xml, "EntryRelationship tag missing."
    assert "<code code=\"HGB\" codeSystem=\"JLAC10\" displayName=\"ヘモグロビン\"/>" in generated_cda_er_xml
    assert "<value xsi:type=\"dt:PQ\" value=\"10.5\" unit=\"g/dL\"/>" in generated_cda_er_xml
    assert "<code code=\"RBC\" codeSystem=\"JLAC10\" displayName=\"赤血球数\"/>" in generated_cda_er_xml
    assert "<value xsi:type=\"dt:PQ\" value=\"350\" unit=\"x10E4/uL\"/>" in generated_cda_er_xml
    assert "<code code=\"HGT_C\" codeSystem=\"SYS_H\" displayName=\"Height\"/>" in generated_cda_er_xml
    logger.info("XML Generator EntryRelationship self-test PASSED.")
