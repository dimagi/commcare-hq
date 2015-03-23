import uuid
from django.test import TestCase
from django.conf import settings
from django.test.utils import override_settings
from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.test_const import *
from casexml.apps.case.tests.util import bootstrap_case_from_xml
from dimagi.utils.post import post_data


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class CaseFromXFormTest(TestCase):
    
    def testCreate(self):
        case = bootstrap_case_from_xml(self, "create.xml")
        self._check_static_properties(case)
        self.assertEqual(False, case.closed)
        
        self.assertEqual(1, len(case.actions))
        create_action = case.actions[0]
        self.assertEqual(const.CASE_ACTION_CREATE, create_action.action_type)
        self.assertEqual("http://openrosa.org/case/test/create", create_action.xform_xmlns)
        self.assertEqual("test create", create_action.xform_name)

    def testCreateThenUpdateInSeparateForms(self):
        # recycle our previous test's form
        original_case = bootstrap_case_from_xml(self, "create_update.xml")
        original_case.save()
        self.assertEqual(original_case.type, "test_case_type")
        self.assertEqual(original_case.name, "test case name")
        # we don't need to bother checking all the properties because this is
        # the exact same workflow as above.
        
        case = bootstrap_case_from_xml(self, "update.xml", original_case.case_id)
        self.assertEqual(False, case.closed)
        
        self.assertEqual(3, len(case.actions))
        new_update_action = case.actions[2]
        self.assertEqual(const.CASE_ACTION_UPDATE, new_update_action.action_type)
        self.assertEqual("http://openrosa.org/case/test/update", new_update_action.xform_xmlns)
        self.assertEqual("", new_update_action.xform_name)

        # some properties didn't change
        self.assertEqual("123", str(case["someotherprop"]))
        
        # but some should have
        self.assertEqual("abcd", case["someprop"])
        self.assertEqual("abcd", new_update_action.updated_unknown_properties["someprop"])
        
        # and there are new ones
        self.assertEqual("efgh", case["somenewprop"])
        self.assertEqual("efgh", new_update_action.updated_unknown_properties["somenewprop"])
        
        # we also changed everything originally in the case
        self.assertEqual("a_new_type", case.type)
        self.assertEqual("a_new_type", new_update_action.updated_known_properties["type"])
        self.assertEqual("a new name", case.name)
        self.assertEqual("a new name", new_update_action.updated_known_properties["name"])        
        self.assertEqual(UPDATE_DATE, case.opened_on)
        self.assertEqual(UPDATE_DATE, new_update_action.updated_known_properties["opened_on"])
        
        # case should have a new modified date
        self.assertEqual(MODIFY_DATE, case.modified_on)
        

    def testCreateThenClose(self):
        case = bootstrap_case_from_xml(self, "create.xml")
        case.save()
                
        # now close it
        case = bootstrap_case_from_xml(self, "close.xml", case.case_id)
        self.assertEqual(True, case.closed)
        
        self.assertEqual(3, len(case.actions))
        update_action = case.actions[1]
        close_action = case.actions[2]
        self.assertEqual(const.CASE_ACTION_UPDATE, update_action.action_type)
        self.assertEqual(const.CASE_ACTION_CLOSE, close_action.action_type)
        self.assertEqual("http://openrosa.org/case/test/close", close_action.xform_xmlns)
        self.assertEqual("", close_action.xform_name)

        self.assertEqual("abcde", case["someprop"])
        self.assertEqual("abcde", update_action.updated_unknown_properties["someprop"])
        self.assertEqual("case closed", case["someclosedprop"])
        self.assertEqual("case closed", update_action.updated_unknown_properties["someclosedprop"])
        
        self.assertEqual(CLOSE_DATE, close_action.date)
        self.assertEqual(CLOSE_DATE, case.modified_on)

    def testCreateMultiple(self):
        # TODO: test creating multiple cases from a single form
        pass
    
    def testCreateAndUpdateInDifferentCaseBlocks(self):
        # TODO: two case blocks, one that creates, another that updates
        pass
    
    def _check_static_properties(self, case):
        self.assertEqual(CommCareCase, type(case))
        self.assertEqual('CommCareCase', case.doc_type)
        self.assertEqual("test_case_type", case.type)
        self.assertEqual("test case name", case.name)
        self.assertEqual("someuser", case.user_id)
        self.assertEqual(ORIGINAL_DATE, case.opened_on)
        self.assertEqual(ORIGINAL_DATE, case.modified_on)
        self.assertEqual("someexternal", case.external_id)
