from pathlib import Path
from sample_test_mode import convert_first_csvs


def test_convert_first_csvs(tmp_path):
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    (d1 / "x.csv").write_text("col\n1", encoding="utf-8")
    (d2 / "y.csv").write_text("col\n2", encoding="utf-8")
    out_dir = tmp_path / "out"
    xmls = convert_first_csvs([d1, d2], out_dir)
    assert len(xmls) == 2
    for p in xmls:
        assert Path(p).exists()
