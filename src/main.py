# -*- coding: utf-8 -*-
import os; import logging; from datetime import datetime; import zipfile; from pathlib import Path
from csv_to_xml_converter.config import load_config
from csv_to_xml_converter.logger import setup_logger
from csv_to_xml_converter.orchestrator import Orchestrator

DEFAULT_CONFIG_FILE = "config_rules/config.json"
DUMMY_XSD_BASE_PATH = "data/xsd_schemas/"
XSD_BASE_TO_USE = DUMMY_XSD_BASE_PATH
# ... (Paths for Index, Summary, HC CDA, HG CDA, CS, GS - condensed for brevity) ...
DEFAULT_INDEX_INPUT_CSV = "data/input_csvs/sample_for_index.csv"; DEFAULT_INDEX_RULES_FILE = "config_rules/index_rules.json"; DEFAULT_INDEX_XSD_FILE = XSD_BASE_TO_USE + "ix08_V08.xsd"; DEFAULT_INDEX_OUTPUT_XML = "data/output_xmls/ix08_output_V08.xml"
DEFAULT_SUMMARY_INPUT_CSV = "data/input_csvs/sample_for_summary.csv"; DEFAULT_SUMMARY_RULES_FILE = "config_rules/summary_rules.json"; DEFAULT_SUMMARY_XSD_FILE = XSD_BASE_TO_USE + "su08_V08.xsd"; DEFAULT_SUMMARY_OUTPUT_XML = "data/output_xmls/su08_output_V08.xml"
DEFAULT_CDA_FULL_INPUT_CSV = "data/input_csvs/sample_health_checkup_full.csv"; DEFAULT_CDA_FULL_RULES_FILE = "config_rules/health_checkup_full_rules.json"; DEFAULT_CDA_FULL_XSD_FILE = XSD_BASE_TO_USE + "hc08_V08.xsd"; DEFAULT_CDA_FULL_OUTPUT_DIR = "data/output_xmls/cda_checkup_full/"; DEFAULT_CDA_FULL_FILE_PREFIX = "hc_cda_"
DEFAULT_HG_CDA_FULL_INPUT_CSV = "data/input_csvs/sample_health_guidance_full.csv"; DEFAULT_HG_CDA_FULL_RULES_FILE = "config_rules/health_guidance_full_rules.json"; DEFAULT_HG_CDA_XSD_FILE = XSD_BASE_TO_USE + "hg08_V08.xsd"; DEFAULT_HG_CDA_FULL_OUTPUT_DIR = "data/output_xmls/cda_guidance_full/"; DEFAULT_HG_CDA_FILE_PREFIX = "hg_cda_"
DEFAULT_CS_INPUT_CSV = "data/input_csvs/sample_checkup_settlement.csv"; DEFAULT_CS_RULES_FILE = "config_rules/checkup_settlement_rules.json"; DEFAULT_CS_XSD_FILE = XSD_BASE_TO_USE + "cc08_V08.xsd"; DEFAULT_CS_OUTPUT_DIR = "data/output_xmls/settlements_checkup/"; DEFAULT_CS_FILE_PREFIX = "cs_"
DEFAULT_GS_INPUT_CSV = "data/input_csvs/sample_guidance_settlement.csv"; DEFAULT_GS_RULES_FILE = "config_rules/guidance_settlement_rules.json"; DEFAULT_GS_XSD_FILE = XSD_BASE_TO_USE + "gc08_V08.xsd"; DEFAULT_GS_OUTPUT_DIR = "data/output_xmls/settlements_guidance/"; DEFAULT_GS_FILE_PREFIX = "gs_"
# Paths for Grouped Checkup CDA Test
DEFAULT_GROUPED_CHECKUP_CSV = "data/input_csvs/sample_grouped_checkup.csv"
DEFAULT_GROUPED_CHECKUP_RULES_FILE = "config_rules/grouped_checkup_rules.json"
DEFAULT_GROUPED_CHECKUP_XSD_FILE = XSD_BASE_TO_USE + "hc08_V08.xsd" # Uses the same health checkup XSD
DEFAULT_GROUPED_CHECKUP_OUTPUT_DIR = "data/output_xmls/cda_checkup_grouped/"
DEFAULT_GROUPED_CHECKUP_FILE_PREFIX = "hc_grp_cda_"
DEFAULT_ARCHIVE_OUTPUT_DIR = "data/output_archives/"

