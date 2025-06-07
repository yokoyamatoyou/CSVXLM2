# CSV to MHLW XML Conversion and Packaging Tool (CSVXLM)

## Overview

This project automates the processing of Japanese "特定健診／特定保健指導" (Specific Health Checkup / Specific Health Guidance) data. It takes CSV files as input, transforms the data based on configurable rules, generates various types of XML documents (hc08, hg08, cc08, gc08), aggregates summary information into `index.xml` and `summary.xml`, and packages all outputs into a validated ZIP archive.

## Key Features

*   **CSV Parsing:** Flexible CSV reader supporting various encodings (UTF-8, Shift_JIS) and delimiters, with mandatory column validation.
*   **Rule-Based Transformation:** Maps CSV data to intermediate models using external JSON rule files. (Note: Phase 2 for full rule engine implementation is pending).
*   **XML Generation:** Creates multiple XML types:
    *   Health Checkup CDA (hc08)
    *   Health Guidance CDA (hg08)
    *   Checkup Settlement (cc08)
    *   Guidance Settlement (gc08)
*   **XSD Validation:** Validates generated XMLs against their respective XSD schemas.
*   **Aggregation:** Generates `index.xml` (basic information file) and `summary.xml` (settlement summary) by aggregating data from the individual XMLs.
*   **Packaging:** Creates a final ZIP archive with a defined structure (`DATA/`, `CLAIMS/`, `XSD/`, `index.xml`, `summary.xml`).
*   **Archive Validation:** Performs a final validation of all XML files within the generated ZIP archive against the XSDs also packaged within it.

## Directory Structure

*   `src/`: Contains the main Python source code for the application.
    *   `csv_to_xml_converter/`: Core package for the conversion logic.
        *   `csv_parser/`: CSV parsing.
        *   `rule_engine/`: Data transformation (Phase 2 target).
        *   `xml_generator/`: XML document generation.
        *   `validator/`: XSD validation.
        *   `orchestrator/`: Main workflow management.
    *   `main.py`: Main executable script.
*   `config_rules/`: Contains JSON configuration files, including processing rules and OID catalogs.
    *   `config.json`: Main application configuration (paths, CSV profiles, logging).
    *   `*.rules.json`: Rule files for specific XML generation tasks.
*   `data/`: Contains data-related files.
    *   `input_csvs/`: Sample input CSV files.
    *   `output_xmls/`: Output directory for generated XML files.
    *   `output_archives/`: Output directory for generated ZIP archives.
    *   `xsd_schemas/`: Contains general XSD schemas (ix08, su08, cc08, gc08, hg08, and their coreschemas).
    *   `xsd_schemas_official/`: Contains official MHLW XSDs for HC08 (Health Checkup CDA) and its more comprehensive `coreschemas` (including base HL7 CDA schemas like `POCD_MT000040.xsd`).

## Prerequisites

*   Python 3.x (developed with Python 3.10+ in mind).
*   `lxml` library: Install using `pip install lxml`.

## XSD File Setup (Crucial for Operation)

For the application to run correctly and perform XSD validations, the necessary XSD schema files must be correctly placed in their respective directories:

1.  **`data/xsd_schemas_official/`**:
    *   Must contain `hc08_V08.xsd`.
    *   Its `coreschemas/` subdirectory must be complete (e.g., including `POCD_MT000040.xsd`, `datatypes_hcgv08.xsd`, `narrativeBlock_hcgv08.xsd`, `voc_hcgv08.xsd`, `xlink.xsd`). This is typically the more comprehensive set of core HL7 CDA schemas.

2.  **`data/xsd_schemas/`**:
    *   Must contain all other main XSDs:
        *   `cc08_V08.xsd` (Checkup Settlement)
        *   `gc08_V08.xsd` (Guidance Settlement)
        *   `hg08_V08.xsd` (Health Guidance CDA)
        *   `ix08_V08.xsd` (Index file)
        *   `su08_V08.xsd` (Summary file)
    *   Its `coreschemas/` subdirectory should contain any specific core schemas required by the XSDs in this directory (e.g., `datatypes_hcgv08.xsd`, `voc_hcgv08.xsd`).

The application is configured to look for XSDs in these specific locations. The ZIP packaging process also sources XSDs from these directories, prioritizing `data/xsd_schemas_official/` for any overlapping file names (like `coreschemas/datatypes_hcgv08.xsd`).

## Usage

1.  Ensure all prerequisites (Python, lxml, XSD file setup) are met.
2.  Run the main script from the project root directory:
    ```bash
    python src/main.py
    ```
3.  Output XMLs will be generated in `data/output_xmls/` and ZIP archives in `data/output_archives/`.
4.  Logs are written to `logs/app.log` (configurable in `config_rules/config.json`).

## Development Notes
* The project is structured into several phases. Phase 2 (Rule Engine for complex transformations) is a significant upcoming part.

## Phase 2 Progress

Development of the rule engine has begun and several mapping scenarios have been
verified through unit tests:

* Direct field transfers from CSV to the intermediate model.
* Lookup conversions that translate codes (for example, mapping gender strings to
  code and OID values).
* Date normalization based on specified format patterns.
* Conditional property assignments depending on input values.
* Error handling for unmapped values.
* Multi-row mapping where multiple CSV rows are combined into a single record,
  such as accumulating laboratory results for one patient.

These tests confirm that the engine can populate the intermediate objects with
all data required for later XML generation.

## Phase 3 Plan

Phase 3 implements XML generation for four profiles:

* **hc08** – Specific health checkup CDA
* **cc08** – Health checkup settlement
* **hg08** – Specific health guidance CDA
* **gc08** – Health guidance settlement

Each generator builds an XML tree from the intermediate objects and validates it
against the appropriate XSD.  The repository already contains the official XSD
sets used for these validations.  The schemas are located in the following
directories:

* `XSD/` – Top-level directory containing the main XSD files and `coreschemas/`.
* `5521111111_00280081_202405271_1/5521111111_00280081_202405271_1/XSD/` –
  Example package layout with bundled XSDs that mirrors the final ZIP structure.

During XML generation the program loads the corresponding schema from these
folders and fails loudly if validation errors occur. If a schema exists in both
locations, the deeper example path is preferred over the top-level `XSD/`
directory.
