from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from casexml.apps.case import const
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.test_const import *
from casexml.apps.case.tests.util import bootstrap_case_from_xml
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CaseTransaction, CommCareCaseSQL
from corehq.form_processor.tests.utils import run_with_all_backends


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class CaseFromXFormTest(TestCase):

    def setUp(self):
        self.interface = FormProcessorInterface()

    @run_with_all_backends
    def testCreate(self):
        xform, case = bootstrap_case_from_xml(self, "create.xml")
        self._check_static_properties(case)
        self.assertEqual(False, case.closed)

        if settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self._check_transactions(case, [xform])
            self.assertTrue(case.transactions[0].is_case_create)
        else:
            self.assertEqual(1, len(case.actions))
            create_action = case.actions[0]
            self.assertEqual(const.CASE_ACTION_CREATE, create_action.action_type)
            self.assertEqual("http://openrosa.org/case/test/create", create_action.xform_xmlns)
            self.assertEqual(xform.form_id, create_action.xform_id)
            self.assertEqual("test create", create_action.xform_name)

    @run_with_all_backends
    def testCreateThenUpdateInSeparateForms(self):
        # recycle our previous test's form
        xform1, original_case = bootstrap_case_from_xml(self, "create_update.xml")
        self.assertEqual(original_case.type, "test_case_type")
        self.assertEqual(original_case.name, "test case name")
        # we don't need to bother checking all the properties because this is
        # the exact same workflow as above.
        
        xform2, case = bootstrap_case_from_xml(self, "update.xml", original_case.case_id)
        # fetch the case from the DB to ensure it is property wrapped
        case = CaseAccessors().get_case(case.case_id)
        self.assertEqual(False, case.closed)

        if settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self._check_transactions(case, [xform1, xform2])
            self.assertTrue(case.transactions[0].is_case_create)
        else:
            self.assertEqual(3, len(case.actions))
            new_update_action = case.actions[2]
            self.assertEqual(const.CASE_ACTION_UPDATE, new_update_action.action_type)
            self.assertEqual("http://openrosa.org/case/test/update", new_update_action.xform_xmlns)
            self.assertEqual("", new_update_action.xform_name)
            # updated prop
            self.assertEqual("abcd", new_update_action.updated_unknown_properties["someprop"])
            # new prop
            self.assertEqual("efgh", new_update_action.updated_unknown_properties["somenewprop"])

            # update original case fields
            self.assertEqual("a_new_type", new_update_action.updated_known_properties["type"])
            self.assertEqual("a new name", new_update_action.updated_known_properties["name"])
            self.assertEqual(UPDATE_DATE, new_update_action.updated_known_properties["opened_on"])

        # some properties didn't change
        self.assertEqual("123", str(case.dynamic_case_properties()['someotherprop']))

        # but some should have
        self.assertEqual("abcd", case.dynamic_case_properties()["someprop"])

        # and there are new ones
        self.assertEqual("efgh", case.dynamic_case_properties()["somenewprop"])

        # we also changed everything originally in the case
        self.assertEqual("a_new_type", case.type)
        self.assertEqual("a new name", case.name)
        self.assertEqual(UPDATE_DATE, case.opened_on)

        # case should have a new modified date
        self.assertEqual(MODIFY_DATE, case.modified_on)
        
    @run_with_all_backends
    def testCreateThenClose(self):
        xform1, case = bootstrap_case_from_xml(self, "create.xml")

        # now close it
        xform2, case = bootstrap_case_from_xml(self, "close.xml", case.case_id)
        self.assertEqual(True, case.closed)

        if settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self._check_transactions(case, [xform1, xform2])
            self.assertTrue(case.transactions[0].is_case_create)
            self.assertTrue(case.transactions[1].is_case_close)
        else:
            self.assertEqual(3, len(case.actions))
            update_action = case.actions[1]
            close_action = case.actions[2]
            self.assertEqual(const.CASE_ACTION_UPDATE, update_action.action_type)
            self.assertEqual(const.CASE_ACTION_CLOSE, close_action.action_type)
            self.assertEqual("http://openrosa.org/case/test/close", close_action.xform_xmlns)
            self.assertEqual("", close_action.xform_name)
            self.assertEqual("abcde", update_action.updated_unknown_properties["someprop"])
            self.assertEqual("case closed", update_action.updated_unknown_properties["someclosedprop"])
            self.assertEqual(CLOSE_DATE, close_action.date)

        self.assertEqual("abcde", case.dynamic_case_properties()["someprop"])
        self.assertEqual("case closed", case.dynamic_case_properties()["someclosedprop"])
        self.assertEqual(CLOSE_DATE, case.modified_on)

    def _check_static_properties(self, case):
        if settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self.assertEqual(CommCareCaseSQL, type(case))
        else:
            self.assertEqual(CommCareCase, type(case))
            self.assertEqual('CommCareCase', case.doc_type)
        self.assertEqual("test_case_type", case.type)
        self.assertEqual("test case name", case.name)
        self.assertEqual("someuser", case.user_id)
        self.assertEqual(ORIGINAL_DATE, case.opened_on)
        self.assertEqual(ORIGINAL_DATE, case.modified_on)
        self.assertEqual("someexternal", case.external_id)

    def _check_transactions(self, case, xforms):
        self.assertEqual(len(xforms), len(case.transactions))
        for index, xform in enumerate(xforms):
            transaction = case.transactions[index]
            self.assertTrue(CaseTransaction.is_form_transaction)
            self.assertEqual(xform.form_id, transaction.form_id)
            self.assertFalse(transaction.revoked)