def main():
    app_config = {}; main_logger = None
    try: app_config = load_config(DEFAULT_CONFIG_FILE)
    except Exception as e: print(f"Error loading config: {e}"); app_config = {"logging": {}}
    app_config["_config_file_path_"] = DEFAULT_CONFIG_FILE
    main_logger = setup_logger(config=app_config)
    main_logger.info("Application starting - Grouped CDA Test Run...")
    output_dirs = [app_config.get("paths", {}).get("output_xmls", "data/output_xmls"), DEFAULT_CDA_FULL_OUTPUT_DIR, DEFAULT_HG_CDA_FULL_OUTPUT_DIR, DEFAULT_CS_OUTPUT_DIR, DEFAULT_GS_OUTPUT_DIR, DEFAULT_GROUPED_CHECKUP_OUTPUT_DIR, DEFAULT_ARCHIVE_OUTPUT_DIR]
    for d_str in output_dirs: # Corrected variable name 'd' to 'd_str'
        Path(d_str).mkdir(parents=True, exist_ok=True)
    orchestrator = Orchestrator(app_config)
    gip=None; gsp=None; ghcf=[]; ghgf=[]; gcsf=[]; ggsf=[]; grouped_cda_files=[]

    if orchestrator.process_single_csv_to_index_xml(DEFAULT_INDEX_INPUT_CSV, DEFAULT_INDEX_RULES_FILE, DEFAULT_INDEX_XSD_FILE, DEFAULT_INDEX_OUTPUT_XML): gip=DEFAULT_INDEX_OUTPUT_XML
    if orchestrator.process_single_csv_to_summary_xml(DEFAULT_SUMMARY_INPUT_CSV, DEFAULT_SUMMARY_RULES_FILE, DEFAULT_SUMMARY_XSD_FILE, DEFAULT_SUMMARY_OUTPUT_XML): gsp=DEFAULT_SUMMARY_OUTPUT_XML
    ghcf = orchestrator.process_csv_to_health_checkup_cdas(DEFAULT_CDA_FULL_INPUT_CSV, DEFAULT_CDA_FULL_RULES_FILE, DEFAULT_CDA_FULL_XSD_FILE, DEFAULT_CDA_FULL_OUTPUT_DIR)
    ghgf = orchestrator.process_csv_to_health_guidance_cdas(DEFAULT_HG_CDA_FULL_INPUT_CSV, DEFAULT_HG_CDA_FULL_RULES_FILE, DEFAULT_HG_CDA_XSD_FILE, DEFAULT_HG_CDA_FULL_OUTPUT_DIR)
    gcsf = orchestrator.process_csv_to_checkup_settlement_xmls(DEFAULT_CS_INPUT_CSV, DEFAULT_CS_RULES_FILE, DEFAULT_CS_XSD_FILE, DEFAULT_CS_OUTPUT_DIR)
    ggsf = orchestrator.process_csv_to_guidance_settlement_xmls(DEFAULT_GS_INPUT_CSV, DEFAULT_GS_RULES_FILE, DEFAULT_GS_XSD_FILE, DEFAULT_GS_OUTPUT_DIR)

    # --- Test for Grouped Checkup CDA ---
    main_logger.info(f"--- Test: Grouped Checkup CDA (profile: grouped_checkup_profile) ---")
    grouped_cda_files = orchestrator.process_csv_to_health_checkup_cdas( # Reusing existing orchestrator method
        DEFAULT_GROUPED_CHECKUP_CSV, DEFAULT_GROUPED_CHECKUP_RULES_FILE, DEFAULT_GROUPED_CHECKUP_XSD_FILE,
        DEFAULT_GROUPED_CHECKUP_OUTPUT_DIR, DEFAULT_GROUPED_CHECKUP_FILE_PREFIX, "grouped_checkup_profile"
    )
    if grouped_cda_files: main_logger.info(f"OK: Generated {len(grouped_cda_files)} Grouped Checkup CDA XML(s).")
    else: main_logger.error(f"FAIL: Grouped Checkup CDA generation.")

    main_logger.info(f"--- Archiving Process ---")
    all_data = ghcf + ghgf + grouped_cda_files # Add new grouped files
    all_claims = gcsf + ggsf
    if gip and gsp and all_data:
        archive_base = f"Submission_GroupedTest_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        zip_path = orchestrator.create_submission_archive(gip, gsp, all_data, all_claims, archive_base, DEFAULT_ARCHIVE_OUTPUT_DIR)
        if zip_path: main_logger.info(f"OK: Archive created: {zip_path}")
        # ... (zip verification) ...
        else: main_logger.error(f"FAIL: Archive creation.")
    else: main_logger.warning("Skipping archiving: missing critical XMLs or data.")
    main_logger.info("Application finished.")

if __name__ == "__main__": main()
