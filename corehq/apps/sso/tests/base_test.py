from django.test import TestCase

from corehq.apps.sso.tests import generator


class BaseIdPTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()

    def setUp(self):
        super().setUp()
        self.idp = generator.create_idp('vaultwax', self.account)

    def tearDown(self):
        self.idp.delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.account.delete()
        super().tearDownClass()
