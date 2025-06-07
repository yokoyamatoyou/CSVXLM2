import pytest
from csv_to_xml_converter.config import load_config


def test_load_default_config():
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "paths" in cfg


def test_load_config_missing(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_config(str(missing))
