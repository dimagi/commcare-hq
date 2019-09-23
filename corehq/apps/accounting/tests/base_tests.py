from django.test import TestCase

from django_prbac.models import Role

from corehq.apps.accounting.tests import generator


class BaseAccountingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseAccountingTest, cls).setUpClass()
        Role.get_cache().clear()
