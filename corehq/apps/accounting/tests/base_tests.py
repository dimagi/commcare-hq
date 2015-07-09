from django.test import TestCase
from corehq.apps.accounting import generator
from corehq.apps.domain.models import Domain


class BaseAccountingTest(TestCase):

    def setUp(self):
        generator.instantiate_accounting_for_tests()

    def tearDown(self):
        for domain in Domain.get_all():
            domain.delete()
