import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..rule_engine import load_rules, apply_rules
from ..xml_generator import (
    get_claim_amount_from_cc08,
    get_claim_amount_from_gc08,
    get_subject_count_from_cda,
)
from ..models import IndexRecord, SummaryRecord

from .csv_processing import CSVProcessingMixin

logger = logging.getLogger(__name__)


class XMLAggregationMixin(CSVProcessingMixin):
    """Methods for creating aggregated index and summary XML files."""

    def generate_aggregated_index_xml(
        self,
        data_xml_files: List[str],
        claims_xml_files: List[str],
        output_xml_path: str,
        xsd_file_path: str,
        rules_file_path: Optional[str] = None,
    ) -> bool:
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
                transformed_list = apply_rules(
                    [aggregation_input],
                    rules,
                    model_class=IndexRecord,
                    lookup_tables=self.lookup_tables,
                )
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

            from . import generate_index_xml  # patched in tests
            xml_string = generate_index_xml(transformed_obj)
            is_valid, errors = self._validate_xml(xml_string, xsd_file_path)
            if not is_valid:
                logger.error(f"Aggregated index.xml FAILED validation: {errors}")
                return False

            Path(output_xml_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_xml_path, "w", encoding="utf-8") as f:
                f.write(xml_string)
            logger.info(
                f"Successfully generated and validated aggregated index.xml: {output_xml_path}"
            )
            return True
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Error generating aggregated index.xml: {e}", exc_info=True)
            return False

    def generate_aggregated_summary_xml(
        self,
        claims_xml_files: List[str],
        data_xml_files: List[str],
        output_xml_path: str,
        xsd_file_path: str,
        rules_file_path: Optional[str] = None,
    ) -> bool:
        """Generate summary.xml from aggregated claim amounts and subject counts."""
        logger.info(f"Generating aggregated summary.xml to {output_xml_path}")
        try:
            total_subject_count = 0
            for cda_file in data_xml_files:
                total_subject_count += get_subject_count_from_cda(cda_file)

            total_cost_amount = 0.0
            total_claim_amount = 0.0

            for claim_file in claims_xml_files:
                amount_cc = get_claim_amount_from_cc08(claim_file)
                if amount_cc is not None:
                    total_claim_amount += amount_cc
                    total_cost_amount += amount_cc
                    logger.debug(f"Processed CC08 {claim_file}, amount: {amount_cc}")
                    continue

                amount_gc = get_claim_amount_from_gc08(claim_file)
                if amount_gc is not None:
                    total_claim_amount += amount_gc
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
                transformed_list = apply_rules(
                    [aggregation_input],
                    rules,
                    model_class=SummaryRecord,
                    lookup_tables=self.lookup_tables,
                )
                if transformed_list:
                    transformed_obj = transformed_list[0]
            else:
                transformed_obj.totalSubjectCount_value = aggregation_input["total_subjects"]
                transformed_obj.totalCostAmountValue = aggregation_input["total_cost"]
                transformed_obj.totalPaymentAmountValue = aggregation_input["total_claim"]
                transformed_obj.totalClaimAmountValue = aggregation_input["total_claim"]

            from . import generate_summary_xml  # patched in tests
            xml_string = generate_summary_xml(transformed_obj)
            is_valid, errors = self._validate_xml(xml_string, xsd_file_path)
            if not is_valid:
                logger.error(f"Aggregated summary.xml FAILED validation: {errors}")
                return False

            Path(output_xml_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_xml_path, "w", encoding="utf-8") as f:
                f.write(xml_string)
            logger.info(
                f"Successfully generated and validated aggregated summary.xml: {output_xml_path}"
            )
            return True
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Error generating aggregated summary.xml: {e}", exc_info=True)
            return False
