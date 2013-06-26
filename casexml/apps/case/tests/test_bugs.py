from django.test import TestCase
import os
from casexml.apps.case import settings
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import CaseBlock, delete_all_cases
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases

class CaseBugTest(TestCase):
    """
    Tests bugs that come up in case processing
    """
    
    def setUp(self):
        settings.CASEXML_FORCE_DOMAIN_CHECK = False
        delete_all_cases()

    def testConflictingIds(self):
        """
        If two forms share an ID it's a conflict
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "id_conflicts.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        try:
            process_cases(sender="testharness", xform=form)
            self.fail("Previous statement should have raised an exception")
        except Exception:
            pass

        
    def testStringFormatProblems(self):
        """
        If two forms share an ID it's a conflict
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "string_formatting.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(sender="testharness", xform=form)
        
        
    def testEmptyCaseId(self):
        """
        How do we do when submitting an empty case id?
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "empty_id.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        try:
            process_cases(sender="testharness", xform=form)
            self.fail("Empty Id should crash")
        except:
            pass
            
    
    def testDateInCaseNameBug(self):
        """
        How do we do when submitting a case name that looks like a date?
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "date_in_case_name.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get(form.xpath("form/case/case_id"))
        self.assertEqual("2011-11-16", case.name)
        
    
    def testDuplicateCasePropertiesBug(self):
        """
        How do we do when submitting multiple values for the same property
        in an update block
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs",
                                 "duplicate_case_properties.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get(form.xpath("form/case/@case_id"))
        # make sure the property is there, but empty
        self.assertEqual("", case.foo)
        
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs",
                                 "duplicate_case_properties_2.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get(form.xpath("form/case/@case_id"))
        # make sure the property takes the last defined value
        self.assertEqual("2", case.bar)
    
    def testMultipleCaseBlocks(self):
        """
        How do we do when submitting a form with multiple blocks for the same case?
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "mutiple_case_blocks.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(sender="testharness", xform=form)
        case = CommCareCase.get(form.xpath("form/comunidad/case/@case_id"))
        self.assertEqual('1630005', case.community_code)
        self.assertEqual('SantaMariaCahabon', case.district_name)
        self.assertEqual('TAMERLO', case.community_name)

        ids = case.get_xform_ids_from_couch()
        self.assertEqual(1, len(ids))
        self.assertEqual(form._id, ids[0])


    def testLotsOfSubcases(self):
        """
        How do we do when submitting a form with multiple blocks for the same case?
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "lots_of_subcases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(sender="testharness", xform=form)
        self.assertEqual(11, len(CommCareCase.view("case/by_user", reduce=False).all()))

    def testSubmitToDeletedCase(self):
        # submitting to a deleted case should update the case but keep it as deleted
        case_id = 'immagetdeleted'
        deleted_doc_type = 'CommCareCase-Deleted'
        post_case_blocks([
            CaseBlock(create=True, case_id=case_id, user_id='whatever',
                      version=V2, update={'foo': 'bar'}).as_xml()
        ])
        case = CommCareCase.get(case_id)
        self.assertEqual('bar', case.foo)
        # hack copy how we delete things
        case.doc_type = deleted_doc_type
        case.save()
        self.assertEqual(deleted_doc_type, case.doc_type)
        post_case_blocks([
            CaseBlock(create=False, case_id=case_id, user_id='whatever',
                      version=V2, update={'foo': 'not_bar'}).as_xml()
        ])
        case = CommCareCase.get(case_id)
        self.assertEqual('not_bar', case.foo)
        self.assertEqual(deleted_doc_type, case.doc_type)
