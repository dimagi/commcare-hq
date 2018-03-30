from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from django.test import TestCase
import os

from django.test.testcases import SimpleTestCase
from django.test.utils import override_settings

from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml.parser import case_update_from_block
from corehq.apps.receiverwrapper.util import submit_form_locally
from casexml.apps.case.tests.util import check_xml_line_by_line, CaseBlock, delete_all_cases
from datetime import datetime
from casexml.apps.case.xml import V2, V2_NAMESPACE
from casexml.apps.case import const
from casexml.apps.phone import xml
from corehq.form_processor.tests.utils import use_sql_backend


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class Version2CaseParsingTest(TestCase):
    """
    Tests parsing v2 casexml
    """
    
    def setUp(self):
        super(Version2CaseParsingTest, self).setUp()
        delete_all_cases()

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        super(Version2CaseParsingTest, cls).tearDownClass()

    def testParseCreate(self):
        self._test_parse_create()

    def _test_parse_create(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        case = submit_form_locally(xml_data, 'test-domain').case
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual("bar-user-id", case.opened_by)
        creation_date = datetime(2011, 12, 6, 13, 42, 50)
        self.assertEqual(creation_date, case.modified_on)
        self.assertEqual(creation_date, case.opened_on)
        self.assertEqual("v2_case_type", case.type)
        self.assertEqual("test case name", case.name)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(1, len(case.actions))
            [action] = case.actions
            self.assertEqual("http://openrosa.org/case/test/create", action.xform_xmlns)
            self.assertEqual("v2 create", action.xform_name)
            self.assertEqual("bar-user-id", case.actions[0].user_id)

    def testParseUpdate(self):
        self._test_parse_create()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        case = submit_form_locally(xml_data, 'test-domain').case
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual(datetime(2011, 12, 7, 13, 42, 50), case.modified_on)
        self.assertEqual("updated_v2_case_type", case.type)
        self.assertEqual("updated case name", case.name)
        self.assertEqual("something dynamic", case.dynamic_case_properties()['dynamic'])

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(2, len(case.actions))
            self.assertEqual("bar-user-id", case.actions[1].user_id)

    def testParseNoop(self):
        self._test_parse_create()

        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_noop.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        case = submit_form_locally(xml_data, 'test-domain').case
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual(datetime(2011, 12, 7, 13, 44, 50), case.modified_on)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(2, len(case.actions))
            self.assertEqual("bar-user-id", case.actions[1].user_id)

        self.assertEqual(2, len(case.xform_ids))

    def testParseClose(self):
        self._test_parse_create()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_close.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        case = submit_form_locally(xml_data, 'test-domain').case
        self.assertTrue(case.closed)
        self.assertEqual("bar-user-id", case.closed_by)

    def testParseNamedNamespace(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "named_namespace.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        case = submit_form_locally(xml_data, 'test-domain').case
        self.assertFalse(case.closed)
        self.assertEqual("d5ce3a980b5b69e793445ec0e3b2138e", case.user_id)
        self.assertEqual(datetime(2011, 12, 27), case.modified_on)
        self.assertEqual("cc_bihar_pregnancy", case.type)
        self.assertEqual("TEST", case.name)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(2, len(case.actions))

    def testParseWithIndices(self):
        self._test_parse_create()

        user_id = "bar-user-id"
        for prereq in ["some_referenced_id", "some_other_referenced_id"]:
            post_case_blocks([
                CaseBlock(
                    create=True, case_id=prereq,
                    user_id=user_id
                ).as_xml()
            ])

        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "index_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        case = submit_form_locally(xml_data, 'test-domain').case
        self.assertEqual(2, len(case.indices))
        self.assertTrue(case.has_index("foo_ref"))
        self.assertTrue(case.has_index("baz_ref"))
        self.assertEqual("bar", case.get_index("foo_ref").referenced_type)
        self.assertEqual("some_referenced_id", case.get_index("foo_ref").referenced_id)
        self.assertEqual("bop", case.get_index("baz_ref").referenced_type)
        self.assertEqual("some_other_referenced_id", case.get_index("baz_ref").referenced_id)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            # check the action
            self.assertEqual(2, len(case.actions))
            [_, index_action] = case.actions
            self.assertEqual(const.CASE_ACTION_INDEX, index_action.action_type)
            self.assertEqual(2, len(index_action.indices))

        # quick test for ota restore
        v2response = xml.get_case_xml(case, [const.CASE_ACTION_CREATE, const.CASE_ACTION_UPDATE], V2)
        expected_v2_response = """
        <case case_id="foo-case-id" date_modified="2011-12-07T13:42:50.000000Z" user_id="bar-user-id" xmlns="http://commcarehq.org/case/transaction/v2">
                <create>
                    <case_type>v2_case_type</case_type>
                    <case_name>test case name</case_name>
                    <owner_id>bar-user-id</owner_id>
                </create>
                <update>
                    <date_opened>2011-12-06</date_opened>
                </update>
                <index>
                    <baz_ref case_type="bop">some_other_referenced_id</baz_ref>
                    <foo_ref case_type="bar">some_referenced_id</foo_ref>
                </index>
            </case>"""
        check_xml_line_by_line(self, expected_v2_response, v2response)


@use_sql_backend
class Version2CaseParsingTestSQL(Version2CaseParsingTest):
    pass


class SimpleParsingTests(SimpleTestCase):
    def test_index_block_not_dict(self):
        block = case_update_from_block({
            '@xmlns': V2_NAMESPACE,
            '@case_id': '123',
            'index': "   "
        })
        self.assertEqual(block.get_index_action().indices, [])

    def test_attachments_block_not_dict(self):
        block = case_update_from_block({
            '@xmlns': V2_NAMESPACE,
            '@case_id': '123',
            'attachment': "   "
        })
        self.assertEqual(block.get_attachment_action().attachments, {})
