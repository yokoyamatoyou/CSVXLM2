# -*- coding: utf-8 -*-
"""Command-line interface for CSVXLM.

This module exposes a small CLI around the conversion orchestrator.  It can be
invoked directly from the project root::

    python src/main.py [-c CONFIG] [-p PROFILE]

where ``CONFIG`` is the path to the JSON configuration file and ``PROFILE`` is a
CSV profile name defined inside that configuration.  When no options are
provided the script defaults to ``config_rules/config.json`` and the profile
``grouped_checkup_profile``.

The default configuration expects example CSV inputs in ``data/input_csvs/`` and
produces XML files under ``data/output_xmls/``.  A ZIP archive containing the
results is written to ``data/output_archives/``.  The various input file paths,
rule files and XSD locations can be customised in the configuration JSON.
"""

import argparse
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path

from csv_to_xml_converter.config import load_config
from csv_to_xml_converter.logger import setup_logger
from csv_to_xml_converter.orchestrator import Orchestrator

DEFAULT_CONFIG_FILE = "config_rules/config.json"
DEEP_XSD_BASE = "5521111111_00280081_202405271_1/"
# Official schemas reside inside the deeper directory under an "XSD" folder
XSD_OFFICIAL_BASE = os.path.join(DEEP_XSD_BASE, "XSD/")
# General schemas remain in the top level "XSD" directory
XSD_GENERAL_BASE = "XSD/"

# Define output paths for aggregated index and summary
# Changed from ix08_output_V08.xml
DEFAULT_INDEX_OUTPUT_XML = "data/output_xmls/index.xml"
# Changed from su08_output_V08.xml
DEFAULT_SUMMARY_OUTPUT_XML = "data/output_xmls/summary.xml"
DEFAULT_INDEX_XSD_FILE = os.path.join(XSD_GENERAL_BASE, "ix08_V08.xsd")
DEFAULT_SUMMARY_XSD_FILE = os.path.join(XSD_GENERAL_BASE, "su08_V08.xsd")

# Paths for individual document generation (CDAs, Settlements)
DEFAULT_CDA_FULL_RULES_FILE = "config_rules/health_checkup_full_rules.json"
DEFAULT_CDA_FULL_XSD_FILE = os.path.join(XSD_OFFICIAL_BASE, "hc08_V08.xsd")
DEFAULT_CDA_FULL_OUTPUT_DIR = "data/output_xmls/cda_checkup_full/"
DEFAULT_CDA_FULL_FILE_PREFIX = "hc_cda_"

DEFAULT_HG_CDA_FULL_RULES_FILE = "config_rules/health_guidance_full_rules.json"
DEFAULT_HG_CDA_XSD_FILE = os.path.join(XSD_GENERAL_BASE, "hg08_V08.xsd")
DEFAULT_HG_CDA_FULL_OUTPUT_DIR = "data/output_xmls/cda_guidance_full/"
DEFAULT_HG_CDA_FILE_PREFIX = "hg_cda_"

DEFAULT_CS_RULES_FILE = "config_rules/checkup_settlement_rules.json"
DEFAULT_CS_XSD_FILE = os.path.join(XSD_GENERAL_BASE, "cc08_V08.xsd")
DEFAULT_CS_OUTPUT_DIR = "data/output_xmls/settlements_checkup/"
DEFAULT_CS_FILE_PREFIX = "cs_"

