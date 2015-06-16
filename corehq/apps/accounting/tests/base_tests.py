from django.test import TestCase
from corehq.apps.accounting import generator


class BaseAccountingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        generator.instantiate_accounting_for_tests()

    @classmethod
    def tearDownClass(cls):
        generator.tear_down_accounting_for_tests()
