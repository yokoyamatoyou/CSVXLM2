# CSV to MHLW XML Conversion and Packaging Tool (CSVXLM)

## Overview

This project automates the processing of Japanese "特定健診／特定保健指導" (Specific Health Checkup / Specific Health Guidance) data. It takes CSV files as input, transforms the data based on configurable rules, generates various types of XML documents (hc08, hg08, cc08, gc08), aggregates summary information into `index.xml` and `summary.xml`, and packages all outputs into a validated ZIP archive.

## Specification

The latest Japanese specification for the conversion workflow is included as
`CSVからXML変換詳細手順説明_utf8.txt`, which is a UTF‑8 encoded copy of the
original Shift_JIS file `CSVからXML変換詳細手順説明.txt`.

## Key Features

*   **CSV Parsing:** Flexible CSV reader supporting various encodings (UTF-8, Shift_JIS) and delimiters, with mandatory column validation. Header rows can be supplied via `column_names` when calling `parse_csv_from_profile`, allowing CSVs without headers to be parsed.
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

## Environment Setup

The project targets **Python 3.10+**.  Install the required
dependencies with:

```bash
pip install -r requirements.txt
```

This installs the `lxml` library which is required for XML generation
and validation. The CLI uses Python's built-in `argparse` so no
additional packages are required. If you are running Python 3.6, also
install the `dataclasses` backport.

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

If the path `5521111111_00280081_202405271_1/5521111111_00280081_202405271_1/XSD/` referenced in `config_rules/config.json` does not exist, unzip the archive `data/5521111111_00280081_202405271_1.zip` from the project root:

```bash
unzip data/5521111111_00280081_202405271_1.zip
```

This will create the necessary folder hierarchy containing official schema files used during archive validation.

## Usage

1.  Install the dependencies listed in `requirements.txt` and ensure
    the XSD files are placed as described above.
2.  Run the main script from the project root directory. Configuration and CSV
    profile can be overridden via command line options:
    ```bash
    python src/main.py --config config_rules/config.json --profile grouped_checkup_profile
    ```
3.  Output XMLs will be generated in `data/output_xmls/` and ZIP archives in `data/output_archives/`.
4.  Logs are written to the console and/or `logs/app.log` as specified in
    `config_rules/config.json`. Set `logging.console` or `logging.file` to `true`
    or `false` to control the destinations.

## Running Tests

The test suite relies on the Python `lxml` package and the `xmllint` command-line tool.
`lxml` is installed from `requirements.txt`. On Debian/Ubuntu systems install `xmllint` via the `libxml2-utils` package:

```bash
sudo apt-get update
sudo apt-get install -y libxml2-utils
```

Run all unit tests from the project root with:

```bash
pytest -q
```


## Development Notes

### Project Roadmap

The implementation is divided into five phases:

1. **Phase 1 – CSV Parsing**
   * Support various delimiters and encodings (UTF‑8/Shift_JIS).
   * Validate the presence of required columns.
2. **Phase 2 – Rule Engine**
   * Load mapping rules from JSON/YAML files.
   * Perform code lookups and date conversions to populate intermediate objects.
3. **Phase 3 – Individual XML Generation**
   * Generate HC08, HG08, CC08 and GC08 XML documents and validate them against XSDs.
4. **Phase 4 – index.xml / summary.xml**
   * Aggregate counts and totals from the generated XMLs to produce index and summary files.
5. **Phase 5 – ZIP Packaging**
   * Assemble the XML files and schemas into a submission archive with the required directory structure.

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

## Current Progress

The XML generation layer is largely in place. The following generators have been
implemented and validated against their XSD schemas:

* `index.xml` and `summary.xml`
* hc08 (health checkup CDA)
* hg08 (health guidance CDA)
* cc08 (checkup settlement)
* gc08 (guidance settlement)

### Remaining Work

* Integrate the dataclass-based models with these generators.
* Expand the rule engine to support more complex mappings.
* Refactor the orchestrator to remove legacy dictionary paths.
* Add unit tests covering real-world data samples.

### Known Limitations / TODOs

* Several orchestrator calls still pass raw dictionaries to the generators.
* Command-line options are minimal and may change as development continues.
