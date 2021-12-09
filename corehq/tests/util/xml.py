"""XML test utilities"""
import difflib

import lxml
from lxml.doctestcompare import LHTMLOutputChecker, LXMLOutputChecker


def assert_xml_equal(expected, actual, normalize=True):
    if normalize:
        expected = parse_normalize(expected)
        actual = parse_normalize(actual)
    _check_shared(expected, actual, LXMLOutputChecker(), "xml")


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
    _check_shared(expected, actual, LHTMLOutputChecker(), "html")


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


def _check_shared(expected, actual, checker, extension):
    # snippet from http://stackoverflow.com/questions/321795/comparing-xml-in-a-unit-test-in-python/7060342#7060342
    if isinstance(expected, bytes):
        expected = expected.decode('utf-8')
    if isinstance(actual, bytes):
        actual = actual.decode('utf-8')
    if not checker.check_output(expected, actual, 0):
        original_message = message = "{} mismatch\n\n".format(extension.upper())
        diff = difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile='want.{}'.format(extension),
            tofile='got.{}'.format(extension)
        )
        for line in diff:
            message += line
        if message != original_message:
            # check that there was actually a diff, because checker.check_output
            # doesn't work with unicode characters in xml node names
            raise AssertionError(message)


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
