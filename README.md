# CSV to MHLW XML Conversion and Packaging Tool (CSVXLM)

## Overview

This project automates the processing of Japanese "特定健診／特定保健指導" (Specific Health Checkup / Specific Health Guidance) data. It takes CSV files as input, transforms the data based on configurable rules, generates various types of XML documents (hc08, hg08, cc08, gc08), aggregates summary information into `index.xml` and `summary.xml`, and packages all outputs into a validated ZIP archive.

## Specification

The latest Japanese specification for the conversion workflow is included as
`CSVからXML変換詳細手順説明_utf8.txt`, which is a UTF‑8 encoded copy of the
original Shift_JIS file `CSVからXML変換詳細手順説明.txt`.

## Key Features

*   **CSV Parsing:** Flexible CSV reader supporting various encodings (UTF-8, Shift_JIS) and delimiters, with mandatory column validation. Header rows can be supplied via `column_names` when calling `parse_csv_from_profile`, allowing CSVs without headers to be parsed.
*   **Rule-Based Transformation:** Maps CSV data to intermediate models using external JSON rule files. The rule engine now supports dataclass targets, rounding of numeric values, and standardized handling of missing data.
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
    *   `XSD/`: Top-level directory with the main XSD files used for validation.
    *   `coreschemas/`: Base HL7 CDA schemas referenced by the main XSDs.

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

For the application to run correctly and perform XSD validations, the necessary
schema files are provided in the repository’s top-level `XSD/` directory.  Its
`coreschemas/` subdirectory contains the base HL7 CDA schemas required by the
specification.  The sample archive
`5521111111_00280081_202405271_1/5521111111_00280081_202405271_1/XSD/` mirrors
this layout and can be used directly for testing or as a template.

During XML generation the program loads schemas from these directories and fails
loudly if validation errors occur.  If duplicates exist, the example package path
is preferred over the top-level `XSD/` directory when packaging archives.

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
   * Assemble the XML files and schemas into a submission archive with the required directory structure and verify the package contents.

## Phase 2 Progress

Phase 2 is complete. The rule engine loads mapping rules, performs lookups, converts dates and numbers, and integrates seamlessly with the dataclass-based models used by the XML generators. Key features verified through unit tests include:

* Direct field transfers from CSV to the intermediate model.
* Lookup conversions that translate codes (for example, mapping gender strings to
  code and OID values).
* Date normalization based on specified format patterns.
* Conditional property assignments depending on input values.
* Error handling for unmapped values.
* Multi-row mapping where multiple CSV rows are combined into a single record,
  such as accumulating laboratory results for one patient.

These tests confirm that the engine can populate the intermediate objects with all data required for later XML generation. Additional rules handle rounding of numeric values and normalization of missing value markers as described in the specification.

## Phase 3 & 4 Implementation

Phases 3 and 4 cover the generation of XML documents and the creation of
aggregated `index.xml` and `summary.xml` files.  The project provides generators
for the following profiles:

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

## Phase 5 Implementation

Phase 5 finalizes the workflow by creating the ZIP archive required for
submission. The orchestrator's `create_submission_archive` method copies all
generated XML files and relevant XSDs into the `DATA/`, `CLAIMS/`, and `XSD/`
directories and writes `index.xml` and `summary.xml` at the top level. The
`verify_archive_contents` helper then validates each XML inside the archive
against the bundled XSDs to ensure the package meets the official schema
requirements.

## Current Progress

The full conversion pipeline is operational.  Individual CDAs and settlement
XMLs are generated from CSV input, aggregated into `index.xml` and
`summary.xml`, packaged into a submission ZIP, and the archive contents are
validated against the bundled XSDs.

### Remaining Work

* Expand unit tests with real-world data samples.
* Provide additional command-line options for fine-grained control.

### Known Limitations / TODOs

* Some orchestrator methods still include transitional logic that can be
  simplified.
