from django.test import TestCase
from corehq.apps.accounting import generator
from corehq.apps.domain.models import Domain

from django_prbac.models import Role


class BaseAccountingTest(TestCase):

    def setUp(self):
        Role.get_cache().clear()
        generator.instantiate_accounting_for_tests()

    def tearDown(self):
        for domain in Domain.get_all():
            domain.delete()
