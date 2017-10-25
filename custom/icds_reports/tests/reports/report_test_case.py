from django.test import TestCase

from corehq.apps.users.models import WebUser


class ReportTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportTestCase, cls).setUpClass()
        cls.username1 = 'user'
        cls.password1 = 'dummy'
        cls.web_user1 = WebUser.create('icds-cas', cls.username1, cls.password1)
        cls.web_user1.eula.signed = True
        cls.web_user1.save()

    def setUp(self):
        self.client.login(username=self.username1, password=self.password1)

    def tearDown(self):
        self.client.logout()

    @classmethod
    def tearDownClass(cls):
        cls.web_user1.delete()
        super(ReportTestCase, cls).tearDownClass()
