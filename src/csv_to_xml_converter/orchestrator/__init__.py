# -*- coding: utf-8 -*-
"""
Orchestrates the CSV to XML conversion process for all document types.
"""

import logging; import json; from typing import Dict, Any, List, Optional; import os; from lxml import etree; import zipfile; import shutil; from datetime import datetime, timezone; from pathlib import Path

from ..csv_parser import parse_csv, CSVParsingError
from ..rule_engine import load_rules, apply_rules, RuleApplicationError
from ..xml_generator import generate_index_xml, generate_summary_xml, generate_health_checkup_cda, generate_health_guidance_cda, generate_checkup_settlement_xml, generate_guidance_settlement_xml
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
        default_p = {"encoding": "utf-8", "delimiter": ",", "header": True}
        effective_default = self.csv_profiles.get("default", default_p)
        return self.csv_profiles.get(profile_name, effective_default)

    def process_single_csv_to_index_xml(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_path: str, csv_profile_name: str = "index_profile") -> bool:
        logger.info(f"Processing index.xml from {csv_file_path} using profile \"{csv_profile_name}\"")
        try:
            profile = self._get_csv_profile(csv_profile_name)
            logger.debug(f"Index CSV Profile: {profile}")
            parsed_data = parse_csv(csv_file_path, profile=profile)
            if not parsed_data: logger.error(f"No data from {csv_file_path}"); return False
            record_data = parsed_data[0]
            rules = load_rules(rules_file_path)
            transformed_list = apply_rules([record_data], rules, lookup_tables=self.lookup_tables)
            if not transformed_list: logger.error("No data after rules for index.xml"); return False
            transformed_record = transformed_list[0]
            xml_string = generate_index_xml(transformed_record)
            is_valid, errors = validate_xml(xml_string, xsd_file_path)
            if not is_valid: logger.error(f"index.xml FAILED validation: {errors}"); return False
            Path(output_xml_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_xml_path, "w", encoding="utf-8") as f: f.write(xml_string)
            logger.info(f"Wrote index.xml to: {output_xml_path}")
            return True
        except Exception as e: logger.error(f"Error for index.xml: {e}", exc_info=True); return False

    def process_single_csv_to_summary_xml(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_path: str, csv_profile_name: str = "summary_profile") -> bool:
        logger.info(f"Processing summary.xml from {csv_file_path} using profile \"{csv_profile_name}\"")
        try:
            profile = self._get_csv_profile(csv_profile_name)
            logger.debug(f"Summary CSV Profile: {profile}")
            parsed_data = parse_csv(csv_file_path, profile=profile)
            if not parsed_data: logger.error(f"No data from {csv_file_path}"); return False
            record_data = parsed_data[0]
            rules = load_rules(rules_file_path)
            transformed_list = apply_rules([record_data], rules, lookup_tables=self.lookup_tables)
            if not transformed_list: logger.error("No data after rules for summary.xml"); return False
            xml_string = generate_summary_xml(transformed_list[0])
            is_valid, errors = validate_xml(xml_string, xsd_file_path)
            if not is_valid: logger.error(f"summary.xml FAILED validation: {errors}"); return False
            Path(output_xml_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_xml_path, "w", encoding="utf-8") as f: f.write(xml_string)
            logger.info(f"Wrote summary.xml to: {output_xml_path}")
            return True
        except Exception as e: logger.error(f"Error for summary.xml: {e}", exc_info=True); return False

    def process_csv_to_health_checkup_cdas(self, csv_file_path: str, rules_file_path: str, xsd_file_path: str, output_xml_dir: str, output_file_prefix: str = "hc_cda_", csv_profile_name: str = "health_checkup_full") -> List[str]:
        logger.info(f"Processing Health Checkup CDAs from {csv_file_path} using profile \"{csv_profile_name}\"")
        successful_files = []; parsed_data_rows_count = 0;
        try:
            profile = self._get_csv_profile(csv_profile_name); parsed_data_rows = parse_csv(csv_file_path, profile=profile)
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
            profile = self._get_csv_profile(csv_profile_name); parsed_data_rows = parse_csv(csv_file_path, profile=profile)
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
            profile = self._get_csv_profile(csv_profile_name); parsed_data_rows = parse_csv(csv_file_path, profile=profile)
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
            profile = self._get_csv_profile(csv_profile_name); parsed_data_rows = parse_csv(csv_file_path, profile=profile)
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
        xsd_src = Path(self.config.get("paths", {}).get("xsd_source_path_for_archive", "data/xsd_schemas"))
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

            if xsd_src.exists() and xsd_src.is_dir():
                for item in xsd_src.iterdir():
                    if item.is_file() and item.name.endswith(".xsd"): shutil.copy2(item, x_dir / item.name)
                    elif item.is_dir() and item.name == "coreschemas":
                        for ci in item.iterdir():
                            if ci.is_file() and ci.name.endswith(".xsd"): shutil.copy2(ci, xc_dir / ci.name)
            else: logger.warning(f"XSD source dir {xsd_src} not found. XSDs not added.")

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
