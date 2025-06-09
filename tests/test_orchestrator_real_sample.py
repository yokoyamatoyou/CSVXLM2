import os
from csv_to_xml_converter.orchestrator import Orchestrator


def test_verify_real_sample_archive():
    orch = Orchestrator({})
    sample_zip = os.path.join('data', '5521111111_00280081_202405271_1.zip')
    assert not orch.verify_archive_contents(sample_zip)
