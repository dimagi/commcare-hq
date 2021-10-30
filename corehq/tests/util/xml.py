"""XML test utilities"""
import lxml
from lxml.doctestcompare import LHTMLOutputChecker, LXMLOutputChecker

from corehq.tests.util import check_output


def assert_xml_equal(expected, actual, normalize=True):
    if normalize:
        expected = parse_normalize(expected)
        actual = parse_normalize(actual)
    check_output(expected, actual, LXMLOutputChecker(), "xml")


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
