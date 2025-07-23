import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .xml_aggregation import XMLAggregationMixin

logger = logging.getLogger(__name__)


@dataclass
class XMLValidationTarget:
    """Represents an XML file to validate against an XSD."""

    path: Path
    xsd_name: str
    file_type: str


class ArchiveVerificationMixin(XMLAggregationMixin):
    """Utility methods for creating and validating submission archives."""

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
            logger.warning(
                "`xsd_source_path_for_archive` in config not found or not a string/list. Defaulting to 'data/xsd_schemas/' for archive XSDs."
            )
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
                            arc_dir_name = (
                                str(std_dir_path.relative_to(tmp_root.parent)).replace(os.sep, "/") + "/"
                            )
                            try:
                                zf.getinfo(arc_dir_name)
                            except KeyError:
                                dir_zipinfo = zipfile.ZipInfo(
                                    arc_dir_name, date_time=datetime.now().timetuple()[:6]
                                )
                                dir_zipinfo.external_attr = 0o40755 << 16
                                zf.writestr(dir_zipinfo, "")
                logger.info("Archive created: %s", final_zip)
                return str(final_zip)
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Error creating archive: %s", e, exc_info=True)
            return None

    def _collect_xml_validation_targets(self, archive_root: Path) -> Tuple[List[XMLValidationTarget], bool]:
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
        except Exception as exc:  # pragma: no cover - defensive
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
        except Exception as e:  # pragma: no cover - defensive
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
