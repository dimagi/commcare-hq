from django.test import TestCase
from corehq.apps.accounting import generator


class BaseAccountingTest(TestCase):

    def setUp(self):
        generator.instantiate_accounting_for_tests()

    def tearDown(self):
        generator.teardown_accounting_for_tests()
