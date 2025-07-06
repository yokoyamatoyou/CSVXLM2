# -*- coding: utf-8 -*-
"""
Orchestrates the CSV to XML conversion process for all document types.
"""

import json
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from lxml import etree

from ..csv_parser import parse_csv_from_profile  # CSVParsingError not used directly
from ..rule_engine import load_rules
from ..rule_engine import apply_rules  # RuleApplicationError not used directly
from ..xml_generator import generate_index_xml
from ..xml_generator import generate_summary_xml
from ..xml_generator import generate_health_checkup_cda
from ..xml_generator import generate_health_guidance_cda
from ..xml_generator import generate_checkup_settlement_xml
from ..xml_generator import generate_guidance_settlement_xml
from ..xml_generator import get_claim_amount_from_cc08
from ..xml_generator import get_claim_amount_from_gc08
from ..xml_generator import get_subject_count_from_cda
from ..validator import validate_xml
from ..validator import XMLValidationError
from ..models import (
    HealthCheckupRecord, HealthGuidanceRecord,
    CheckupSettlementRecord, GuidanceSettlementRecord,
    IndexRecord, SummaryRecord,
    IntermediateRecord # Though Rule Engine uses local if not found, Orchestrator should know it for type hints if any.
)


logger = logging.getLogger(__name__)


@dataclass
class XMLValidationTarget:
    """Represents an XML file to validate against an XSD."""

    path: Path
    xsd_name: str
    file_type: str

