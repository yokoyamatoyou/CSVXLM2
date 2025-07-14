import json
from pathlib import Path
import builtins

import pytest

# Allow importing main from src directory
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main as cli_main

class DummyOrchestrator:
    def __init__(self, config):
        self.config = config

    def process_csv_to_health_checkup_cdas(self, *args, **kwargs):
        return []

    def process_csv_to_health_guidance_cdas(self, *args, **kwargs):
        return []

    def process_csv_to_checkup_settlement_xmls(self, *args, **kwargs):
        return []

    def process_csv_to_guidance_settlement_xmls(self, *args, **kwargs):
        return []

    def generate_aggregated_index_xml(self, *args):
        output_path = args[2]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("<index/>", encoding="utf-8")
        return True

    def generate_aggregated_summary_xml(self, *args):
        output_path = args[2]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("<summary/>", encoding="utf-8")
        return True

    def create_submission_archive(self, *args):
        archive_dir = Path(args[-1])
        archive_dir.mkdir(parents=True, exist_ok=True)
        zip_path = archive_dir / "archive.zip"
        with open(zip_path, "wb") as f:
            f.write(b"zip")
        return str(zip_path)

    def verify_archive_contents(self, *args, **kwargs):
        return True


def test_cli_main_runs(monkeypatch, tmp_path):
    # Minimal config only needs logging section
    config = {"logging": {"console": False}}
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setattr(cli_main, "Orchestrator", DummyOrchestrator)
    monkeypatch.setattr(cli_main, "DEFAULT_INDEX_OUTPUT_XML", str(tmp_path / "index.xml"))
    monkeypatch.setattr(cli_main, "DEFAULT_SUMMARY_OUTPUT_XML", str(tmp_path / "summary.xml"))
    monkeypatch.setattr(cli_main, "DEFAULT_ARCHIVE_OUTPUT_DIR", str(tmp_path / "archive"))

    cli_main.main(["--config", str(cfg_path), "--profile", "grouped_checkup_profile"])

    assert (tmp_path / "index.xml").exists()
    assert (tmp_path / "summary.xml").exists()
