import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from lxml import etree

from ..csv_parser import parse_csv_from_profile
from ..rule_engine import load_rules, apply_rules
from ..models import (
    HealthCheckupRecord,
    HealthGuidanceRecord,
    CheckupSettlementRecord,
    GuidanceSettlementRecord,
)

logger = logging.getLogger(__name__)


class CSVProcessingMixin:
    """Utility methods for converting CSVs to various XML files."""

    csv_profiles: Dict[str, Any]
    lookup_tables: Dict[str, Any]

    def _get_csv_profile(self, profile_name: str) -> Dict[str, Any]:
        """Return CSV profile configuration for a given name."""
        default_p = {"encoding": "utf-8", "delimiter": ",", "header": True}
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

    def _transform_record(
        self, record_data: Dict[str, Any], rules: List[Dict[str, Any]], model_class
    ):
        """Apply rules to a record and return the transformed model instance."""
        transformed_list = apply_rules(
            [record_data], rules, model_class, lookup_tables=self.lookup_tables
        )
        if not transformed_list:
            return None
        model_instance = transformed_list[0]
        if hasattr(model_instance, "errors") and model_instance.errors:
            logger.warning(
                "Rule application for %s resulted in errors: %s",
                model_class.__name__,
                model_instance.errors,
            )
        return model_instance

    def _generate_xml_string(self, model_instance: Any, generator_func) -> str:
        """Generate an XML string from the model instance using ``generator_func``."""
        xml_obj = generator_func(model_instance)
        if isinstance(xml_obj, etree._Element):
            return etree.tostring(
                xml_obj, pretty_print=True, xml_declaration=True, encoding="utf-8"
            ).decode("utf-8")
        return str(xml_obj)

    def _validate_xml(self, xml_string: str, xsd_file_path: str) -> tuple[bool, List[str]]:
        """Return validation result and error list for ``xml_string``."""
        from . import validate_xml  # patched in tests via orchestrator module
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
                logger.info(
                    "Saved invalid %s for %s to: %s", log_prefix, out_path.stem, invalid_out_path
                )
            return False
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(xml_string)
        logger.info("Wrote %s XML to: %s", log_prefix, out_path)
        return True

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
        short_prefix = output_file_prefix.split("_")[0]

        try:
            parsed_data_rows = self._load_csv_records(csv_file_path, csv_profile_name)
            parsed_data_rows_count = len(parsed_data_rows)
            if not parsed_data_rows:
                logger.error(f"No data from {csv_file_path}")
                return []

            json_out_dir = (
                self.config.get("paths", {}).get("json_output_dir")
                or self.config.get("json_output_dir")
            )
            if json_out_dir:
                Path(json_out_dir).mkdir(parents=True, exist_ok=True)
                json_path = Path(json_out_dir) / (Path(csv_file_path).stem + ".json")
            else:
                json_path = Path(csv_file_path).with_suffix(".json")
            try:
                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump(parsed_data_rows, jf, ensure_ascii=False, indent=2)
                logger.info(f"Wrote parsed records to {json_path}")
            except Exception as e_dump:
                logger.error(f"Failed to write JSON output {json_path}: {e_dump}")

            rules = load_rules(rules_file_path)
            Path(output_xml_dir).mkdir(parents=True, exist_ok=True)
            logger.info(
                f"Loaded {len(rules)} rules for {model_class.__name__} from: {rules_file_path}"
            )

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

    # Public CSV processing helpers -------------------------------------------------

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
        from . import generate_health_checkup_cda  # patched in tests
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
        from . import generate_health_guidance_cda  # patched in tests
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
        from . import generate_checkup_settlement_xml  # patched in tests
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
            from . import generate_guidance_settlement_xml  # patched in tests
            if record.document_id.extension and not record.document_id.root:
                default_gs_doc_id_root = (
                    self.config.get("document_defaults", {})
                    .get("guidance_settlement", {})
                    .get("documentIdRootOid", "1.2.392.200119.6.1.GC.DEFAULT")
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
