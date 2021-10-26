from django.test import TestCase
from casexml.apps.case.tests.test_const import CLOSE_DATE, MODIFY_DATE, ORIGINAL_DATE, UPDATE_DATE
from casexml.apps.case.tests.util import bootstrap_case_from_xml
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CaseTransaction, CommCareCaseSQL
from corehq.form_processor.tests.utils import sharded
from corehq.util.dates import coerce_to_datetime


@sharded
class CaseFromXFormTest(TestCase):

    def setUp(self):
        self.interface = FormProcessorInterface()

    def testCreate(self):
        xform, case = bootstrap_case_from_xml(self, "create.xml")
        self._check_static_properties(case)
        self.assertEqual(False, case.closed)

        self._check_transactions(case, [xform])
        self.assertTrue(case.transactions[0].is_case_create)

    def testCreateThenUpdateInSeparateForms(self):
        # recycle our previous test's form
        xform1, original_case = bootstrap_case_from_xml(self, "create_update.xml")
        self.assertEqual(original_case.type, "test_case_type")
        self.assertEqual(original_case.name, "test case name")
        # we don't need to bother checking all the properties because this is
        # the exact same workflow as above.

        xform2, case = bootstrap_case_from_xml(self, "update.xml", original_case.case_id)
        # fetch the case from the DB to ensure it is property wrapped
        case = CaseAccessors(case.domain).get_case(case.case_id)
        self.assertEqual(False, case.closed)

        self._check_transactions(case, [xform1, xform2])
        self.assertTrue(case.transactions[0].is_case_create)

        # some properties didn't change
        self.assertEqual("123", str(case.dynamic_case_properties()['someotherprop']))

        # but some should have
        self.assertEqual("abcd", case.dynamic_case_properties()["someprop"])

        # and there are new ones
        self.assertEqual("efgh", case.dynamic_case_properties()["somenewprop"])

        # we also changed everything originally in the case
        self.assertEqual("a_new_type", case.type)
        self.assertEqual("a new name", case.name)
        self.assertEqual(coerce_to_datetime(UPDATE_DATE), coerce_to_datetime(case.opened_on))

        # case should have a new modified date
        self.assertEqual(MODIFY_DATE, case.modified_on)

    def testCreateThenClose(self):
        xform1, case = bootstrap_case_from_xml(self, "create.xml")

        # now close it
        xform2, case = bootstrap_case_from_xml(self, "close.xml", case.case_id)
        self.assertEqual(True, case.closed)

        self._check_transactions(case, [xform1, xform2])
        self.assertTrue(case.transactions[0].is_case_create)
        self.assertTrue(case.transactions[1].is_case_close)

        self.assertEqual("abcde", case.dynamic_case_properties()["someprop"])
        self.assertEqual("case closed", case.dynamic_case_properties()["someclosedprop"])
        self.assertEqual(CLOSE_DATE, case.modified_on)

    def _check_static_properties(self, case):
        self.assertEqual(CommCareCaseSQL, type(case))
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
