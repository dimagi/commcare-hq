from __future__ import absolute_import
from __future__ import unicode_literals
import os
import lxml
from lxml.doctestcompare import LXMLOutputChecker, LHTMLOutputChecker
import mock
from corehq.apps.builds.models import CommCareBuild, CommCareBuildConfig, \
    BuildSpec
import difflib
from lxml import etree

import commcare_translations
from corehq.util.test_utils import TestFileMixin, unit_testing_only
from corehq.apps.app_manager.models import Application
import six


class TestXmlMixin(TestFileMixin):
    root = os.path.dirname(__file__)

    def assertXmlPartialEqual(self, expected, actual, xpath):
        """
        Extracts a section of XML using the xpath and compares it to the expected

        Extracted XML is placed inside a <partial/> element prior to comparison.
        """
        expected = parse_normalize(expected)
        actual = extract_xml_partial(actual, xpath)
        self.assertXmlEqual(expected, actual, normalize=False)

    def assertXmlEqual(self, expected, actual, normalize=True):
        if normalize:
            expected = parse_normalize(expected)
            actual = parse_normalize(actual)
        _check_shared(expected, actual, LXMLOutputChecker(), "xml")

    def assertXmlHasXpath(self, element, xpath):
        message = "Could not find xpath expression '{}' in below XML\n".format(xpath)
        self._assertXpathHelper(element, xpath, message, should_not_exist=False)

    def assertXmlDoesNotHaveXpath(self, element, xpath):
        message = "Found xpath expression '{}' in below XML\n".format(xpath)
        self._assertXpathHelper(element, xpath, message, should_not_exist=True)

    def _assertXpathHelper(self, element, xpath, message, should_not_exist):
        element = parse_normalize(element, to_string=False)
        if bool(element.xpath(xpath)) == should_not_exist:
            raise AssertionError(message + lxml.etree.tostring(element, pretty_print=True))

    def assertHtmlEqual(self, expected, actual, normalize=True):
        if normalize:
            expected = parse_normalize(expected, is_html=True)
            actual = parse_normalize(actual, is_html=True)
        _check_shared(expected, actual, LHTMLOutputChecker(), "html")


class SuiteMixin(TestFileMixin):

    def _assertHasAllStrings(self, app, strings):
        et = etree.XML(app)
        locale_elems = et.findall(".//locale/[@id]")
        locale_strings = [elem.attrib['id'] for elem in locale_elems]

        app_strings = commcare_translations.loads(strings)

        for string in locale_strings:
            if string not in app_strings:
                raise AssertionError("App strings did not contain %s" % string)
            if not app_strings.get(string, '').strip():
                raise AssertionError("App strings has blank entry for %s" % string)

    def _test_generic_suite(self, app_tag, suite_tag=None):
        suite_tag = suite_tag or app_tag
        app = Application.wrap(self.get_json(app_tag))
        self.assertXmlEqual(self.get_xml(suite_tag), app.create_suite())

    def _test_generic_suite_partial(self, app_tag, xpath, suite_tag=None):
        suite_tag = suite_tag or app_tag
        app = Application.wrap(self.get_json(app_tag))
        self.assertXmlPartialEqual(self.get_xml(suite_tag), app.create_suite(), xpath)

    def _test_app_strings(self, app_tag):
        app = Application.wrap(self.get_json(app_tag))
        app_xml = app.create_suite()
        app_strings = app.create_app_strings('default')

        self._assertHasAllStrings(app_xml, app_strings)


def normalize_attributes(xml):
    """Sort XML attributes to make it easier to find differences"""
    for node in xml.iterfind(".//*"):
        if node.attrib:
            attrs = sorted(six.iteritems(node.attrib))
            node.attrib.clear()
            node.attrib.update(attrs)
    return xml


def parse_normalize(xml, to_string=True, is_html=False):
    parser_class = lxml.etree.XMLParser
    markup_class = lxml.etree.XML
    meth = "xml"
    if is_html:
        parser_class = lxml.etree.HTMLParser
        markup_class = lxml.etree.HTML
        meth = "html"
    parser = parser_class(remove_blank_text=True)
    parse = lambda *args: normalize_attributes(markup_class(*args))
    parsed = parse(xml, parser)
    return lxml.etree.tostring(parsed, pretty_print=True, method=meth) if to_string else parsed


def _check_shared(expected, actual, checker, extension):
    # snippet from http://stackoverflow.com/questions/321795/comparing-xml-in-a-unit-test-in-python/7060342#7060342
    if not checker.check_output(expected, actual, 0):
        original_message = message = "{} mismatch\n\n".format(extension.upper())
        diff = difflib.unified_diff(
            expected.splitlines(1),
            actual.splitlines(1),
            fromfile='want.{}'.format(extension),
            tofile='got.{}'.format(extension)
        )
        for line in diff:
            message += line
        if message != original_message:
            # check that there was actually a diff, because checker.check_output
            # doesn't work with unicode characters in xml node names
            raise AssertionError(message)


def extract_xml_partial(xml, xpath):
    actual = parse_normalize(xml, to_string=False)
    nodes = actual.findall(xpath)
    root = lxml.etree.Element('partial')
    for node in nodes:
        root.append(node)
    return lxml.etree.tostring(root, pretty_print=True)


def add_build(version, build_number):
    path = os.path.join(os.path.dirname(__file__), "jadjar")
    jad_path = os.path.join(path, 'CommCare_%s_%s.zip' % (version, build_number))
    return CommCareBuild.create_from_zip(jad_path, version, build_number)


def _get_default(self):
    return BuildSpec({
        "version": "2.7.0",
        "build_number": None,
        "latest": True
    })

patch_default_builds = mock.patch.object(CommCareBuildConfig, 'get_default',
                                         _get_default)


def commtrack_enabled(is_enabled):
    """
    Override the Application.commtrack_enabled lookup.
    Decorate test methods to explicitly specify a commtrack_enabled status.
    """
    return mock.patch(
        'corehq.apps.app_manager.models.Application.commtrack_enabled',
        new=is_enabled,
    )


@unit_testing_only
def delete_all_apps():
    results = Application.get_db().view(
        'app_manager/applications',
        reduce=False,
        include_docs=False,
    ).all()
    for result in results:
        try:
            app = Application.get(result['id'])
        except Exception:
            pass
        else:
            app.delete()
