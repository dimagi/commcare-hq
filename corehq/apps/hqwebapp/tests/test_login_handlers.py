from django.test import RequestFactory, TestCase
from time_machine import travel
from django.contrib.auth.models import User
from corehq.apps.hqwebapp.models import UserAccessLog

from corehq.apps.hqwebapp.login_handlers import handle_failed_login, \
    handle_login, handle_logout, _handle_access_event


class TestLoginAccessHandler(TestCase):
    def test_missing_user_agent_is_set_as_empty(self):
        factory = RequestFactory()
        request = factory.post('/login')

        _handle_access_event('some_event', request, 'test_user')

        log_entry = UserAccessLog.objects.filter(user_id='test_user').first()
        self.assertIsNone(log_entry.user_agent)

    def test_missing_request_logs_empty_attributes(self):
        _handle_access_event('some_event', None, 'test_user')

        log_entry = UserAccessLog.objects.filter(user_id='test_user').first()
        self.assertIsNone(log_entry.ip)
        self.assertEqual(log_entry.path, '')
        self.assertIsNone(log_entry.user_agent)


class TestHandleLogin(TestCase):
    @travel('2020-01-02 03:20:15', tick=False)
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
    def setUp(self):
        factory = RequestFactory()
        self.request = factory.post('/logout')

    @travel('2020-01-02 03:20:15', tick=False)
    def test_logout_stores_correct_fields_in_database(self):
        user = User(username='test_user')
        self.request.META['HTTP_USER_AGENT'] = 'Mozilla'

        handle_logout('any_source', self.request, user)

        log_entry = UserAccessLog.objects.filter(user_id='test_user').first()
        self.assertEqual(log_entry.action, 'logout')
        self.assertEqual(log_entry.user_id, 'test_user')
        self.assertEqual(log_entry.ip, '127.0.0.1')
        self.assertEqual(log_entry.user_agent, 'Mozilla')
        self.assertEqual(log_entry.path, '/logout')
        self.assertEqual(str(log_entry.timestamp), '2020-01-02 03:20:15')

    def test_no_user_is_logged_with_empty_user_id(self):
        handle_logout('any_source', self.request, user=None)

        unknown_logouts = UserAccessLog.objects.filter(user_id='')
        self.assertEqual(unknown_logouts.count(), 1)


class TestHandleFailedLogin(TestCase):
    @travel('2020-01-02 03:20:15', tick=False)
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
