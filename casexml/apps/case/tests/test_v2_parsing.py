from django.test import TestCase
import os
from casexml.apps.case.models import CommCareCase
from couchforms.util import post_xform_to_couch
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.signals import process_cases
from datetime import datetime
from casexml.apps.phone import views as phone_views
from django.http import HttpRequest

class Version2CaseParsingTest(TestCase):
    """
    Tests parsing v2 casexml
    """
    
    def setUp(self):
        for item in CommCareCase.view("case/by_xform_id", include_docs=True).all():
            item.delete()
        
    
    def testParseCreate(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_create.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get("foo-case-id")
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual(datetime(2011, 12, 6, 13, 42, 50), case.modified_on)
        self.assertEqual("v2_case_type", case.type)
        self.assertEqual("test case name", case.name)
        self.assertEqual(1, len(case.actions))
    
    def testParseUpdate(self):
        self.testParseCreate()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get("foo-case-id")
        self.assertFalse(case.closed)
        self.assertEqual("bar-user-id", case.user_id)
        self.assertEqual(datetime(2011, 12, 7, 13, 42, 50), case.modified_on)
        self.assertEqual("updated_v2_case_type", case.type)
        self.assertEqual("updated case name", case.name)
        self.assertEqual("something dynamic", case.dynamic)
        self.assertEqual(2, len(case.actions))
    
    def testParseClose(self):
        self.testParseCreate()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "basic_close.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get("foo-case-id")
        self.assertTrue(case.closed)
        
    def testParseWithIndices(self):
        self.testParseCreate()
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "v2", "index_update.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get("foo-case-id")
        self.assertEqual(2, len(case.indices))
        self.assertTrue(case.has_index("foo_ref"))
        self.assertTrue(case.has_index("baz_ref"))
        self.assertEqual("bar", case.get_index("foo_ref").referenced_type)
        self.assertEqual("some_referenced_id", case.get_index("foo_ref").referenced_id)
        self.assertEqual("bop", case.get_index("baz_ref").referenced_type)
        self.assertEqual("some_other_referenced_id", case.get_index("baz_ref").referenced_id)
        
        # quick test for ota restore
        v2response = phone_views.xml_for_case(HttpRequest(), case.get_id, version="2.0")
        expected_v2_response = """
<case case_id="foo-case-id" date_modified="2011-12-07" user_id="bar-user-id" xmlns="http://commcarehq.org/case/transaction/v2">
    <create>
        <case_type>v2_case_type</case_type>
        <case_name>test case name</case_name>
    </create>
    <update />
    <index>
        <foo_ref case_type="bar">some_referenced_id</foo_ref>
        <baz_ref case_type="bop">some_other_referenced_id</baz_ref>
    </index>
</case>"""
        check_xml_line_by_line(self, expected_v2_response, v2response.content)
        