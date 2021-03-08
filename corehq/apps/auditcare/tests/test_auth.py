from unittest import SkipTest

from django.urls import reverse

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import Client

from corehq.apps.users.models import WebUser

from .. import models
from ..models import AccessAudit, AuditEvent
from .testutils import delete_all, get_latest_access


class TestAccessAudit(TestCase):

    def setUp(self):
        User.objects.all().delete()
        delete_all(AuditEvent, 'auditcare/all_events')
        self.client = Client()

    def create_user(self):
        usr = User()
        usr.username = 'mockmock@mockmock.com'
        usr.set_password('mockmock')
        usr.first_name = 'mocky'
        usr.last_name = 'mock'
        usr.save()

    def create_web_user(self):
        # A Couch user is required for logout
        user = WebUser.create('', 'mockmock@mockmock.com', 'mockmock', None, None)
        user.save()
        self.addCleanup(lambda: user.delete(None))

    def login(self, password='mockmock'):
        self.client.post(reverse('login'), {
            'auth-username': 'mockmock@mockmock.com',
            'auth-password': password,
            'hq_login_view-current_step': 'auth',
        })

    def test_login(self):
        self.create_user()
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.login()
        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count + 1, login_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(latest_audit.access_type, models.ACCESS_LOGIN)

    def test_login_failed(self):
        self.create_user()
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.login('wrongwrongwrong')

        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count + 1, login_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(latest_audit.access_type, models.ACCESS_FAILED)

    def test_logout_authenticated_user(self):
        self.create_web_user()
        self.login()
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()

        self.client.post(reverse('logout'))
        logout_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count + 1, logout_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(latest_audit.access_type, models.ACCESS_LOGOUT)

    def test_logout_unauthenticated_user(self):
        raise SkipTest("unauthenticated user logout causes a 500 error unlreated to what this is testing")
        self.create_web_user()
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()

        self.client.post(reverse('logout'))
        logout_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count + 1, logout_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(latest_audit.access_type, models.ACCESS_LOGOUT)
