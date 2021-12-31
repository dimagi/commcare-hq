from django.test import TestCase
from unittest.mock import patch
from datetime import date, timedelta

from corehq.apps.users.models import CouchUser

from ..signals import add_failed_attempt
from .. import signals


class FakeUser(CouchUser):
    def __init__(self, is_web_user=True, **kwargs):
        super().__init__(**kwargs)
        self.doc_type = 'WebUser' if is_web_user else 'CommCareUser'

    def save(self):
        pass


class TestFailedLoginSignal(TestCase):
    def test_failed_login_increments_failure_count(self):
        user = FakeUser(attempt_date=date.today(), login_attempts=1)
        credentials = {'username': 'test-user'}

        with patch.object(signals.CouchUser, 'get_by_username', return_value=user):
            add_failed_attempt(None, credentials)

        self.assertEqual(user.login_attempts, 2)

    def test_resets_login_failures_daily(self):
        yesterday = date.today() - timedelta(days=1)
        user = FakeUser(attempt_date=yesterday, login_attempts=4)
        credentials = {'username': 'test-user'}

        with patch.object(signals.CouchUser, 'get_by_username', return_value=user):
            add_failed_attempt(None, credentials)

        self.assertEqual(user.login_attempts, 1)

    def test_failed_logins_increment_count_beyond_max(self):
        user = FakeUser(attempt_date=date.today(), login_attempts=5000)
        credentials = {'username': 'test-user'}

        with patch.object(signals.CouchUser, 'get_by_username', return_value=user):
            add_failed_attempt(None, credentials)

        self.assertEqual(user.login_attempts, 5001)
