from unittest import SkipTest

from django.urls import reverse

from django.contrib.auth.models import User
from django.test.client import Client

from corehq.apps.users.models import WebUser

from .. import models
from ..models import AccessAudit
from .testutils import AuditcareTest

USERNAME = 'mockmock@mockmock.com'


class TestAccessAudit(AuditcareTest):

    def setUp(self):
        self.client = Client()

    def create_user(self):
        usr = User(username=USERNAME, first_name="mocky", last_name="mock")
        usr.set_password('mockmock')
        usr.save()

    def create_web_user(self):
        # A Couch user is required for logout
        user = WebUser.create('', USERNAME, 'mockmock', None, None)
        user.save()
        self.addCleanup(user.delete, '', deleted_by=None)

    def login(self, password='mockmock'):
        self.client.post(reverse('login'), {
            'auth-username': USERNAME,
            'auth-password': password,
            'hq_login_view-current_step': 'auth',
        })

    def test_login(self):
        self.create_user()
        self.login()

        login_count = AccessAudit.objects.filter(user=USERNAME).count()
        self.assertEqual(1, login_count)
        latest_audit = get_latest_access(USERNAME)
        self.assertEqual(latest_audit.access_type, models.ACCESS_LOGIN)

    def test_login_failed(self):
        raise SkipTest("AccessAudit.audit_login_failed is broken")  # FIXME
        # AttributeError: 'NoneType' object has no attribute 'META'
        self.create_user()
        self.login('wrongwrongwrong')

        login_count = AccessAudit.objects.filter(user=USERNAME).count()
        self.assertEqual(1, login_count)
        latest_audit = get_latest_access(USERNAME)
        self.assertEqual(latest_audit.access_type, models.ACCESS_FAILED)

    def test_logout_authenticated_user(self):
        self.create_web_user()
        self.login()

        self.client.post(reverse('logout'))
        logout_count = AccessAudit.objects.filter(user=USERNAME).count()
        self.assertEqual(2, logout_count)

        latest_audit = get_latest_access(USERNAME)
        self.assertEqual(latest_audit.access_type, models.ACCESS_LOGOUT)


def get_latest_access(username):
    return AccessAudit.objects.filter(user=username).order_by("-event_date")[:1][0]