class Orchestrator:
    """Coordinate CSV parsing, rule application and XML generation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the orchestrator with configuration values."""
        self.config = config
        self.csv_profiles = config.get("csv_profiles", {})
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
        """Return CSV profile configuration for a given name."""
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

    def _load_csv_records(self, csv_file_path: str, csv_profile_name: str) -> List[Dict[str, Any]]:
        """Return list of CSV records using the named profile."""
        profile_params = self._get_csv_profile(csv_profile_name)
        full_profile = {
            "source": csv_file_path,
            "delimiter": profile_params.get("delimiter", ","),
            "encoding": profile_params.get("encoding", "utf-8"),
            "required_columns": profile_params.get("required_columns"),
            "skip_comments": profile_params.get("skip_comments", True),
        }
        return parse_csv_from_profile(full_profile)

    def _transform_record(self, record_data: Dict[str, Any], rules: List[Dict[str, Any]], model_class):
        """Apply rules to a record and return the transformed model instance."""
        transformed_list = apply_rules([record_data], rules, model_class, lookup_tables=self.lookup_tables)
        if not transformed_list:
            return None
        model_instance = transformed_list[0]
        if hasattr(model_instance, "errors") and model_instance.errors:
            logger.warning("Rule application for %s resulted in errors: %s", model_class.__name__, model_instance.errors)
        return model_instance

    def _generate_xml_string(self, model_instance: Any, generator_func) -> str:
        """Generate an XML string from the model instance using ``generator_func``."""
        xml_obj = generator_func(model_instance)
        if isinstance(xml_obj, etree._Element):
            return etree.tostring(xml_obj, pretty_print=True, xml_declaration=True, encoding="utf-8").decode("utf-8")
        return str(xml_obj)

    def _validate_xml(self, xml_string: str, xsd_file_path: str) -> tuple[bool, List[str]]:
        """Return validation result and error list for ``xml_string``."""
        return validate_xml(xml_string, xsd_file_path)

    def _validate_and_write_xml(
        self,
        xml_string: str,
        xsd_file_path: str,
        out_path: Path,
        log_prefix: str,
        invalid_out_path: Optional[Path] = None,
    ) -> bool:
        """Validate ``xml_string`` and write to ``out_path`` when valid."""
        is_valid, errors = self._validate_xml(xml_string, xsd_file_path)
        if not is_valid:
            logger.error("%s for %s FAILED validation: %s", log_prefix, out_path.stem, errors)
            if invalid_out_path:
                with open(invalid_out_path, "w", encoding="utf-8") as f_err:
                    f_err.write(xml_string)
                logger.info("Saved invalid %s for %s to: %s", log_prefix, out_path.stem, invalid_out_path)
            return False
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(xml_string)
        logger.info("Wrote %s XML to: %s", log_prefix, out_path)
        return True

    def generate_aggregated_index_xml(self, data_xml_files: List[str], claims_xml_files: List[str], output_xml_path: str, xsd_file_path: str, rules_file_path: Optional[str] = None) -> bool:
        """Generate index.xml using aggregation and rule based transformation."""
        logger.info(f"Generating aggregated index.xml to {output_xml_path}")
        try:
            total_record_count = len(data_xml_files) + len(claims_xml_files)
            creation_time = datetime.now(timezone.utc).strftime("%Y%m%d")

            aggregation_input = {
                "creation_date": creation_time,
                "record_count": total_record_count,
            }

            if not rules_file_path:
                rules_file_path = self.config.get("rule_files", {}).get("index_rules")

            transformed_obj = IndexRecord()
            if rules_file_path and Path(rules_file_path).exists():
                rules = load_rules(rules_file_path)
                transformed_list = apply_rules([aggregation_input], rules, model_class=IndexRecord, lookup_tables=self.lookup_tables)
                if transformed_list:
                    transformed_obj = transformed_list[0]
            else:
                transformed_obj.creationTime = aggregation_input["creation_date"]
                transformed_obj.totalRecordCount = aggregation_input["record_count"]

            missing_required_fields = [
                k
                for k in [
                    "senderIdRootOid",
                    "senderIdExtension",
                    "receiverIdRootOid",
                    "receiverIdExtension",
                ]
                if getattr(transformed_obj, k, None) is None
            ]
            if missing_required_fields:
                logger.error(f"Missing required fields for index.xml: {missing_required_fields}")
                return False

            xml_string = generate_index_xml(transformed_obj)
            is_valid, errors = self._validate_xml(xml_string, xsd_file_path)
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

    def generate_aggregated_summary_xml(self, claims_xml_files: List[str], data_xml_files: List[str], output_xml_path: str, xsd_file_path: str, rules_file_path: Optional[str] = None) -> bool:
        """Generate summary.xml from aggregated claim amounts and subject counts."""
        logger.info(f"Generating aggregated summary.xml to {output_xml_path}")
        try:
            total_subject_count = 0
            for cda_file in data_xml_files:
                total_subject_count += get_subject_count_from_cda(cda_file)

            total_cost_amount = 0.0
            total_claim_amount = 0.0

            for claim_file in claims_xml_files:
                # Determine if it's CC08 or GC08 by filename pattern or try parsing for specific roots
                # For now, let's assume CC08 parsing can find amounts, and GC08 has its own.
                # This part might need more robust type detection if filenames are not reliable.
                amount_cc = get_claim_amount_from_cc08(claim_file)
                if amount_cc is not None:
                    total_claim_amount += amount_cc
                    # Assuming cost and payment are same as claim for CC08 for this example
                    total_cost_amount += amount_cc
                    logger.debug(f"Processed CC08 {claim_file}, amount: {amount_cc}")
                    continue # Move to next file

                amount_gc = get_claim_amount_from_gc08(claim_file)
                if amount_gc is not None:
                    total_claim_amount += amount_gc
                    # Assuming cost and payment are same as claim for GC08
                    total_cost_amount += amount_gc
                    logger.debug(f"Processed GC08 {claim_file}, amount: {amount_gc}")

            if not rules_file_path:
                rules_file_path = self.config.get("rule_files", {}).get("summary_rules")

            aggregation_input = {
                "total_subjects": int(total_subject_count),
                "total_cost": int(round(total_cost_amount)),
                "total_claim": int(round(total_claim_amount)),
            }

            transformed_obj = SummaryRecord()
            if rules_file_path and Path(rules_file_path).exists():
                rules = load_rules(rules_file_path)
                transformed_list = apply_rules([aggregation_input], rules, model_class=SummaryRecord, lookup_tables=self.lookup_tables)
                if transformed_list:
                    transformed_obj = transformed_list[0]
            else:
                transformed_obj.totalSubjectCount_value = aggregation_input["total_subjects"]
                transformed_obj.totalCostAmountValue = aggregation_input["total_cost"]
                transformed_obj.totalPaymentAmountValue = aggregation_input["total_claim"]
                transformed_obj.totalClaimAmountValue = aggregation_input["total_claim"]

            xml_string = generate_summary_xml(transformed_obj)
            is_valid, errors = self._validate_xml(xml_string, xsd_file_path)
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

    def _process_csv_records(
        self,
        csv_file_path: str,
        rules_file_path: str,
        xsd_file_path: str,
        output_xml_dir: str,
        output_file_prefix: str,
        csv_profile_name: str,
        model_class,
        generator_func,
    ) -> List[str]:
        """Generic CSV to XML processing helper."""
        logger.info(
            f"Processing {model_class.__name__} records from {csv_file_path} using profile \"{csv_profile_name}\""
        )

        successful_files: List[str] = []
        parsed_data_rows_count = 0

        try:
            parsed_data_rows = self._load_csv_records(csv_file_path, csv_profile_name)
            parsed_data_rows_count = len(parsed_data_rows)
            if not parsed_data_rows:
                logger.error(f"No data from {csv_file_path}")
                return []

            rules = load_rules(rules_file_path)
            Path(output_xml_dir).mkdir(parents=True, exist_ok=True)
            logger.info(
                f"Loaded {len(rules)} rules for {model_class.__name__} from: {rules_file_path}"
            )

            short_prefix = output_file_prefix.split("_")[0]

            for i, record_data in enumerate(parsed_data_rows):
                row_doc_id = record_data.get("doc_id", f"unk_{short_prefix}_doc_{i+1}")
                logger.info(
                    f"Processing {short_prefix.upper()} record {i+1}/{parsed_data_rows_count}: {row_doc_id}"
                )
                try:
                    model_instance = self._transform_record(record_data, rules, model_class)
                    if model_instance is None:
                        logger.warning(
                            f"No data after rules for {short_prefix.upper()} record {row_doc_id}."
                        )
                        continue

                    xml_string = self._generate_xml_string(model_instance, generator_func)

                    invalid_path = None
                    if model_class is not HealthGuidanceRecord:
                        invalid_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.invalid.xml"

                    out_path = Path(output_xml_dir) / f"{output_file_prefix}{row_doc_id}.xml"

                    if self._validate_and_write_xml(
                        xml_string,
                        xsd_file_path,
                        out_path,
                        short_prefix.upper(),
                        invalid_out_path=invalid_path,
                    ):
                        successful_files.append(str(out_path))
                except Exception as e_rec:
                    logger.error(
                        "Error on %s record %s: %s",
                        short_prefix.upper(),
                        row_doc_id,
                        e_rec,
                        exc_info=True,
                    )
        except Exception as e_glob:
            logger.error(
                "Global error in %s processing: %s",
                short_prefix.upper(),
                e_glob,
                exc_info=True,
            )

        logger.info(
            "%s generation finished. %d of %d files generated.",
            short_prefix.upper(),
            len(successful_files),
            parsed_data_rows_count,
        )
        return successful_files

    def process_csv_to_health_checkup_cdas(
        self,
        csv_file_path: str,
        rules_file_path: str,
        xsd_file_path: str,
        output_xml_dir: str,
        output_file_prefix: str = "hc_cda_",
        csv_profile_name: str = "health_checkup_full",
    ) -> List[str]:
        """Convert a health checkup CSV into CDA XML files."""
        return self._process_csv_records(
            csv_file_path,
            rules_file_path,
            xsd_file_path,
            output_xml_dir,
            output_file_prefix,
            csv_profile_name,
            HealthCheckupRecord,
            generate_health_checkup_cda,
        )

    def process_csv_to_health_guidance_cdas(
        self,
        csv_file_path: str,
        rules_file_path: str,
        xsd_file_path: str,
        output_xml_dir: str,
        output_file_prefix: str = "hg_cda_",
        csv_profile_name: str = "health_guidance_full",
    ) -> List[str]:
        """Convert a health guidance CSV into CDA XML files."""
        return self._process_csv_records(
            csv_file_path,
            rules_file_path,
            xsd_file_path,
            output_xml_dir,
            output_file_prefix,
            csv_profile_name,
            HealthGuidanceRecord,
            generate_health_guidance_cda,
        )

    def process_csv_to_checkup_settlement_xmls(
        self,
        csv_file_path: str,
        rules_file_path: str,
        xsd_file_path: str,
        output_xml_dir: str,
        output_file_prefix: str = "cs_",
        csv_profile_name: str = "checkup_settlement",
    ) -> List[str]:
        """Convert a checkup settlement CSV into XML files."""
        return self._process_csv_records(
            csv_file_path,
            rules_file_path,
            xsd_file_path,
            output_xml_dir,
            output_file_prefix,
            csv_profile_name,
            CheckupSettlementRecord,
            generate_checkup_settlement_xml,
        )

    def process_csv_to_guidance_settlement_xmls(
        self,
        csv_file_path: str,
        rules_file_path: str,
        xsd_file_path: str,
        output_xml_dir: str,
        output_file_prefix: str = "gs_",
        csv_profile_name: str = "guidance_settlement",
    ) -> List[str]:
        """Convert a guidance settlement CSV into XML files."""
        current_time_iso = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S+0000")
        def _gen(record):
            if record.document_id.extension and not record.document_id.root:
                default_gs_doc_id_root = (
                    self.config.get("document_defaults", {}).get("guidance_settlement", {}).get("documentIdRootOid", "1.2.392.200119.6.1.GC.DEFAULT")
                )
                record.document_id.root = default_gs_doc_id_root
            return generate_guidance_settlement_xml(record, current_time_iso)
        return self._process_csv_records(
            csv_file_path,
            rules_file_path,
            xsd_file_path,
            output_xml_dir,
            output_file_prefix,
            csv_profile_name,
            GuidanceSettlementRecord,
            _gen,
        )

    def _copy_xsds_for_archive(
        self,
        xsd_source_paths: List[Path],
        xsd_dir: Path,
        coreschema_dir: Path,
    ) -> None:
        """Copy XSD files and coreschemas from configured paths into the archive."""
        for xsd_src_path in xsd_source_paths:
            logger.info(f"Processing XSD source path for archive: {xsd_src_path}")
            if xsd_src_path.exists() and xsd_src_path.is_dir():
                for item in xsd_src_path.iterdir():
                    if item.is_file() and item.name.lower().endswith(".xsd"):
                        target_file = xsd_dir / item.name
                        shutil.copy2(item, target_file)
                        logger.debug(f"Copied XSD: {item} to {target_file}")

                core_schemas_dir = xsd_src_path / "coreschemas"
                if core_schemas_dir.exists() and core_schemas_dir.is_dir():
                    for core_item in core_schemas_dir.iterdir():
                        if core_item.is_file() and core_item.name.lower().endswith(".xsd"):
                            target_core_file = coreschema_dir / core_item.name
                            shutil.copy2(core_item, target_core_file)
                            logger.debug(
                                f"Copied core schema XSD: {core_item} to {target_core_file}"
                            )
            else:
                logger.warning(
                    f"XSD source directory {xsd_src_path} not found or not a directory. Skipping."
                )

        main_xsds = list(xsd_dir.glob("*.xsd"))
        core_xsds = list(coreschema_dir.glob("*.xsd"))
        if not main_xsds and not core_xsds:
            logger.warning(
                f"No XSD files or coreschemas were copied to the archive from configured paths: {xsd_source_paths}"
            )

    def create_submission_archive(
        self,
        index_xml_path: str,
        summary_xml_path: str,
        data_xml_files: List[str],
        claims_xml_files: List[str],
        archive_base_name: str,
        archive_output_dir: str,
    ) -> Optional[str]:
        """Bundle generated XML files and XSDs into a ZIP archive."""
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

        final_zip = Path(archive_output_dir) / f"{archive_base_name}.zip"
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                tmp_root = Path(temp_dir) / archive_base_name
                d_dir = tmp_root / "DATA"
                d_dir.mkdir(parents=True, exist_ok=True)
                c_dir = tmp_root / "CLAIMS"
                c_dir.mkdir(parents=True, exist_ok=True)
                x_dir = tmp_root / "XSD"
                x_dir.mkdir(parents=True, exist_ok=True)
                xc_dir = x_dir / "coreschemas"
                xc_dir.mkdir(parents=True, exist_ok=True)

                if index_xml_path and Path(index_xml_path).exists():
                    shutil.copy2(index_xml_path, tmp_root / "index.xml")
                else:
                    logger.warning(f"Index XML {index_xml_path} not found for archive.")
                if summary_xml_path and Path(summary_xml_path).exists():
                    shutil.copy2(summary_xml_path, tmp_root / "summary.xml")
                else:
                    logger.warning(f"Summary XML {summary_xml_path} not found for archive.")

                for p_str in data_xml_files:
                    fp = Path(p_str)
                    if fp.exists():
                        shutil.copy2(fp, d_dir / fp.name)
                    else:
                        logger.warning(f"Data file {fp} not found.")
                for p_str in claims_xml_files:
                    fp = Path(p_str)
                    if fp.exists():
                        shutil.copy2(fp, c_dir / fp.name)
                    else:
                        logger.warning(f"Claim file {fp} not found.")


                self._copy_xsds_for_archive(xsd_source_paths, x_dir, xc_dir)

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
                            try:
                                zf.getinfo(arc_dir_name)
                            except KeyError:
                                dir_zipinfo = zipfile.ZipInfo(arc_dir_name, date_time=datetime.now().timetuple()[:6])
                                dir_zipinfo.external_attr = 0o40755 << 16
                                zf.writestr(dir_zipinfo, '')
                logger.info("Archive created: %s", final_zip)
                return str(final_zip)
        except Exception as e:
            logger.error("Error creating archive: %s", e, exc_info=True)
            return None

    def _collect_xml_validation_targets(
        self, archive_root: Path
    ) -> tuple[List[XMLValidationTarget], bool]:
        """Return a list of XML files with their expected XSDs and a success flag."""
        targets: List[XMLValidationTarget] = []
        all_found = True

        index_xml = archive_root / "index.xml"
        if index_xml.exists():
            targets.append(XMLValidationTarget(index_xml, "ix08_V08.xsd", "Index"))
        else:
            logger.error(f"index.xml not found in archive at expected location: {index_xml}")
            all_found = False

        summary_xml = archive_root / "summary.xml"
        if summary_xml.exists():
            targets.append(XMLValidationTarget(summary_xml, "su08_V08.xsd", "Summary"))
        else:
            logger.error(f"summary.xml not found in archive at expected location: {summary_xml}")
            all_found = False

        data_dir = archive_root / "DATA"
        if data_dir.is_dir():
            for item in data_dir.iterdir():
                if item.is_file() and item.name.lower().endswith(".xml"):
                    if item.name.startswith("hc_cda_"):
                        targets.append(XMLValidationTarget(item, "hc08_V08.xsd", "Health Checkup CDA"))
                    elif item.name.startswith("hg_cda_"):
                        targets.append(XMLValidationTarget(item, "hg08_V08.xsd", "Health Guidance CDA"))
                    else:
                        logger.warning(f"Could not determine XSD for DATA file: {item.name}")

        claims_dir = archive_root / "CLAIMS"
        if claims_dir.is_dir():
            for item in claims_dir.iterdir():
                if item.is_file() and item.name.lower().endswith(".xml"):
                    if item.name.startswith("cs_"):
                        targets.append(XMLValidationTarget(item, "cc08_V08.xsd", "Checkup Settlement"))
                    elif item.name.startswith("gs_"):
                        targets.append(XMLValidationTarget(item, "gc08_V08.xsd", "Guidance Settlement"))
                    else:
                        logger.warning(f"Could not determine XSD for CLAIMS file: {item.name}")

        return targets, all_found

    def _validate_xml_file(self, target: XMLValidationTarget, xsd_dir: Path) -> bool:
        """Validate a single XML file against the given XSD directory."""
        xsd_path = xsd_dir / target.xsd_name
        if not xsd_path.exists():
            logger.error(
                f"XSD file '{target.xsd_name}' not found in archive's XSD directory ({xsd_dir}) for {target.file_type} '{target.path.name}'. Skipping validation."
            )
            return False
        try:
            logger.info(
                f"Validating {target.file_type}: {target.path.name} against {xsd_path.name}"
            )
            xml_content = target.path.read_text(encoding="utf-8")
            is_valid, errors = self._validate_xml(xml_content, str(xsd_path))
            if is_valid:
                logger.info(
                    f"OK: {target.file_type} '{target.path.name}' is valid against '{xsd_path.name}'."
                )
                return True
            logger.error(
                f"FAIL: {target.file_type} '{target.path.name}' is invalid against '{xsd_path.name}'. Errors: {errors}"
            )
            return False
        except Exception as exc:
            logger.error(
                f"Error validating {target.file_type} '{target.path.name}': {exc}", exc_info=True
            )
            return False

    def verify_archive_contents(self, zip_archive_path: str) -> bool:
        """Validate XML files in a created archive against their bundled XSDs."""
        logger.info(f"Verifying contents of archive: {zip_archive_path}")
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="zip_verify_")
        temp_dir_path = Path(temp_dir_obj.name)
        all_valid = True

        try:
            logger.debug(f"Extracting archive to temporary directory: {temp_dir_path}")
            with zipfile.ZipFile(zip_archive_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir_path)

            archive_root = temp_dir_path / Path(zip_archive_path).stem
            xsd_dir = archive_root / "XSD"

            targets, found_required = self._collect_xml_validation_targets(archive_root)
            if not targets and found_required:
                logger.warning(
                    f"No XML files were found or mapped for validation in archive {zip_archive_path}."
                )
            if not found_required:
                all_valid = False

            for target in targets:
                if not self._validate_xml_file(target, xsd_dir):
                    all_valid = False

        except FileNotFoundError:
            logger.error(f"Archive not found: {zip_archive_path}")
            all_valid = False
        except zipfile.BadZipFile:
            logger.error(f"Invalid or corrupted ZIP file: {zip_archive_path}")
            all_valid = False
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during archive verification: {e}",
                exc_info=True,
            )
            all_valid = False
        finally:
            logger.debug(f"Cleaning up temporary directory: {temp_dir_path}")
            temp_dir_obj.cleanup()

        if all_valid:
            logger.info(
                f"All XML files in archive '{zip_archive_path}' successfully validated against their XSDs from within the archive."
            )
        else:
            logger.error(
                f"One or more XML files in archive '{zip_archive_path}' failed validation or were missing."
            )
        return all_valid
