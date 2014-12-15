from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.models import CommCareCase
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.tests.util import check_xml_line_by_line, CaseBlock, delete_all_cases
from casexml.apps.case import process_cases
from datetime import datetime
from casexml.apps.phone import views as phone_views
from django.http import HttpRequest
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from dimagi.utils.parsing import json_format_datetime
from casexml.apps.case import const


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class Version2CaseParsingTest(TestCase):
    """
    Tests parsing v2 casexml
    """
    
    def setUp(self):
        delete_all_cases()

    def testParseCreate(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        case = CommCareCase.get("foo-case-id")
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual("bar-user-id", case.opened_by)
        self.assertEqual(datetime(2011, 12, 6, 13, 42, 50), case.modified_on)
        self.assertEqual("v2_case_type", case.type)
        self.assertEqual("test case name", case.name)
        self.assertEqual(1, len(case.actions))
        [action] = case.actions
        self.assertEqual("http://openrosa.org/case/test/create", action.xform_xmlns)
        self.assertEqual("v2 create", action.xform_name)
        self.assertEqual("bar-user-id", case.actions[0].user_id)
    
    def testParseUpdate(self):
        self.testParseCreate()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        case = CommCareCase.get("foo-case-id")
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual(datetime(2011, 12, 7, 13, 42, 50), case.modified_on)
        self.assertEqual("updated_v2_case_type", case.type)
        self.assertEqual("updated case name", case.name)
        self.assertEqual("something dynamic", case.dynamic)
        self.assertEqual(2, len(case.actions))
        self.assertEqual("bar-user-id", case.actions[1].user_id)
    
    def testParseClose(self):
        self.testParseCreate()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_close.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        case = CommCareCase.get("foo-case-id")
        self.assertTrue(case.closed)
        self.assertEqual("bar-user-id", case.closed_by)
        
    def testParseNamedNamespace(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "named_namespace.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        case = CommCareCase.get("14cc2770-2d1c-49c2-b252-22d6ecce385a")
        self.assertFalse(case.closed)
        self.assertEqual("d5ce3a980b5b69e793445ec0e3b2138e", case.user_id)
        self.assertEqual(datetime(2011, 12, 27), case.modified_on)
        self.assertEqual("cc_bihar_pregnancy", case.type)
        self.assertEqual("TEST", case.name)
        self.assertEqual(2, len(case.actions))

    def testParseWithIndices(self):
        self.testParseCreate()

        user_id = "bar-user-id"
        for prereq in ["some_referenced_id", "some_other_referenced_id"]:
            post_case_blocks([
                CaseBlock(
                    create=True, case_id=prereq,
                    user_id=user_id, version=V2
                ).as_xml(format_datetime=json_format_datetime)
            ])

        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "index_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        form = post_xform_to_couch(xml_data)
        process_cases(form)
        case = CommCareCase.get("foo-case-id")
        self.assertEqual(2, len(case.indices))
        self.assertTrue(case.has_index("foo_ref"))
        self.assertTrue(case.has_index("baz_ref"))
        self.assertEqual("bar", case.get_index("foo_ref").referenced_type)
        self.assertEqual("some_referenced_id", case.get_index("foo_ref").referenced_id)
        self.assertEqual("bop", case.get_index("baz_ref").referenced_type)
        self.assertEqual("some_other_referenced_id", case.get_index("baz_ref").referenced_id)

        # check the action
        self.assertEqual(2, len(case.actions))
        [_, index_action] = case.actions
        self.assertEqual(const.CASE_ACTION_INDEX, index_action.action_type)
        self.assertEqual(2, len(index_action.indices))


        # quick test for ota restore
        v2response = phone_views.xml_for_case(HttpRequest(), case.get_id, version="2.0")
        expected_v2_response = """
        <case case_id="foo-case-id" date_modified="2011-12-07T13:42:50Z" user_id="bar-user-id" xmlns="http://commcarehq.org/case/transaction/v2">
                <create>
                    <case_type>v2_case_type</case_type>
                    <case_name>test case name</case_name>
                    <owner_id>bar-user-id</owner_id>
                </create>
                <index>
                    <baz_ref case_type="bop">some_other_referenced_id</baz_ref>
                    <foo_ref case_type="bar">some_referenced_id</foo_ref>
                </index>
            </case>"""
        check_xml_line_by_line(self, expected_v2_response, v2response.content)
        
