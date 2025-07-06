from csv_to_xml_converter.xml_generator import xml_parsing_utils


def test_xml_parsing_utils_exported():
    assert hasattr(xml_parsing_utils, 'get_claim_amount')
