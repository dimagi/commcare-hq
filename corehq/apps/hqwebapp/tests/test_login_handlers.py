from django.test import RequestFactory, TestCase
from freezegun import freeze_time
from django.contrib.auth.models import User
from corehq.apps.hqwebapp.models import UserAccessLog

from corehq.apps.hqwebapp.login_handlers import handle_failed_login, \
    handle_login, handle_logout, handle_access_event


class TestLoginAccessHandler(TestCase):
    def test_missing_user_agent_is_set_as_unknown(self):
        factory = RequestFactory()
        request = factory.post('/login')

        handle_access_event('some_event', request, 'test_user')

        log_entry = UserAccessLog.objects.filter(user_id='test_user').first()
        self.assertEqual(log_entry.user_agent, '<unknown>')


class TestHandleLogin(TestCase):
    @freeze_time('2020-01-02 03:20:15')
    def test_login_stores_correct_fields_in_database(self):
        factory = RequestFactory()
        user = User(username='test_user')
        request = factory.post('/login')
        request.META['HTTP_USER_AGENT'] = 'Mozilla'

        handle_login('any_source', request, user)

        log_entry = UserAccessLog.objects.filter(user_id='test_user').first()
        self.assertEqual(log_entry.action, 'login')
        self.assertEqual(log_entry.user_id, 'test_user')
        self.assertEqual(log_entry.ip, '127.0.0.1')
        self.assertEqual(log_entry.user_agent, 'Mozilla')
        self.assertEqual(log_entry.path, '/login')
        self.assertEqual(str(log_entry.timestamp), '2020-01-02 03:20:15')


class TestHandleLogout(TestCase):
    @freeze_time('2020-01-02 03:20:15')
    def test_logout_stores_correct_fields_in_database(self):
        factory = RequestFactory()
        user = User(username='test_user')
        request = factory.post('/logout')
        request.META['HTTP_USER_AGENT'] = 'Mozilla'

        handle_logout('any_source', request, user)

        log_entry = UserAccessLog.objects.filter(user_id='test_user').first()
        self.assertEqual(log_entry.action, 'logout')
        self.assertEqual(log_entry.user_id, 'test_user')
        self.assertEqual(log_entry.ip, '127.0.0.1')
        self.assertEqual(log_entry.user_agent, 'Mozilla')
        self.assertEqual(log_entry.path, '/logout')
        self.assertEqual(str(log_entry.timestamp), '2020-01-02 03:20:15')


class TestHandleFailedLogin(TestCase):
    @freeze_time('2020-01-02 03:20:15')
    def test_logout_stores_correct_fields_in_database(self):
        factory = RequestFactory()
        request = factory.post('/login')
        request.META['HTTP_USER_AGENT'] = 'Mozilla'
        credentials = {'username': 'fake_user'}

        handle_failed_login('any_source', credentials, request)

        log_entry = UserAccessLog.objects.filter(user_id='fake_user').first()
        self.assertEqual(log_entry.action, 'failure')
        self.assertEqual(log_entry.user_id, 'fake_user')
        self.assertEqual(log_entry.ip, '127.0.0.1')
        self.assertEqual(log_entry.user_agent, 'Mozilla')
        self.assertEqual(log_entry.path, '/login')
        self.assertEqual(str(log_entry.timestamp), '2020-01-02 03:20:15')
