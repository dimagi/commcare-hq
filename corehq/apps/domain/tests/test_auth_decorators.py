from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, TestCase, RequestFactory

from corehq.apps.domain.decorators import _login_or_challenge
from corehq.apps.domain.shortcuts import create_domain, create_user
from corehq.apps.users.models import WebUser, CommCareUser

SUCCESS = 'it worked!'
CHECK_FAILED = 'check failed'


def sample_view(request, *args, **kwargs):
    return SUCCESS


def challenge(check):
    def decorator(view):
        def wrapper(request, *args, **kwargs):
            auth = check(request)
            if auth:
                return view(request, *args, **kwargs)

            return CHECK_FAILED
        return wrapper
    return decorator


passing_decorator = challenge(lambda request: True)
failing_decorator = challenge(lambda request: False)


class LoginOrChallengeTest(SimpleTestCase):

    def test_challenge(self):
        request = object()

        test = passing_decorator(sample_view)
        self.assertEqual('it worked!', test(request))

        test = failing_decorator(sample_view)
        self.assertEqual(CHECK_FAILED, test(request))


class LoginOrChallengeDBTest(TestCase):
    domain_name = 'auth-challenge-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.web_user = WebUser.create(cls.domain_name, 'test@dimagi.com', 'secret', None, None)
        cls.web_django_user = cls.web_user.get_django_user()
        cls.commcare_user = CommCareUser.create(cls.domain_name, 'test', 'secret', None, None)
        cls.commcare_django_user = cls.commcare_user.get_django_user()

    @classmethod
    def tearDownClass(cls):
        # domain deletion also deletes users and such
        cls.domain.delete()
        super().tearDownClass()

    def _get_request(self, user):
        request = RequestFactory().get('/foobar/')
        request.user = user
        return request

    def test_no_user_set(self):
        # no matter what, no user = no success
        for allow_cc_users in (True, False):
            for allow_sessions in (True, False):
                for require_domain in (True, False):
                    decorator = _login_or_challenge(passing_decorator,
                                                    allow_cc_users=allow_cc_users,
                                                    allow_sessions=allow_sessions,
                                                    require_domain=require_domain)
                    test = decorator(sample_view)
                    request = self._get_request(user=AnonymousUser())
                    self.assertNotEqual(SUCCESS, test(request, self.domain_name))

    def test_no_cc_users_no_sessions(self):
        decorator = _login_or_challenge(passing_decorator, allow_cc_users=False, allow_sessions=False)
        test = decorator(sample_view)

        request = self._get_request(self.web_django_user)
        self.assertEqual(SUCCESS, test(request, self.domain_name))

        request = self._get_request(self.commcare_django_user)
        self.assertNotEqual(SUCCESS, test(request, self.domain_name))

    def test_no_cc_users_with_sessions(self):
        decorator = _login_or_challenge(passing_decorator, allow_cc_users=False, allow_sessions=True)
        test = decorator(sample_view)

        request = self._get_request(self.web_django_user)
        self.assertEqual(SUCCESS, test(request, self.domain_name))

        request = self._get_request(self.commcare_django_user)
        # note: this behavior is surprising and arguably incorrect, but just documenting it here for now
        self.assertEqual(SUCCESS, test(request, self.domain_name))

    def test_with_cc_users(self):
        with_sessions = _login_or_challenge(passing_decorator, allow_cc_users=True, allow_sessions=True)
        no_sessions = _login_or_challenge(passing_decorator, allow_cc_users=True, allow_sessions=False)
        for decorator in [with_sessions, no_sessions]:
            test = decorator(sample_view)
            request = self._get_request(self.web_django_user)
            self.assertEqual(SUCCESS, test(request, self.domain_name))

            request = self._get_request(self.commcare_django_user)
            self.assertEqual(SUCCESS, test(request, self.domain_name))

    def test_no_domain_no_sessions(self):
        decorator = _login_or_challenge(passing_decorator, allow_cc_users=True, allow_sessions=False,
                                        require_domain=False)
        test = decorator(sample_view)

        request = self._get_request(self.web_django_user)
        self.assertEqual(SUCCESS, test(request))

        request = self._get_request(self.commcare_django_user)
        self.assertEqual(SUCCESS, test(request))

    def test_no_domain_with_sessions(self):
        decorator = _login_or_challenge(passing_decorator, allow_cc_users=True, allow_sessions=True,
                                        require_domain=False)
        test = decorator(sample_view)

        request = self._get_request(self.web_django_user)
        self.assertEqual(SUCCESS, test(request))

        request = self._get_request(self.commcare_django_user)
        self.assertEqual(SUCCESS, test(request))
