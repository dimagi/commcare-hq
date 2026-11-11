from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from django.contrib.messages import get_messages
from django.test import RequestFactory, TestCase
from django.test.client import Client
from django.urls import reverse
from django.utils.html import escape
from django.utils.http import urlencode

from corehq.apps.accounting.models import DefaultProductPlan
from corehq.apps.domain.models import Domain
from corehq.apps.registration.models import (
    RegistrationRequest,
    SelfSignupWorkflow,
)
from corehq.apps.registration.views import (
    _get_domain_registered_redirect_url,
    eula_agreement,
)
from corehq.apps.users.models import WebUser


class TestConfirmDomainView(TestCase):

    def setUp(self):
        super().setUp()
        self.domain = Domain(name='the-name-of-a-domain', is_active=False)
        self.domain.save()
        self.addCleanup(self.domain.delete)

        self.user = WebUser.create(self.domain.name, 'test-user', 'password', None, None, 'testy@example.com')
        self.addCleanup(self.user.delete, self.domain.name, deleted_by=None)

        self.client = Client()
        self.client.force_login(self.user.get_django_user())
        self.client.defaults.update({'plan': DefaultProductPlan.get_default_plan_version()})

    def tearDown(self):
        SelfSignupWorkflow.get_in_progress_for_domain.clear(SelfSignupWorkflow, self.domain.name)
        super().tearDown()

    def create_registration_request(self, guid):
        reg_request = RegistrationRequest.objects.create(
            request_time=datetime.now(),
            activation_guid=guid,
            domain=self.domain.name,
            new_user_username=self.user.username
        )
        self.addCleanup(reg_request.delete)

    @staticmethod
    def url(guid=None):
        url = reverse('registration_confirm_domain')
        if guid:
            url += f'{guid}/'
        return url

    def test_confirm_domain(self):
        guid = 'abc123'
        self.create_registration_request(guid)

        response = self.client.get(self.url(guid))
        self.assertRedirects(response, reverse('dashboard_domain', args=[self.domain.name]))

        domain = Domain.get_by_name(self.domain.name)
        self.assertTrue(domain.is_active)

    def test_no_guid(self):
        response = self.client.get(self.url())
        self.assertTemplateUsed(response, 'registration/confirmation_error.html')

        expected_message = 'An account activation key was not provided.'
        self.assertIn(expected_message, response.content.decode())

    def test_bad_guid(self):
        bad_guid = 'bad456'
        response = self.client.get(self.url(bad_guid))
        self.assertTemplateUsed(response, 'registration/confirmation_error.html')

        expected_message = escape(f'The account activation key "{bad_guid}" provided is invalid.')
        self.assertIn(expected_message, response.content.decode())

    def test_domain_already_confirmed(self):
        guid = 'abc123'
        self.create_registration_request(guid)
        self.client.get(self.url(guid))

        response = self.client.get(self.url(guid))
        self.assertRedirects(response, reverse('dashboard_domain', args=[self.domain.name]))

        messages = list(get_messages(response.wsgi_request))
        self.assertIn(
            f'Your account {self.user.username} has already been activated',
            messages[1].message
        )


@pytest.mark.parametrize('next_url, referer, expected', [
    ('/a/test-domain/next/', '/settings/projects/', '/a/test-domain/next/'),
    ('https://example.com/', '/settings/projects/', '/settings/projects/'),
    ('https://example.com/', 'https://example.com/', None),
    ('//example.com/', None, None),
    (None, '/settings/projects/', '/settings/projects/'),
    (None, 'https:///example.com/', None),
    (None, None, None),
])
def test_domain_registered_redirect_url(next_url, referer, expected):
    query = {'referer': referer} if referer is not None else {}
    data = {'next': next_url} if next_url is not None else {}
    request = RequestFactory().post(
        reverse('registration_domain') + '?' + urlencode(query), data,
    )
    if expected is None:
        expected = reverse('domain_homepage', args=['test-domain'])
    assert _get_domain_registered_redirect_url(request, 'test-domain') == expected


@pytest.mark.parametrize('next_url, expected', [
    ('/a/test-domain/', '/a/test-domain/'),
    ('https://example.com/', '/'),
    (None, '/'),
])
def test_eula_agreement_redirect(next_url, expected):
    data = {'next': next_url} if next_url is not None else {}
    request = RequestFactory().post(reverse('agree_to_eula'), data)
    request.user = Mock()
    with patch('corehq.apps.registration.views.CouchUser.from_django_user'):
        response = eula_agreement(request)
    assert response.status_code == 302
    assert response['Location'] == expected
