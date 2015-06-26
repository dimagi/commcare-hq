from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import delete_all_cases
from corehq.apps.hqcase.dbaccessors import get_total_case_count


class TestCaseByOwner(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_cases()

    def testCountZero(self):
        self.assertEqual(0, get_total_case_count())

    def testCountNonZero(self):
        CommCareCase().save()
        CommCareCase().save()
        self.assertEqual(2, get_total_case_count())
        delete_all_cases()
