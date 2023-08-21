import os
import uuid

from unittest import mock

from lxml import etree
from nose.tools import nottest

import commcare_translations
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import app_doc_types
from corehq.apps.builds.models import (
    BuildSpec,
    CommCareBuild,
    CommCareBuildConfig,
)
from corehq.tests.util.xml import (
    assert_html_equal,
    assert_xml_equal,
    parse_normalize, assert_xml_partial_equal,
)
from corehq.util.test_utils import TestFileMixin, unit_testing_only


class TestXmlMixin(TestFileMixin):
    root = os.path.dirname(__file__)

    def assertXmlPartialEqual(self, expected, actual, xpath):
        assert_xml_partial_equal(expected, actual, xpath)

    def assertXmlEqual(self, expected, actual, normalize=True):
        assert_xml_equal(expected, actual, normalize)

    def assertXmlHasXpath(self, element, xpath):
        message = "Could not find xpath expression '{}' in below XML\n".format(xpath)
        self._assertXpathHelper(element, xpath, message, should_not_exist=False)

    def assertXmlDoesNotHaveXpath(self, element, xpath):
        message = "Found xpath expression '{}' in below XML\n".format(xpath)
        self._assertXpathHelper(element, xpath, message, should_not_exist=True)

    def _assertXpathHelper(self, element, xpath, message, should_not_exist):
        element = parse_normalize(element, to_string=False)
        if bool(element.xpath(xpath)) == should_not_exist:
            raise AssertionError(message + etree.tostring(element, pretty_print=True, encoding='unicode'))

    def assertHtmlEqual(self, expected, actual, normalize=True):
        assert_html_equal(expected, actual, normalize)


class SuiteMixin(TestXmlMixin):

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

    def assert_module_datums(self, suite, module_index, datums):
        """Check the datum IDs used in the suite XML

        :param: suite - The suite xml as bytes
        :param: module_index - The index of the module under test, usually ``module.id``
        :param: datums - List of tuple(datum_xml_tag, datum_id)
        """
        suite_xml = etree.XML(suite)

        session_nodes = suite_xml.findall(f"./entry[{module_index + 1}]/session")
        assert len(session_nodes) == 1
        actual_datums = [
            (child.tag, child.attrib['id'])
            for child in session_nodes[0].getchildren()
        ]
        self.assertEqual(datums, actual_datums)


def add_build(version, build_number):
    return CommCareBuild.create_without_artifacts(version, build_number)


@nottest
def get_build_spec_for_tests(version=None):
    return BuildSpec({
        "version": version or "2.7.0",
        "build_number": None,
        "latest": True
    })


def _get_default(self):
    return get_build_spec_for_tests()


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


def patch_get_xform_resource_overrides():
    """
    Override get_xform_resource_overrides, one of the few places in app manager that uses
    SQL-based models, to avoid needing to turn SimpleTestCases into TestCases.
    """
    return mock.patch(
        'corehq.apps.app_manager.suite_xml.post_process.resources.get_xform_resource_overrides',
        lambda _, __: {}
    )


def patch_validate_xform():
    return mock.patch('corehq.apps.app_manager.models.validate_xform', lambda _: None)


def case_search_sync_cases_on_form_entry_enabled_for_domain():
    """
    Decorate test methods with case_search_sync_cases_on_form_entry_enabled_for_domain() to override
    default False for unit tests.
    """
    return mock.patch(
        "corehq.apps.app_manager.suite_xml.sections.entries."
        "case_search_sync_cases_on_form_entry_enabled_for_domain", return_value=True
    )


@unit_testing_only
def delete_all_apps():
    for doc_type in app_doc_types():
        res = Application.get_db().view(
            'all_docs/by_doc_type',
            startkey=[doc_type],
            endkey=[doc_type, {}],
            reduce=False,
            include_docs=True
        )
        for row in res:
            Application.get_db().delete_doc(row['doc'])


def get_simple_form(xmlns=None):
    xmlns = xmlns or uuid.uuid4().hex
    return """<?xml version="1.0" encoding="UTF-8" ?>
    <h:html xmlns:h="http://www.w3.org/1999/xhtml"
            xmlns:orx="http://openrosa.org/jr/xforms"
            xmlns="http://www.w3.org/2002/xforms"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:jr="http://openrosa.org/javarosa">
        <h:head>
            <h:title>New Form</h:title>
            <model>
                <instance>
                    <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
                          xmlns="{xmlns}" uiVersion="1" version="1" name="New Form">
                        <question1 />
                    </data>
                </instance>
                <bind nodeset="/data/question1" type="xsd:string" />
                <itext>
                    <translation lang="en" default="">
                        <text id="question1-label">
                            <value>question1</value>
                        </text>
                    </translation>
                </itext>
            </model>
        </h:head>
        <h:body>
            <input ref="/data/question1">
                <label ref="jr:itext('question1-label')" />
            </input>
        </h:body>
    </h:html>
    """.format(xmlns=xmlns)
