import json
from pathlib import Path
import builtins

import pytest

# Allow importing main from src directory
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main as cli_main

orchestrator_instances = []


class DummyOrchestrator:
    def __init__(self, config):
        self.config = config
        orchestrator_instances.append(self)
        self.hc_calls = []
        self.hg_calls = []
        self.cs_calls = []
        self.gs_calls = []

    def process_csv_to_health_checkup_cdas(self, csv_path, *args, **kwargs):
        self.hc_calls.append(csv_path)
        return []

    def process_csv_to_health_guidance_cdas(self, csv_path, *args, **kwargs):
        self.hg_calls.append(csv_path)
        return []

    def process_csv_to_checkup_settlement_xmls(self, csv_path, *args, **kwargs):
        self.cs_calls.append(csv_path)
        return []

    def process_csv_to_guidance_settlement_xmls(self, csv_path, *args, **kwargs):
        self.gs_calls.append(csv_path)
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
    input_dir = tmp_path / "csvs"
    input_dir.mkdir()
    csv1 = input_dir / "a.csv"
    csv2 = input_dir / "b.csv"
    csv1.write_text("doc_id\n1\n", encoding="utf-8")
    csv2.write_text("doc_id\n2\n", encoding="utf-8")

    config = {"logging": {"console": False}, "paths": {"input_csvs": str(input_dir)}}
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    orchestrator_instances.clear()

    monkeypatch.setattr(cli_main, "Orchestrator", DummyOrchestrator)
    monkeypatch.setattr(cli_main, "DEFAULT_INDEX_OUTPUT_XML", str(tmp_path / "index.xml"))
    monkeypatch.setattr(cli_main, "DEFAULT_SUMMARY_OUTPUT_XML", str(tmp_path / "summary.xml"))
    monkeypatch.setattr(cli_main, "DEFAULT_ARCHIVE_OUTPUT_DIR", str(tmp_path / "archive"))

    cli_main.main(["--config", str(cfg_path), "--profile", "grouped_checkup_profile"])

    assert (tmp_path / "index.xml").exists()
    assert (tmp_path / "summary.xml").exists()

    orch = orchestrator_instances[0]
    assert orch.hc_calls == [str(csv1), str(csv1), str(csv2), str(csv2)]
    assert orch.hg_calls == [str(csv1), str(csv2)]
    assert orch.cs_calls == [str(csv1), str(csv2)]
    assert orch.gs_calls == [str(csv1), str(csv2)]
