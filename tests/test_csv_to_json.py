import json
from pathlib import Path

from csv_to_xml_converter.utils import csv_to_json


def test_convert_csv_to_json(tmp_path, monkeypatch):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("a,b\n1,2\n3,4", encoding="utf-8")

    config = {
        "csv_profiles": {
            "test": {"delimiter": ",", "encoding": "utf-8", "header": True}
        }
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")

    monkeypatch.setattr(csv_to_json, "DEFAULT_CONFIG_FILE", str(cfg_path))
    records = csv_to_json.convert_csv_to_json(str(csv_path), "test")

    assert records == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    json_path = csv_path.with_suffix(".json")
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded == records
