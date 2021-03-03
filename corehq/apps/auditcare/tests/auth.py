from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from freezegun import freeze_time

from .. import models
from ..models import AccessAudit, AuditEvent
from .testutils import delete_all, get_latest_access


class AuthenticationTestCase(TestCase):

    def setUp(self):
        super(AuthenticationTestCase, self).setUp()
        User.objects.all().delete()
        delete_all(AuditEvent, 'auditcare/all_events')
        self.client = Client()
        self._createUser()

    def _createUser(self):
        usr = User()
        usr.username = 'mockmock@mockmock.com'
        usr.set_password('mockmock')
        usr.first_name = 'mocky'
        usr.last_name = 'mock'
        usr.save()

    def testLogin(self):
        #login
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.client.post(reverse('auth_login'), {
            'username': 'mockmock@mockmock.com',
            'password': 'mockmock',
        })
        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count + 1, login_count)

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(latest_audit.access_type, models.ACCESS_LOGIN)

    def testSingleFailedLogin(self):
        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.client.post(reverse('auth_login'), {
            'username': 'mockmock@mockmock.com',
            'password': 'wrongwrongwrong',
        })

        login_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.assertEqual(start_count + 1, login_count)
        #got the basic count, now let's inspect this value to see what kind of result it is.

        latest_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(latest_audit.access_type, models.ACCESS_FAILED)
        self.assertEqual(latest_audit.failures_since_start, 1)

    @freeze_time(datetime.utcnow(), as_arg=True)
    def testRepeatedFailedLogin(frozen_time, self):
        from ..decorators import login
        login.FAILURE_LIMIT = 3
        login.LOCK_OUT_AT_FAILURE = True
        login.COOLOFF_TIME = timedelta(seconds=4)

        start_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
        self.client.post(reverse('auth_login'), {
            'username': 'mockmock@mockmock.com',
            'password': 'wrongwrongwrong',
        })

        firstlogin_count = AccessAudit.view(
            'auditcare/login_events', key=['user', 'mockmock@mockmock.com']
        ).count()
        self.assertEqual(start_count + 1, firstlogin_count)

        first_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(first_audit.access_type, models.ACCESS_FAILED)
        self.assertEqual(first_audit.failures_since_start, 1)
        start_failures = first_audit.failures_since_start

        for n in range(1, 3):
            #we are logging in within the cooloff period, so let's check to see if it doesn't increment.
            self.client.post(reverse('auth_login'), {
                'username': 'mockmock@mockmock.com',
                'password': 'wrongwrongwrong',
            })
            next_count = AccessAudit.view('auditcare/login_events', key=['user', 'mockmock@mockmock.com']).count()
            self.assertEqual(firstlogin_count, next_count)

            next_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
            self.assertEqual(next_audit.access_type, models.ACCESS_FAILED)
            self.assertEqual(next_audit.failures_since_start, n + start_failures)
            frozen_time.tick(timedelta(seconds=1))
        frozen_time.tick(timedelta(seconds=3))
        self.client.post(reverse('auth_login'), {
            'username': 'mockmock@mockmock.com',
            'password': 'wrongwrong',
        })
        cooled_audit = get_latest_access(['user', 'mockmock@mockmock.com'])
        self.assertEqual(cooled_audit.failures_since_start, 1)
