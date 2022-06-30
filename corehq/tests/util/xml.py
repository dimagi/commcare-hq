"""XML test utilities"""
import lxml
from lxml.doctestcompare import LHTMLOutputChecker, LXMLOutputChecker

from corehq.tests.util import check_output


def assert_xml_equal(expected, actual, normalize=True):
    if normalize:
        expected = parse_normalize(expected)
        actual = parse_normalize(actual)
    check_output(expected, actual, LXMLOutputChecker(), "xml")


def assert_xml_partial_equal(expected, actual, xpath):
    """
    Extracts a section of XML using the xpath and compares it to the expected

    Extracted XML is placed inside a <partial/> element prior to comparison.
    """
    expected = parse_normalize(expected)
    actual = extract_xml_partial(actual, xpath)
    assert_xml_equal(expected, actual, normalize=False)


def assert_html_equal(expected, actual, normalize=True):
    if normalize:
        expected = parse_normalize(expected, is_html=True)
        actual = parse_normalize(actual, is_html=True)
    check_output(expected, actual, LHTMLOutputChecker(), "html")


def parse_normalize(xml, to_string=True, is_html=False):
    parser_class = lxml.etree.XMLParser
    markup_class = lxml.etree.XML
    meth = "xml"
    if is_html:
        parser_class = lxml.etree.HTMLParser
        markup_class = lxml.etree.HTML
        meth = "html"
    parser = parser_class(remove_blank_text=True)
    parsed = normalize_attributes(markup_class(xml, parser))
    return lxml.etree.tostring(parsed, pretty_print=True, method=meth, encoding='utf-8') if to_string else parsed


def normalize_attributes(xml):
    """Sort XML attributes to make it easier to find differences"""
    for node in xml.iterfind(".//*"):
        if node.attrib:
            attrs = sorted(node.attrib.items())
            node.attrib.clear()
            node.attrib.update(attrs)
    return xml


def extract_xml_partial(xml, xpath, wrap=True):
    actual = parse_normalize(xml, to_string=False)
    nodes = actual.findall(xpath)
    if not wrap:
        assert len(nodes) == 1, 'result must be wrapped if more than 1 node is matched'
        return lxml.etree.tostring(nodes[0], pretty_print=True, encoding='utf-8')

    root = lxml.etree.Element('partial')
    for node in nodes:
        root.append(node)
    return lxml.etree.tostring(root, pretty_print=True, encoding='utf-8')
