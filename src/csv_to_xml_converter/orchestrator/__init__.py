"""High level orchestration helpers for CSV to XML conversion."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from ..xml_generator import (
    generate_index_xml,
    generate_summary_xml,
    generate_health_checkup_cda,
    generate_health_guidance_cda,
    generate_checkup_settlement_xml,
    generate_guidance_settlement_xml,
    get_claim_amount_from_cc08,
    get_claim_amount_from_gc08,
    get_subject_count_from_cda,
)
from ..validator import validate_xml

from .archive_verification import ArchiveVerificationMixin, XMLValidationTarget

logger = logging.getLogger(__name__)


class Orchestrator(ArchiveVerificationMixin):
    """Coordinate CSV parsing, rule application and XML generation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the orchestrator with configuration values."""
        self.config = config
        self.csv_profiles = config.get("csv_profiles", {})
        self.lookup_tables = config.get("lookup_tables", {}).copy()

        oid_catalog_path_from_config = config.get("oid_catalog_file")
        if oid_catalog_path_from_config:
            resolved_oid_path = Path(oid_catalog_path_from_config)
            if resolved_oid_path.exists():
                try:
                    with open(resolved_oid_path, "r", encoding="utf-8") as f_oid:
                        oid_data = json.load(f_oid)
                    self.lookup_tables["$oid_catalog$"] = oid_data
                    logger.info(
                        f"Successfully loaded OID Catalog from '{resolved_oid_path}' into lookup_tables."
                    )
                except Exception as e_oid_load:  # pragma: no cover - defensive
                    logger.error(
                        f"Failed to load or parse OID Catalog from '{resolved_oid_path}': {e_oid_load}"
                    )
            else:
                logger.warning(
                    f"OID Catalog file specified in config ('{oid_catalog_path_from_config}') but not found at path '{resolved_oid_path}' (expected relative to project root)."
                )
        else:
            logger.info(
                "No 'oid_catalog_file' specified in config. OID lookups will fail if rules expect '$oid_catalog$'."
            )

        logger.info("Orchestrator initialized (CSV profiles and OID catalog processing attempted).")