DEFAULT_GS_RULES_FILE = "config_rules/guidance_settlement_rules.json"
DEFAULT_GS_XSD_FILE = os.path.join(XSD_GENERAL_BASE, "gc08_V08.xsd")
DEFAULT_GS_OUTPUT_DIR = "data/output_xmls/settlements_guidance/"
DEFAULT_GS_FILE_PREFIX = "gs_"
# Paths for Grouped Checkup CDA Test
DEFAULT_GROUPED_CHECKUP_RULES_FILE = "config_rules/grouped_checkup_rules.json"
# Uses the same health checkup XSD as individual CDA generation
DEFAULT_GROUPED_CHECKUP_XSD_FILE = os.path.join(XSD_OFFICIAL_BASE, "hc08_V08.xsd")
DEFAULT_GROUPED_CHECKUP_OUTPUT_DIR = "data/output_xmls/cda_checkup_grouped/"
DEFAULT_GROUPED_CHECKUP_FILE_PREFIX = "hc_grp_cda_"
DEFAULT_ARCHIVE_OUTPUT_DIR = "data/output_archives/"


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the CLI.

    Parameters
    ----------
    args : list[str] | None, optional
        Argument list to parse. When ``None`` the values are taken from
        ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        Parsed arguments object.
    """

    parser = argparse.ArgumentParser(
        description="CSV to MHLW XML conversion tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help=(
            "Path to the configuration JSON file. "
            "This determines input paths, rule files and output locations."
        ),
    )
    parser.add_argument(
        "-p",
        "--profile",
        default="grouped_checkup_profile",
        help=(
            "CSV profile name defined under 'csv_profiles' in the configuration. "
            "Used to parse the input CSV files."
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Override logging level from the configuration file.",
    )
    parser.add_argument(
        "--sample-test",
        action="store_true",
        help="Run sample data conversion test using bundled folders.",
    )
    parser.add_argument(
        "--sample-num-files",
        type=int,
        default=2,
        metavar="N",
        help="Number of CSV files to convert from each folder when using --sample-test.",
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="When used with --sample-test, skip the normal conversion workflow.",
    )
    # Removed --csv-to-json option; this functionality is no longer exposed via the CLI
    return parser.parse_args(args)


def main(cli_args=None):
    """Run conversion workflow using provided CLI arguments."""

    cli = parse_args(cli_args)
    config_path = cli.config
    app_config = {}
    main_logger = None
    try:
        app_config = load_config(config_path)
    except Exception as e:
        logging.error("Error loading config: %s", e)
        app_config = {"logging": {}}
    if cli.log_level:
        app_config.setdefault("logging", {})["log_level"] = cli.log_level
    app_config["_config_file_path_"] = config_path
    main_logger = setup_logger(config=app_config)
    main_logger.info("Application starting - Grouped CDA Test Run...")

    # Legacy CSV to JSON functionality has been removed
    output_dirs = [
        app_config.get("paths", {}).get("output_xmls", "data/output_xmls"),
        DEFAULT_CDA_FULL_OUTPUT_DIR,
        DEFAULT_HG_CDA_FULL_OUTPUT_DIR,
        DEFAULT_CS_OUTPUT_DIR,
        DEFAULT_GS_OUTPUT_DIR,
        DEFAULT_GROUPED_CHECKUP_OUTPUT_DIR,
        DEFAULT_ARCHIVE_OUTPUT_DIR,
    ]
    # Create output directories
    for d_str in output_dirs:
        Path(d_str).mkdir(parents=True, exist_ok=True)
    orchestrator = Orchestrator(app_config)

    if cli.sample_test:
        from sample_test_mode import convert_first_csvs

        test_dirs = [
            "3610123279",
            "3610123675",
            "3610123808",
            "40歳未満健診CSV",
        ]
        out_dir = app_config.get("paths", {}).get("output_xmls", "data/output_xmls")
        convert_first_csvs(
            test_dirs,
            os.path.join(out_dir, "sample_test"),
            num_files=cli.sample_num_files,
        )
        if cli.sample_only:
            main_logger.info("Sample test complete; exiting as --sample-only was provided.")
            return

    # Initialize lists for collecting generated XML file paths
    all_data_xml_files = []
    all_claims_xml_files = []

    csv_input_dir = app_config.get("paths", {}).get("input_csvs", "data/input_csvs")
    csv_paths = sorted(Path(csv_input_dir).glob("*.csv"))
    if not csv_paths:
        main_logger.warning(f"No CSV files found in {csv_input_dir}")

    for csv_path in csv_paths:
        main_logger.info(f"Processing CSV: {csv_path}")

        ghcf = orchestrator.process_csv_to_health_checkup_cdas(
            str(csv_path),
            DEFAULT_CDA_FULL_RULES_FILE,
            DEFAULT_CDA_FULL_XSD_FILE,
            DEFAULT_CDA_FULL_OUTPUT_DIR,
            DEFAULT_CDA_FULL_FILE_PREFIX,
            cli.profile,
        )
        all_data_xml_files.extend(ghcf)

        ghgf = orchestrator.process_csv_to_health_guidance_cdas(
            str(csv_path),
            DEFAULT_HG_CDA_FULL_RULES_FILE,
            DEFAULT_HG_CDA_XSD_FILE,
            DEFAULT_HG_CDA_FULL_OUTPUT_DIR,
            DEFAULT_HG_CDA_FILE_PREFIX,
            cli.profile,
        )
        all_data_xml_files.extend(ghgf)

        gcsf = orchestrator.process_csv_to_checkup_settlement_xmls(
            str(csv_path),
            DEFAULT_CS_RULES_FILE,
            DEFAULT_CS_XSD_FILE,
            DEFAULT_CS_OUTPUT_DIR,
            DEFAULT_CS_FILE_PREFIX,
            cli.profile,
        )
        all_claims_xml_files.extend(gcsf)

        ggsf = orchestrator.process_csv_to_guidance_settlement_xmls(
            str(csv_path),
            DEFAULT_GS_RULES_FILE,
            DEFAULT_GS_XSD_FILE,
            DEFAULT_GS_OUTPUT_DIR,
            DEFAULT_GS_FILE_PREFIX,
            cli.profile,
        )
        all_claims_xml_files.extend(ggsf)

        main_logger.info(
            f"--- Grouped Checkup CDA for {csv_path.name} (profile: {cli.profile}) ---"
        )
        grouped_cda_files = orchestrator.process_csv_to_health_checkup_cdas(
            str(csv_path),
            DEFAULT_GROUPED_CHECKUP_RULES_FILE,
            DEFAULT_GROUPED_CHECKUP_XSD_FILE,
            DEFAULT_GROUPED_CHECKUP_OUTPUT_DIR,
            DEFAULT_GROUPED_CHECKUP_FILE_PREFIX,
            cli.profile,
        )
        all_data_xml_files.extend(grouped_cda_files)
        if grouped_cda_files:
            main_logger.info(
                f"OK: Generated {len(grouped_cda_files)} Grouped Checkup CDA XML(s)."
            )
        else:
            main_logger.error("FAIL: Grouped Checkup CDA generation.")

    # --- Generate Aggregated Index and Summary XMLs ---
    main_logger.info(f"--- Generating Aggregated Index and Summary XMLs ---")
    index_xml_generated_path = None
    summary_xml_generated_path = None

    if orchestrator.generate_aggregated_index_xml(
        all_data_xml_files,
        all_claims_xml_files,
        DEFAULT_INDEX_OUTPUT_XML,
        DEFAULT_INDEX_XSD_FILE,
    ):
        index_xml_generated_path = DEFAULT_INDEX_OUTPUT_XML
        main_logger.info(
            f"OK: Aggregated Index XML generated: {index_xml_generated_path}"
        )
    else:
        main_logger.error(f"FAIL: Aggregated Index XML generation.")

    if orchestrator.generate_aggregated_summary_xml(
        all_claims_xml_files,
        all_data_xml_files,
        DEFAULT_SUMMARY_OUTPUT_XML,
        DEFAULT_SUMMARY_XSD_FILE,
    ):
        summary_xml_generated_path = DEFAULT_SUMMARY_OUTPUT_XML
        main_logger.info(
            "OK: Aggregated Summary XML generated: "
            f"{summary_xml_generated_path}"
        )
    else:
        main_logger.error(f"FAIL: Aggregated Summary XML generation.")

    main_logger.info(f"--- Archiving Process ---")
    # Use all_data_xml_files and all_claims_xml_files collected above
    if (
        index_xml_generated_path
        and summary_xml_generated_path
        and (all_data_xml_files or all_claims_xml_files)
    ):
        archive_base = (
            f"Submission_Aggregated_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        zip_path = orchestrator.create_submission_archive(
            index_xml_generated_path, summary_xml_generated_path,
            all_data_xml_files, all_claims_xml_files,
            archive_base, DEFAULT_ARCHIVE_OUTPUT_DIR
        )
        if zip_path:
            main_logger.info(f"OK: Archive created: {zip_path}")
            # Add verification step
            if orchestrator.verify_archive_contents(zip_path):
                main_logger.info(
                    "OK: Archive contents successfully verified: "
                    f"{zip_path}"
                )
            else:
                main_logger.error(
                    "FAIL: Archive contents verification failed for: "
                    f"{zip_path}"
                )
        else:
            main_logger.error(f"FAIL: Archive creation.")
    else:
        main_logger.warning(
            "Skipping archiving: missing critical aggregated XMLs or "
            "no data/claims files generated."
        )
    main_logger.info("Application finished.")


if __name__ == "__main__":
    main()
