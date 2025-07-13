import os
import pytest
from lxml import etree
from csv_to_xml_converter.validator import validate_xml, XMLValidationError
from csv_to_xml_converter.xml_generator import (
    MHLW_NS_URL as XML_GEN_MHLW_NS_URL,
    XSI_NS as XML_GEN_XSI_NS,
    NSMAP_MHLW_DEFAULT as XML_GEN_NSMAP,
)
def test_validate_xml(tmp_path):
    xsd_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'XSD', 'ix08_V08.xsd'))
    assert os.path.exists(xsd_path)
    root = etree.Element(f"{{{XML_GEN_MHLW_NS_URL}}}index", nsmap=XML_GEN_NSMAP)
    root.set(f"{{{XML_GEN_XSI_NS}}}schemaLocation", f"{XML_GEN_MHLW_NS_URL} ix08_V08.xsd")
    etree.SubElement(root, f"{{{XML_GEN_MHLW_NS_URL}}}interactionType").set("code", "1")
    etree.SubElement(root, f"{{{XML_GEN_MHLW_NS_URL}}}creationTime").set("value", "20230101")
    s_el = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS_URL}}}sender")
    sid_el = etree.SubElement(s_el, f"{{{XML_GEN_MHLW_NS_URL}}}id")
    sid_el.set("root", "1.2.392.200119.6.102")
    sid_el.set("extension", "0000000000")
    r_el = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS_URL}}}receiver")
    rid_el = etree.SubElement(r_el, f"{{{XML_GEN_MHLW_NS_URL}}}id")
    rid_el.set("root", "1.2.392.200119.6.105")
    rid_el.set("extension", "1111111111")
    etree.SubElement(root, f"{{{XML_GEN_MHLW_NS_URL}}}serviceEventType").set("code", "1")
    trc_el = etree.SubElement(root, f"{{{XML_GEN_MHLW_NS_URL}}}totalRecordCount")
    trc_el.set("value", "10")
    valid_xml = etree.tostring(root, xml_declaration=True, encoding="utf-8").decode("utf-8")

    is_valid, errors = validate_xml(valid_xml, xsd_path)
    assert is_valid
    assert errors == []

    trc_el.set("value", "ABC")
    invalid_type_xml = etree.tostring(root, xml_declaration=True, encoding="utf-8").decode("utf-8")
    is_valid, errors = validate_xml(invalid_type_xml, xsd_path)
    assert not is_valid

    trc_el.set("value", "10")
    sender_el = root.find(f"{{{XML_GEN_MHLW_NS_URL}}}sender")
    root.remove(sender_el)
    invalid_struct_xml = etree.tostring(root, xml_declaration=True, encoding="utf-8").decode("utf-8")
    is_valid, errors = validate_xml(invalid_struct_xml, xsd_path)
    assert not is_valid


def test_validate_xml_missing_xsd(tmp_path):
    """validate_xml should raise XMLValidationError when XSD is absent."""
    xml = "<root/>"
    missing_xsd = tmp_path / "missing.xsd"
    with pytest.raises(XMLValidationError):
        validate_xml(xml, str(missing_xsd))
