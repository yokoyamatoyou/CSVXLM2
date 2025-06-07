# -*- coding: utf-8 -*-
"""
Orchestrates the CSV to XML conversion process for all document types.
"""

import logging; import json; from typing import Dict, Any, List, Optional; import os; from lxml import etree; import zipfile; import shutil; from datetime import datetime, timezone; from pathlib import Path
import tempfile # Added import

from ..csv_parser import parse_csv, parse_csv_from_profile # CSVParsingError not used directly in this file after changes
from ..rule_engine import load_rules, apply_rules # RuleApplicationError not used directly
from ..xml_generator import (
    generate_index_xml, generate_summary_xml,
    generate_health_checkup_cda, generate_health_guidance_cda,
    generate_checkup_settlement_xml, generate_guidance_settlement_xml,
    # Import new parsing utilities
    get_claim_amount_from_cc08, get_claim_amount_from_gc08, get_subject_count_from_cda
)
from ..validator import validate_xml, XMLValidationError

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config; self.csv_profiles = config.get("csv_profiles", {})
        self.lookup_tables = config.get("lookup_tables", {}).copy()

        oid_catalog_path_from_config = config.get("oid_catalog_file")
        if oid_catalog_path_from_config:
            # Path from config.json is assumed to be relative to the project root or absolute.
            resolved_oid_path = Path(oid_catalog_path_from_config)

            if resolved_oid_path.exists():
                try:
                    with open(resolved_oid_path, "r", encoding="utf-8") as f_oid:
                        oid_data = json.load(f_oid)
                    self.lookup_tables["$oid_catalog$"] = oid_data
                    logger.info(f"Successfully loaded OID Catalog from '{resolved_oid_path}' into lookup_tables.")
                except Exception as e_oid_load:
                    logger.error(f"Failed to load or parse OID Catalog from '{resolved_oid_path}': {e_oid_load}")
            else:
                logger.warning(f"OID Catalog file specified in config ('{oid_catalog_path_from_config}') but not found at path '{resolved_oid_path}' (expected relative to project root).")
        else:
            logger.info("No 'oid_catalog_file' specified in config. OID lookups will fail if rules expect '$oid_catalog$'.")

        logger.info("Orchestrator initialized (CSV profiles and OID catalog processing attempted).")

    def _get_csv_profile(self, profile_name: str) -> Dict[str, Any]:
        # This method might be less relevant if CSV parsing for index/summary is removed,
        # but could still be used by other CSV processing methods.
        # For now, keeping it as it's used by CDA/Settlement processing.
        default_p = {"encoding": "utf-8", "delimiter": ",", "header": True} # parse_csv new defaults
        # The new parse_csv takes profile dict directly for 'source', 'delimiter', 'encoding', 'required_columns', 'skip_comments'
        # This _get_csv_profile was for the old parse_csv that took a profile *object* with more fields.
        # Let's simplify its return to be compatible with the new parse_csv_from_profile if needed,
        # or just acknowledge it's mainly for the other processors.
        # For now, the methods like process_csv_to_health_checkup_cdas will need to adapt
        # if they intend to use the new parse_csv signature or parse_csv_from_profile.
        # This subtask doesn't change those, so _get_csv_profile remains as is for them.
        effective_default = self.csv_profiles.get("default", default_p)
        return self.csv_profiles.get(profile_name, effective_default)

    def generate_aggregated_index_xml(self, data_xml_files: List[str], claims_xml_files: List[str], output_xml_path: str, xsd_file_path: str) -> bool:
        logger.info(f"Generating aggregated index.xml to {output_xml_path}")
        try:
            total_record_count = len(data_xml_files) + len(claims_xml_files)
            creation_time = datetime.now(timezone.utc).strftime("%Y%m%d") # Changed to YYYYMMDD for index.xml

            index_defaults = self.config.get("index_defaults", {})

            transformed_data = {
                "interactionType": index_defaults.get("interactionType", "1"), # Example default
                "creationTime": creation_time,
                "senderIdRootOid": index_defaults.get("senderIdRootOid"),
                "senderIdExtension": index_defaults.get("senderIdExtension"),
                "receiverIdRootOid": index_defaults.get("receiverIdRootOid"),
                "receiverIdExtension": index_defaults.get("receiverIdExtension"),
                "serviceEventType": index_defaults.get("serviceEventType", "1"), # Example default
                "totalRecordCount": str(total_record_count)
            }

            missing_required_fields = [k for k,v in transformed_data.items() if v is None and k in ["senderIdRootOid", "senderIdExtension", "receiverIdRootOid", "receiverIdExtension"]]
            if missing_required_fields:
                logger.error(f"Missing required fields for index.xml from config's index_defaults: {missing_required_fields}")
                return False

            xml_string = generate_index_xml(transformed_data)
            is_valid, errors = validate_xml(xml_string, xsd_file_path)
            if not is_valid:
                logger.error(f"Aggregated index.xml FAILED validation: {errors}")
                # Optionally save the invalid XML for debugging
                # with open(Path(output_xml_path).with_suffix(".invalid.xml"), "w", encoding="utf-8") as f_err: f_err.write(xml_string)
                return False

            Path(output_xml_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_xml_path, "w", encoding="utf-8") as f:
                f.write(xml_string)
            logger.info(f"Successfully generated and validated aggregated index.xml: {output_xml_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating aggregated index.xml: {e}", exc_info=True)
            return False

    def generate_aggregated_summary_xml(self, claims_xml_files: List[str], data_xml_files: List[str], output_xml_path: str, xsd_file_path: str) -> bool:
        logger.info(f"Generating aggregated summary.xml to {output_xml_path}")
        try:
            total_subject_count = 0
            for cda_file in data_xml_files: # data_xml_files are CDA files (HC08, HG08)
                total_subject_count += get_subject_count_from_cda(cda_file)

            total_cost_amount = 0.0
            total_payment_amount = 0.0 # Assuming payment = claim for now if not distinct
            total_claim_amount = 0.0
            total_payment_by_other_program = 0.0 # Assuming 0 for now

            for claim_file in claims_xml_files:
                # Determine if it's CC08 or GC08 by filename pattern or try parsing for specific roots
                # For now, let's assume CC08 parsing can find amounts, and GC08 has its own.
                # This part might need more robust type detection if filenames are not reliable.
                amount_cc = get_claim_amount_from_cc08(claim_file)
                if amount_cc is not None:
                    total_claim_amount += amount_cc
                    # Assuming cost and payment are same as claim for CC08 for this example
                    total_cost_amount += amount_cc
                    total_payment_amount += amount_cc
                    logger.debug(f"Processed CC08 {claim_file}, amount: {amount_cc}")
                    continue # Move to next file

                amount_gc = get_claim_amount_from_gc08(claim_file)
                if amount_gc is not None:
                    total_claim_amount += amount_gc
                    # Assuming cost and payment are same as claim for GC08
                    total_cost_amount += amount_gc
                    total_payment_amount += amount_gc
                    logger.debug(f"Processed GC08 {claim_file}, amount: {amount_gc}")

            summary_defaults = self.config.get("summary_defaults", {})
            # Amounts in JPY are typically integers (no decimals) in XML.
            # The generator expects strings for values in MO type.
            transformed_data = {
                "serviceEventTypeCode": summary_defaults.get("serviceEventTypeCode", "EVENT_CODE"), # Example
                "serviceEventTypeCodeSystem": summary_defaults.get("serviceEventTypeCodeSystem", "EVENT_CS"), # Example
                "serviceEventTypeDisplayName": summary_defaults.get("serviceEventTypeDisplayName", "Service Event"), # Example
                "totalSubjectCount_value": str(total_subject_count),
                "totalCostAmountValue": str(int(round(total_cost_amount))), # Round and convert to int, then str
                "totalCostAmount_currency": "JPY",
                "totalPaymentAmountValue": str(int(round(total_payment_amount))),
                "totalPaymentAmount_currency": "JPY",
                "totalClaimAmountValue": str(int(round(total_claim_amount))),
                "totalClaimAmount_currency": "JPY",
                "totalPaymentByOtherProgramValue": str(int(round(total_payment_by_other_program))),
                "totalPaymentByOtherProgram_currency": "JPY",
            }

            # Handle case where totalPaymentByOtherProgram is zero and shouldn't be included
            if int(round(total_payment_by_other_program)) == 0:
                del transformed_data["totalPaymentByOtherProgramValue"]
                del transformed_data["totalPaymentByOtherProgram_currency"]
                # The generate_summary_xml also checks for `totalPaymentByOtherProgramValue` presence

            xml_string = generate_summary_xml(transformed_data)
            is_valid, errors = validate_xml(xml_string, xsd_file_path)
            if not is_valid:
                logger.error(f"Aggregated summary.xml FAILED validation: {errors}")
                # with open(Path(output_xml_path).with_suffix(".invalid.xml"), "w", encoding="utf-8") as f_err: f_err.write(xml_string)
                return False

            Path(output_xml_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_xml_path, "w", encoding="utf-8") as f:
                f.write(xml_string)
            logger.info(f"Successfully generated and validated aggregated summary.xml: {output_xml_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating aggregated summary.xml: {e}", exc_info=True)
            return False

    def process_csv_to_health_checkup_cdas(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_dir: str, output_file_prefix: str = "hc_cda_", csv_profile_name: str = "health_checkup_full") -> List[str]:
        # This method and others below are not part of this subtask's changes but are kept.
        # They might need future updates if their CSV parsing relies on the old parse_csv behavior
        # or if they need to use the new parse_csv or parse_csv_from_profile.
        logger.info(f"Processing Health Checkup CDAs from {csv_file_path} using profile \"{csv_profile_name}\"")
        successful_files = []; parsed_data_rows_count = 0;
        try:
            # Adapt to use parse_csv_from_profile
            profile_params = self._get_csv_profile(csv_profile_name)
            full_profile_for_parser = {
                "source": csv_file_path,
                "delimiter": profile_params.get("delimiter", ","),
                "encoding": profile_params.get("encoding", "utf-8"),
                # "header" is implicitly handled by parse_csv discovering the header line
                "required_columns": profile_params.get("required_columns"), # Pass through if defined
                "skip_comments": profile_params.get("skip_comments", True)   # Pass through if defined
            }
            parsed_data_rows = parse_csv_from_profile(full_profile_for_parser)
            parsed_data_rows_count = len(parsed_data_rows)
            if not parsed_data_rows: logger.error(f"No data from {csv_file_path}"); return []
            rules = load_rules(rules_file_path); Path(output_xml_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Loaded {len(rules)} rules for Health Checkup CDA from: {rules_file_path}")
            for i, record_data in enumerate(parsed_data_rows):
                row_doc_id = record_data.get("doc_id", f"unk_hc_doc_{i+1}"); logger.info(f"Processing HC CDA record {i+1}/{parsed_data_rows_count}: {row_doc_id}");
                try:
                    transformed_list = apply_rules([record_data], rules, lookup_tables=self.lookup_tables)
                    if not transformed_list: logger.warning(f"No data after rules for HC CDA record {row_doc_id}."); continue
                    transformed_record = transformed_list[0]; logger.debug(f"Transformed HC CDA record {row_doc_id}: {transformed_record}")
                    cda_element = generate_health_checkup_cda(transformed_record)
                    xml_string = etree.tostring(cda_element, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")
                    is_valid, errors = validate_xml(xml_string, xsd_file_path)
                    if not is_valid:
                        logger.error(f"HC CDA for {row_doc_id} FAILED validation: {errors}");
                        invalid_out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.invalid.xml"
                        with open(invalid_out_path, "w", encoding="utf-8") as f_err: f_err.write(xml_string)
                        logger.info(f"Saved invalid HC CDA for {row_doc_id} to: {invalid_out_path}")
                        continue
                    out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.xml"
                    with open(out_path, "w", encoding="utf-8") as f: f.write(xml_string)
                    logger.info(f"Wrote HC CDA to: {out_path}"); successful_files.append(str(out_path))
                except Exception as e_rec: logger.error(f"Error on HC CDA record {row_doc_id}: {e_rec}", exc_info=True)
        except Exception as e_glob: logger.error(f"Global error in HC CDA processing: {e_glob}", exc_info=True)
        logger.info(f"HC CDA generation finished. {len(successful_files)} of {parsed_data_rows_count} files generated."); return successful_files

    def process_csv_to_health_guidance_cdas(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_dir: str, output_file_prefix: str = "hg_cda_", csv_profile_name: str = "health_guidance_full") -> List[str]:
        logger.info(f"Processing Health Guidance CDAs from {csv_file_path} using profile \"{csv_profile_name}\"")
        successful_files = []; parsed_data_rows_count = 0;
        try:
            profile_params = self._get_csv_profile(csv_profile_name)
            full_profile_for_parser = {
                "source": csv_file_path,
                "delimiter": profile_params.get("delimiter", ","),
                "encoding": profile_params.get("encoding", "utf-8"),
                "required_columns": profile_params.get("required_columns"),
                "skip_comments": profile_params.get("skip_comments", True)
            }
            parsed_data_rows = parse_csv_from_profile(full_profile_for_parser)
            parsed_data_rows_count = len(parsed_data_rows)
            if not parsed_data_rows: logger.error(f"No data from {csv_file_path}"); return []
            rules = load_rules(rules_file_path); Path(output_xml_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Loaded {len(rules)} rules for Health Guidance CDA from: {rules_file_path}")
            for i, record_data in enumerate(parsed_data_rows):
                row_doc_id = record_data.get("doc_id", f"unk_hg_doc_{i+1}"); logger.info(f"Processing HG CDA record {i+1}/{parsed_data_rows_count}: {row_doc_id}");
                try:
                    transformed_list = apply_rules([record_data], rules, lookup_tables=self.lookup_tables)
                    if not transformed_list: logger.warning(f"No data after rules for HG CDA record {row_doc_id}."); continue
                    transformed_record = transformed_list[0]; logger.debug(f"Transformed HG CDA record {row_doc_id}: {transformed_record}")
                    cda_element = generate_health_guidance_cda(transformed_record)
                    xml_string = etree.tostring(cda_element, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")
                    is_valid, errors = validate_xml(xml_string, xsd_file_path)
                    if not is_valid: logger.error(f"HG CDA for {row_doc_id} FAILED validation: {errors}"); continue
                    out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.xml"
                    with open(out_path, "w", encoding="utf-8") as f: f.write(xml_string)
                    logger.info(f"Wrote HG CDA to: {out_path}"); successful_files.append(str(out_path))
                except Exception as e_rec: logger.error(f"Error on HG CDA record {row_doc_id}: {e_rec}", exc_info=True)
        except Exception as e_glob: logger.error(f"Global error in HG CDA processing: {e_glob}", exc_info=True)
        logger.info(f"HG CDA generation finished. {len(successful_files)} of {parsed_data_rows_count} files generated."); return successful_files

    def process_csv_to_checkup_settlement_xmls(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_dir: str, output_file_prefix: str = "cs_", csv_profile_name: str = "checkup_settlement") -> List[str]:
        logger.info(f"Processing Checkup Settlements from {csv_file_path} using profile \"{csv_profile_name}\"")
        successful_files = []; parsed_data_rows_count = 0;
        try:
            profile_params = self._get_csv_profile(csv_profile_name)
            full_profile_for_parser = {
                "source": csv_file_path,
                "delimiter": profile_params.get("delimiter", ","),
                "encoding": profile_params.get("encoding", "utf-8"),
                "required_columns": profile_params.get("required_columns"),
                "skip_comments": profile_params.get("skip_comments", True)
            }
            parsed_data_rows = parse_csv_from_profile(full_profile_for_parser)
            parsed_data_rows_count = len(parsed_data_rows)
            if not parsed_data_rows: logger.error(f"No data from {csv_file_path}"); return []
            rules = load_rules(rules_file_path); Path(output_xml_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Loaded {len(rules)} rules for Checkup Settlement from: {rules_file_path}")
            for i, record_data in enumerate(parsed_data_rows):
                row_doc_id = record_data.get("doc_id", f"unk_cs_doc_{i+1}"); logger.info(f"Processing CS record {i+1}/{parsed_data_rows_count}: {row_doc_id}");
                try:
                    transformed_list = apply_rules([record_data], rules, lookup_tables=self.lookup_tables)
                    if not transformed_list: logger.warning(f"No data after rules for CS record {row_doc_id}."); continue
                    transformed_record = transformed_list[0]; logger.debug(f"Transformed CS record {row_doc_id}: {transformed_record}")
                    xml_string = generate_checkup_settlement_xml(transformed_record)
                    is_valid, errors = validate_xml(xml_string, xsd_file_path)
                    if not is_valid:
                        logger.error(f"CS XML for {row_doc_id} FAILED validation: {errors}")
                        invalid_out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.invalid.xml"
                        with open(invalid_out_path, "w", encoding="utf-8") as f_err: f_err.write(xml_string)
                        logger.info(f"Saved invalid CS XML for {row_doc_id} to: {invalid_out_path}")
                        continue
                    out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.xml"
                    with open(out_path, "w", encoding="utf-8") as f: f.write(xml_string)
                    logger.info(f"Wrote CS XML to: {out_path}"); successful_files.append(str(out_path))
                except Exception as e_rec: logger.error(f"Error on CS record {row_doc_id}: {e_rec}", exc_info=True)
        except Exception as e_glob: logger.error(f"Global error in CS processing: {e_glob}", exc_info=True)
        logger.info(f"CS XML generation finished. {len(successful_files)} of {parsed_data_rows_count} files generated."); return successful_files

    def process_csv_to_guidance_settlement_xmls(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_dir: str, output_file_prefix: str = "gs_", csv_profile_name: str = "guidance_settlement") -> List[str]:
        logger.info(f"Processing Guidance Settlements from {csv_file_path} using profile \"{csv_profile_name}\"")
        successful_files = []; parsed_data_rows_count = 0;
        try:
            profile_params = self._get_csv_profile(csv_profile_name)
            full_profile_for_parser = {
                "source": csv_file_path,
                "delimiter": profile_params.get("delimiter", ","),
                "encoding": profile_params.get("encoding", "utf-8"),
                "required_columns": profile_params.get("required_columns"),
                "skip_comments": profile_params.get("skip_comments", True)
            }
            parsed_data_rows = parse_csv_from_profile(full_profile_for_parser)
            parsed_data_rows_count = len(parsed_data_rows)
            if not parsed_data_rows: logger.error(f"No data from {csv_file_path}"); return []
            rules = load_rules(rules_file_path); Path(output_xml_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Loaded {len(rules)} rules for Guidance Settlement from: {rules_file_path}")

            # Consistent timestamp for all records in this batch, or per record?
            # dt:TS in MHLW context is often YYYYMMDD or YYYYMMDDHHMMSS. Using YYYYMMDDHHMMSSZ for precision.
            # The xml_generator self-test used strftime("%Y%m%dT%H%M%S+0000")
            # Let's use a format compatible with dt:TS which is YYYYMMDDHHMMSS (local) or with timezone.
            # For consistency with CDA effectiveTime (YYYYMMDD), maybe just YYYYMMDD for creationTime if allowed by XSD.
            # The XSD for gc08_V08.xsd has <xs:element name="creationTime" type="dt:TS"/>
            # dt:TS allows YYYYMMDD or YYYYMMDDHHMMSS[+/-ZZZZ]
            # Using a precise ISO format with UTC 'Z' for simplicity.
            current_time_iso = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S+0000")


            for i, record_data in enumerate(parsed_data_rows):
                row_doc_id = record_data.get("doc_id", f"unk_gs_doc_{i+1}"); logger.info(f"Processing GS record {i+1}/{parsed_data_rows_count}: {row_doc_id}");
                try:
                    transformed_list = apply_rules([record_data], rules, lookup_tables=self.lookup_tables)
                    if not transformed_list: logger.warning(f"No data after rules for GS record {row_doc_id}."); continue
                    transformed_record = transformed_list[0]; logger.debug(f"Transformed GS record {row_doc_id}: {transformed_record}")

                    # Add documentIdRootOid if not present from rules, using a default or from config for GS docs
                    if "documentIdRootOid" not in transformed_record and "documentId" in transformed_record: # "documentId" is the extension
                        default_gs_doc_id_root = self.config.get("document_defaults",{}).get("guidance_settlement",{}).get("documentIdRootOid", "1.2.392.200119.6.1.GC.DEFAULT") # Example placeholder
                        transformed_record["documentIdRootOid"] = default_gs_doc_id_root
                        logger.debug(f"Added default documentIdRootOid for GS record {row_doc_id}: {default_gs_doc_id_root}")

                    xml_string = generate_guidance_settlement_xml(transformed_record, current_time_iso)
                    is_valid, errors = validate_xml(xml_string, xsd_file_path)
                    if not is_valid:
                        logger.error(f"GS XML for {row_doc_id} FAILED validation: {errors}")
                        invalid_out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.invalid.xml"
                        with open(invalid_out_path, "w", encoding="utf-8") as f_err: f_err.write(xml_string)
                        logger.info(f"Saved invalid GS XML for {row_doc_id} to: {invalid_out_path}")
                        continue
                    out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.xml"
                    with open(out_path, "w", encoding="utf-8") as f: f.write(xml_string)
                    logger.info(f"Wrote GS XML to: {out_path}"); successful_files.append(str(out_path))
                except Exception as e_rec: logger.error(f"Error on GS record {row_doc_id}: {e_rec}", exc_info=True)
        except Exception as e_glob: logger.error(f"Global error in GS processing: {e_glob}", exc_info=True)
        logger.info(f"GS XML generation finished. {len(successful_files)} of {parsed_data_rows_count} files generated."); return successful_files

    def create_submission_archive(self, index_xml_path: str, summary_xml_path: str,
                                  data_xml_files: List[str], claims_xml_files: List[str],
                                  archive_base_name: str, archive_output_dir: str) -> Optional[str]:
        logger.info(f"Creating archive: {archive_base_name}.zip in {archive_output_dir}")

        xsd_source_paths_config = self.config.get("paths", {}).get("xsd_source_path_for_archive")
        xsd_source_paths: List[Path] = []

        if isinstance(xsd_source_paths_config, str):
            xsd_source_paths = [Path(xsd_source_paths_config)]
        elif isinstance(xsd_source_paths_config, list):
            xsd_source_paths = [Path(p) for p in xsd_source_paths_config]
        else:
            logger.warning("`xsd_source_path_for_archive` in config not found or not a string/list. Defaulting to 'data/xsd_schemas/' for archive XSDs.")
            xsd_source_paths = [Path("data/xsd_schemas")]

        temp_build_parent_dir = Path(archive_output_dir) / f"_temp_build_{archive_base_name}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        tmp_root = temp_build_parent_dir / archive_base_name
        final_zip = Path(archive_output_dir) / f"{archive_base_name}.zip"
        try:
            if temp_build_parent_dir.exists(): shutil.rmtree(temp_build_parent_dir)
            d_dir = tmp_root / "DATA"; d_dir.mkdir(parents=True, exist_ok=True)
            c_dir = tmp_root / "CLAIMS"; c_dir.mkdir(parents=True, exist_ok=True)
            x_dir = tmp_root / "XSD"; x_dir.mkdir(parents=True, exist_ok=True)
            xc_dir = x_dir / "coreschemas"; xc_dir.mkdir(parents=True, exist_ok=True)

            if index_xml_path and Path(index_xml_path).exists(): shutil.copy2(index_xml_path, tmp_root / "index.xml")
            else: logger.warning(f"Index XML {index_xml_path} not found for archive.")
            if summary_xml_path and Path(summary_xml_path).exists(): shutil.copy2(summary_xml_path, tmp_root / "summary.xml")
            else: logger.warning(f"Summary XML {summary_xml_path} not found for archive.")

            for p_str in data_xml_files:
                fp = Path(p_str)
                if fp.exists(): shutil.copy2(fp, d_dir / fp.name)
                else: logger.warning(f"Data file {fp} not found.")
            for p_str in claims_xml_files:
                fp = Path(p_str)
                if fp.exists(): shutil.copy2(fp, c_dir / fp.name)
                else: logger.warning(f"Claim file {fp} not found.")


            copied_xsd_files = set() # To keep track of copied XSDs and avoid redundant logging for coreschemas
            for xsd_src_path in xsd_source_paths:
                logger.info(f"Processing XSD source path for archive: {xsd_src_path}")
                if xsd_src_path.exists() and xsd_src_path.is_dir():
                    # Copy main XSDs
                    for item in xsd_src_path.iterdir():
                        if item.is_file() and item.name.lower().endswith(".xsd"):
                            target_file = x_dir / item.name
                            shutil.copy2(item, target_file)
                            copied_xsd_files.add(item.name)
                            logger.debug(f"Copied XSD: {item} to {target_file}")

                    # Copy coreschemas
                    core_schemas_dir = xsd_src_path / "coreschemas"
                    if core_schemas_dir.exists() and core_schemas_dir.is_dir():
                        for core_item in core_schemas_dir.iterdir():
                            if core_item.is_file() and core_item.name.lower().endswith(".xsd"):
                                target_core_file = xc_dir / core_item.name
                                shutil.copy2(core_item, target_core_file)
                                # No need to add to copied_xsd_files for this check, already covered if it's a main xsd
                                logger.debug(f"Copied core schema XSD: {core_item} to {target_core_file}")
                    # else: # Logging for missing coreschemas can be verbose if many paths are checked
                        # logger.debug(f"Coreschemas directory not found in {xsd_src_path}, or not a directory.")
                else:
                    logger.warning(f"XSD source directory {xsd_src_path} not found or not a directory. Skipping.")

            if not copied_xsd_files and not xc_dir.exists() or (xc_dir.exists() and not any(xc_dir.iterdir())) : # Check if anything was actually copied to XSD or XSD/coreschemas
                 logger.warning(f"No XSD files or coreschemas were copied to the archive from configured paths: {xsd_source_paths}")

            final_zip.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for r_path_obj_walk_root, _, files_in_walk_dir in os.walk(tmp_root):
                    for file_in_walk_dir in files_in_walk_dir:
                        file_abs_path = Path(r_path_obj_walk_root) / file_in_walk_dir
                        arcname = file_abs_path.relative_to(tmp_root.parent)
                        zf.write(file_abs_path, arcname=arcname)
                standard_dirs_to_ensure_in_zip = [d_dir, c_dir, x_dir, xc_dir]
                for std_dir_path in standard_dirs_to_ensure_in_zip:
                    if std_dir_path.is_dir():
                        arc_dir_name = str(std_dir_path.relative_to(tmp_root.parent)).replace(os.sep, '/') + '/'
                        try: zf.getinfo(arc_dir_name)
                        except KeyError:
                            dir_zipinfo = zipfile.ZipInfo(arc_dir_name, date_time=datetime.now().timetuple()[:6])
                            dir_zipinfo.external_attr = 0o40755 << 16
                            zf.writestr(dir_zipinfo, '')
            logger.info(f"Archive created: {final_zip}"); return str(final_zip)
        except Exception as e: logger.error(f"Error creating archive: {e}", exc_info=True); return None
        finally:
            if temp_build_parent_dir.exists():
                try: shutil.rmtree(temp_build_parent_dir); logger.debug(f"Cleaned temp dir: {temp_build_parent_dir}")
                except Exception as e_clean: logger.error(f"Error cleaning temp dir {temp_build_parent_dir}: {e_clean}")

    def verify_archive_contents(self, zip_archive_path: str) -> bool:
        logger.info(f"Verifying contents of archive: {zip_archive_path}")
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="zip_verify_")
        temp_dir_path = Path(temp_dir_obj.name)
        all_valid = True

        try:
            logger.debug(f"Extracting archive to temporary directory: {temp_dir_path}")
            with zipfile.ZipFile(zip_archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir_path)

            # Define XSD and XML file locations within the extracted archive
            extracted_xsd_base_path = temp_dir_path / Path(zip_archive_path).stem / "XSD" # Path includes archive name folder
            xml_files_to_validate = []

            archive_content_root = temp_dir_path / Path(zip_archive_path).stem

            # index.xml
            index_xml_file = archive_content_root / "index.xml"
            if index_xml_file.exists():
                xml_files_to_validate.append({"path": index_xml_file, "xsd_name": "ix08_V08.xsd", "type": "Index"})
            else:
                logger.error(f"index.xml not found in archive at expected location: {index_xml_file}")
                all_valid = False

            # summary.xml
            summary_xml_file = archive_content_root / "summary.xml"
            if summary_xml_file.exists():
                xml_files_to_validate.append({"path": summary_xml_file, "xsd_name": "su08_V08.xsd", "type": "Summary"})
            else:
                logger.error(f"summary.xml not found in archive at expected location: {summary_xml_file}")
                all_valid = False

            # Files in DATA/ directory
            data_dir = archive_content_root / "DATA"
            if data_dir.is_dir():
                for item in data_dir.iterdir():
                    if item.is_file() and item.name.lower().endswith(".xml"):
                        xsd_name = None
                        file_type = "Unknown DATA"
                        if item.name.startswith("hc_cda_"): # Health Checkup CDA
                            xsd_name = "hc08_V08.xsd"; file_type = "Health Checkup CDA"
                        elif item.name.startswith("hg_cda_"): # Health Guidance CDA
                            xsd_name = "hg08_V08.xsd"; file_type = "Health Guidance CDA"

                        if xsd_name:
                            xml_files_to_validate.append({"path": item, "xsd_name": xsd_name, "type": file_type})
                        else:
                            logger.warning(f"Could not determine XSD for DATA file: {item.name}")

            # Files in CLAIMS/ directory
            claims_dir = archive_content_root / "CLAIMS"
            if claims_dir.is_dir():
                for item in claims_dir.iterdir():
                    if item.is_file() and item.name.lower().endswith(".xml"):
                        xsd_name = None
                        file_type = "Unknown CLAIM"
                        if item.name.startswith("cs_"): # Checkup Settlement
                            xsd_name = "cc08_V08.xsd"; file_type = "Checkup Settlement"
                        elif item.name.startswith("gs_"): # Guidance Settlement
                            xsd_name = "gc08_V08.xsd"; file_type = "Guidance Settlement"

                        if xsd_name:
                            xml_files_to_validate.append({"path": item, "xsd_name": xsd_name, "type": file_type})
                        else:
                            logger.warning(f"Could not determine XSD for CLAIMS file: {item.name}")

            # Perform validation for all collected XML files
            for xml_info in xml_files_to_validate:
                xml_file_path = xml_info["path"]
                xsd_file_name = xml_info["xsd_name"]
                file_type_desc = xml_info["type"]

                xsd_path_in_archive = extracted_xsd_base_path / xsd_file_name

                if not xsd_path_in_archive.exists():
                    logger.error(f"XSD file '{xsd_file_name}' not found in archive's XSD directory ({extracted_xsd_base_path}) for {file_type_desc} '{xml_file_path.name}'. Skipping validation.")
                    all_valid = False
                    continue

                try:
                    logger.info(f"Validating {file_type_desc}: {xml_file_path.name} against {xsd_path_in_archive.name}")
                    xml_content = xml_file_path.read_text(encoding="utf-8")
                    # Assuming validate_xml can take a Path object for xsd_path directly or string path
                    is_valid, errors = validate_xml(xml_content, str(xsd_path_in_archive))
                    if is_valid:
                        logger.info(f"OK: {file_type_desc} '{xml_file_path.name}' is valid against '{xsd_path_in_archive.name}'.")
                    else:
                        all_valid = False
                        logger.error(f"FAIL: {file_type_desc} '{xml_file_path.name}' is invalid against '{xsd_path_in_archive.name}'. Errors: {errors}")
                except Exception as e:
                    all_valid = False
                    logger.error(f"Error validating {file_type_desc} '{xml_file_path.name}': {e}", exc_info=True)

            if not xml_files_to_validate and all_valid:
                logger.warning(f"No XML files were found or mapped for validation in archive {zip_archive_path}.")
                # If the archive is expected to have specific files (like index.xml, summary.xml),
                # their absence (already flagged by all_valid = False) would make this an error state.
                # If an empty valid archive is possible, this warning is fine.


        except FileNotFoundError:
            logger.error(f"Archive not found: {zip_archive_path}")
            all_valid = False
        except zipfile.BadZipFile:
            logger.error(f"Invalid or corrupted ZIP file: {zip_archive_path}")
            all_valid = False
        except Exception as e:
            logger.error(f"An unexpected error occurred during archive verification: {e}", exc_info=True)
            all_valid = False
        finally:
            logger.debug(f"Cleaning up temporary directory: {temp_dir_path}")
            temp_dir_obj.cleanup()

        if all_valid:
            logger.info(f"All XML files in archive '{zip_archive_path}' successfully validated against their XSDs from within the archive.")
        else:
            logger.error(f"One or more XML files in archive '{zip_archive_path}' failed validation or were missing.")
        return all_valid
