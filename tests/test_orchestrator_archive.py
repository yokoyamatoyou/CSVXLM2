import os
import zipfile
from csv_to_xml_converter.orchestrator import Orchestrator


def _write_simple_xsd(path, root_name, require_child=False):
    if require_child:
        content = (
            "<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">"
            f"<xs:element name=\"{root_name}\">"
            "<xs:complexType><xs:sequence>"
            "<xs:element name=\"dummy\" type=\"xs:string\"/>"
            "</xs:sequence></xs:complexType>"
            "</xs:element></xs:schema>"
        )
    else:
        content = (
            "<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">"
            f"<xs:element name=\"{root_name}\"/>"
            "</xs:schema>"
        )
    path.write_text(content, encoding="utf-8")


def test_create_and_verify_archive_success(tmp_path):
    xsd_dir = tmp_path / "xsd"
    xsd_dir.mkdir()
    _write_simple_xsd(xsd_dir / "ix08_V08.xsd", "index", require_child=True)
    _write_simple_xsd(xsd_dir / "su08_V08.xsd", "summary")
    _write_simple_xsd(xsd_dir / "hc08_V08.xsd", "ClinicalDocument")
    _write_simple_xsd(xsd_dir / "hg08_V08.xsd", "ClinicalDocument")
    _write_simple_xsd(xsd_dir / "cc08_V08.xsd", "checkupClaim")
    _write_simple_xsd(xsd_dir / "gc08_V08.xsd", "GuidanceClaimDocument")

    index_xml = tmp_path / "index.xml"
    index_xml.write_text("<index><dummy>1</dummy></index>", encoding="utf-8")
    summary_xml = tmp_path / "summary.xml"
    summary_xml.write_text("<summary/>", encoding="utf-8")

    hc_xml = tmp_path / "hc_cda_test.xml"
    hc_xml.write_text("<ClinicalDocument/>", encoding="utf-8")
    hg_xml = tmp_path / "hg_cda_test.xml"
    hg_xml.write_text("<ClinicalDocument/>", encoding="utf-8")
    cs_xml = tmp_path / "cs_test.xml"
    cs_xml.write_text("<checkupClaim/>", encoding="utf-8")
    gs_xml = tmp_path / "gs_test.xml"
    gs_xml.write_text("<GuidanceClaimDocument/>", encoding="utf-8")

    cfg = {"paths": {"xsd_source_path_for_archive": str(xsd_dir)}}
    orchestrator = Orchestrator(cfg)

    zip_path = orchestrator.create_submission_archive(
        str(index_xml),
        str(summary_xml),
        [str(hc_xml), str(hg_xml)],
        [str(cs_xml), str(gs_xml)],
        "archive",
        str(tmp_path),
    )

    assert zip_path and os.path.exists(zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        expected = {
            "archive/index.xml",
            "archive/summary.xml",
            "archive/DATA/hc_cda_test.xml",
            "archive/DATA/hg_cda_test.xml",
            "archive/CLAIMS/cs_test.xml",
            "archive/CLAIMS/gs_test.xml",
            "archive/XSD/ix08_V08.xsd",
            "archive/XSD/su08_V08.xsd",
            "archive/XSD/hc08_V08.xsd",
            "archive/XSD/hg08_V08.xsd",
            "archive/XSD/cc08_V08.xsd",
            "archive/XSD/gc08_V08.xsd",
        }
        assert expected.issubset(names)

    assert orchestrator.verify_archive_contents(zip_path)


def test_verify_archive_failure(tmp_path):
    xsd_dir = tmp_path / "xsd"
    xsd_dir.mkdir()
    _write_simple_xsd(xsd_dir / "ix08_V08.xsd", "index", require_child=True)
    # summary XSD intentionally missing for failure

    index_xml = tmp_path / "index.xml"
    index_xml.write_text("<index></index>", encoding="utf-8")  # missing <dummy>
    summary_xml = tmp_path / "summary.xml"
    summary_xml.write_text("<summary/>", encoding="utf-8")

    cfg = {"paths": {"xsd_source_path_for_archive": str(xsd_dir)}}
    orchestrator = Orchestrator(cfg)

    zip_path = orchestrator.create_submission_archive(
        str(index_xml), str(summary_xml), [], [], "archive2", str(tmp_path)
    )

    assert zip_path and os.path.exists(zip_path)
    assert not orchestrator.verify_archive_contents(zip_path)
