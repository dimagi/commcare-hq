from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.urls import reverse

import pytest
from oauth2_provider.models import (
    AbstractApplication,
    get_application_model,
    get_grant_model,
)

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.forms import HQAllowForm
from corehq.apps.users.models import WebUser


class TestHQAllowForm:

    def build_form(self, domain_choices=None, **data):
        return HQAllowForm(
            data={
                'client_id': 'test-client-id',
                'response_type': 'code',
                'redirect_uri': 'https://example.com/callback',
                'scope': 'access_apis',
                **data,
            },
            domain_choices=domain_choices or [
                ('alpha', 'Alpha Project'),
                ('beta', 'Beta Project'),
            ],
        )

    def test_domain_choices(self):
        form = self.build_form(
            domain_choices=[
                ('gamma', 'Gamma Project'),
                ('delta', 'Delta Project'),
            ]
        )
        assert form.fields['domains'].choices == [
            ('gamma', 'Gamma Project'),
            ('delta', 'Delta Project'),
        ]

    @pytest.mark.parametrize('requested, chosen, granted', [
        ('access_apis', ['alpha'], 'access_apis domain:alpha'),
        ('access_apis', ['alpha', 'beta'], 'access_apis domain:alpha domain:beta'),
        ('access_apis domain:beta', ['alpha'], 'access_apis domain:alpha'),
    ])
    def test_chosen_project_spaces_become_scopes(self, requested, chosen, granted):
        form = self.build_form(scope=requested, allow='Authorize', domains=chosen)
        assert form.is_valid(), form.errors
        assert form.cleaned_data['scope'] == granted

    def test_authorizing_requires_a_project_space(self):
        form = self.build_form(allow='Authorize')
        assert not form.is_valid()
        assert 'domains' in form.errors

    def test_cancelling_does_not_require_a_project_space(self):
        """
        Cancel and Authorize submit the same form; Cancel just omits "allow".
        """
        form = self.build_form()
        assert form.is_valid(), form.errors

    def test_a_project_space_the_user_does_not_have_is_rejected(self):
        form = self.build_form(allow='Authorize', domains=['not-mine'])
        assert not form.is_valid()
        assert 'domains' in form.errors


class TestHQOAuthGrant(TestCase):
    domain = 'consent-test'
    username = 'consent@example.com'
    password = '***'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = Domain.get_or_create_with_name(cls.domain, is_active=True)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = WebUser.create(cls.domain, cls.username, cls.password, None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)
        cls.application = get_application_model().objects.create(
            name='Test Integration',
            client_id='test-client-id',
            client_type=AbstractApplication.CLIENT_CONFIDENTIAL,
            authorization_grant_type=AbstractApplication.GRANT_AUTHORIZATION_CODE,
            redirect_uris='https://example.com/callback',
            user=cls.user.get_django_user(),
        )
        cls.addClassCleanup(cls.application.delete)

    def test_oauth_grant_includes_chosen_domain_scope(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('oauth2_provider:authorize'), {
            'client_id': self.application.client_id,
            'response_type': 'code',
            'redirect_uri': 'https://example.com/callback',
            'scope': 'access_apis',
            'allow': 'Authorize',
            'domains': self.domain,
        })

        assert response.status_code == 302, response.status_code
        code = parse_qs(urlparse(response['Location']).query)['code'][0]
        assert get_grant_model().objects.get(code=code).scope == (
            f'access_apis domain:{self.domain}'
        )
