from unittest.mock import patch

from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path

from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_disabled, flag_enabled

from ..models import IPAccessConfig


def non_domain_view(request):
    return HttpResponse('non_domain_view')


def domain_view(request, domain):
    return HttpResponse('domain_view')


urlpatterns = [
    path('non_domain_view/', non_domain_view),
    path('a/<slug:domain>/', domain_view),
]


@override_settings(ROOT_URLCONF='corehq.apps.ip_access.tests.test_middleware')
@flag_enabled('IP_ACCESS_CONTROLS')
@patch('corehq.apps.ip_access.models.IPAccessConfig.is_allowed')
class TestIPAccessMiddleware(TestCase):
    domain = 'test-ip-access-middleware'

    @classmethod
    def setUpTestData(cls):
        IPAccessConfig.objects.create(domain=cls.domain)

        cls.username = 'username'
        cls.password = '*******'
        cls.user = WebUser.create(None, cls.username, cls.password, None, None)
        cls.addClassCleanup(cls.user.delete, None, deleted_by=None)

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

    def test_non_domain_skips_check(self, is_allowed):
        res = self.client.get('/non_domain_view/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_not_called()

    def test_allowed_domain_view(self, is_allowed):
        is_allowed.return_value = True
        res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_called_once()

    def test_disallowed_domain_view(self, is_allowed):
        is_allowed.return_value = False
        res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 451)
        is_allowed.assert_called_once()

    def test_other_domain(self, is_allowed):
        # Feature flag enabled, but no IPAccessConfig defined
        res = self.client.get('/a/other_domain/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_not_called()

    def test_no_feature_flag(self, is_allowed):
        with flag_disabled('IP_ACCESS_CONTROLS'):
            res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_not_called()

    def test_multiple_requests_one_check(self, is_allowed):
        is_allowed.return_value = True
        res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_called_once()

        res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_called_once()

    def test_multiple_requests_different_ips(self, is_allowed):
        IP_1 = "127.0.0.1"
        IP_2 = "192.0.2.10"
        is_allowed.return_value = True
        res = self.client.get(f'/a/{self.domain}/', REMOTE_ADDR=IP_1)
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_called_once_with(IP_1)

        res = self.client.get(f'/a/{self.domain}/', REMOTE_ADDR=IP_2)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(is_allowed.call_count, 2)
        is_allowed.assert_called_with(IP_2)

        self.assertEqual(
            self.client.session[f"hq_session_ips-{self.domain}"],
            [IP_1, IP_2],
        )

    def test_multiple_requests_different_domains(self, is_allowed):
        is_allowed.return_value = True
        res = self.client.get('/a/other_domain/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_not_called()

        res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_called_once()

    def test_different_domains_different_checks(self, is_allowed):
        is_allowed.return_value = True
        res = self.client.get(f'/a/{self.domain}/')
        self.assertEqual(res.status_code, 200)
        is_allowed.assert_called_once()

        domain_2 = 'another-domain-with-access-configured'
        IPAccessConfig.objects.create(domain=domain_2)
        res = self.client.get(f'/a/{domain_2}/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(is_allowed.call_count, 2)

        self.assertEqual(len(self.client.session[f"hq_session_ips-{self.domain}"]), 1)
        self.assertEqual(len(self.client.session[f"hq_session_ips-{domain_2}"]), 1)
