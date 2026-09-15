from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse

from corehq.apps.hqadmin.models import PlatformDeactivationLog
from corehq.apps.hqadmin.offboarding.clients import (
    AccountInfo,
    DatadogOffboardingClient,
    OffboardingClientError,
    SentryOffboardingClient,
)
from corehq.apps.hqadmin.offboarding.views import (
    execute_row,
    is_protected_email,
    lookup_row,
    validate_target_email,
)
from corehq.apps.users.models import WebUser

EMAIL = 'jane@dimagi.com'
ACCOUNT = AccountInfo('u-1', f'Jane Doe <{EMAIL}>')
INACTIVE_ACCOUNT = AccountInfo('u-1', f'Jane Doe <{EMAIL}>', is_active=False)

PLATFORMS = {
    'datadog': {'api_key': 'k', 'app_key': 'k'},
    'sentry': {'auth_token': 'k', 'org_slug': 'dimagi'},
    'sumologic': {'access_id': 'k', 'access_key': 'k'},
    'hubspot': {'access_token': 'k'},
}


def _patch_find(return_value=None, side_effect=None):
    return patch.object(DatadogOffboardingClient, 'find_account',
                        return_value=return_value, side_effect=side_effect)


def _patch_offboard(return_value='Disabled Datadog user Jane', side_effect=None):
    return patch.object(DatadogOffboardingClient, 'offboard',
                        return_value=return_value, side_effect=side_effect)


def _email_of_length(length):
    """An address Django's validator accepts, of exactly ``length`` characters."""
    domain = '.'.join(['b' * 63] * 2) + '.com'
    return 'a' * (length - len(domain) - 1) + '@' + domain


@pytest.mark.parametrize('raw, expected', [
    ('', ('', None)),
    ('   ', ('', None)),
    (' Jane@Dimagi.COM ', ('jane@dimagi.com', None)),
    ('not-an-email', ('not-an-email', 'Enter a valid email address.')),
    (_email_of_length(254), (_email_of_length(254), None)),
    (_email_of_length(255), (_email_of_length(255), 'Enter a valid email address.')),
])
def test_validate_target_email(raw, expected):
    assert validate_target_email(raw) == expected


@override_settings(OFFBOARDING_PROTECTED_EMAILS=['Shared-Ops@dimagi.com', 'root@dimagi.com'])
@pytest.mark.parametrize('email, expected', [
    ('shared-ops@dimagi.com', True),
    (' SHARED-OPS@Dimagi.com ', True),
    ('root@dimagi.com', True),
    ('jane@dimagi.com', False),
    ('', False),
])
def test_is_protected_email(email, expected):
    assert is_protected_email(email) is expected


@override_settings(OFFBOARDING_PROTECTED_EMAILS=[])
def test_is_protected_email_with_empty_list():
    assert is_protected_email('jane@dimagi.com') is False


@override_settings(OFFBOARDING_PLATFORMS={})
def test_lookup_row_not_configured_makes_no_request():
    with _patch_find() as find:
        row = lookup_row(DatadogOffboardingClient(), EMAIL)
    assert row.state == 'not_configured'
    find.assert_not_called()


@override_settings(OFFBOARDING_PLATFORMS=PLATFORMS)
@pytest.mark.parametrize('find_kwargs, expected_state, expected_label, expected_message', [
    ({'return_value': None}, 'not_found', '', ''),
    ({'return_value': ACCOUNT}, 'found', ACCOUNT.label, ''),
    ({'return_value': INACTIVE_ACCOUNT}, 'inactive', ACCOUNT.label, ''),
    ({'side_effect': OffboardingClientError('Datadog returned HTTP 503: down')}, 'error', '',
     'Datadog returned HTTP 503: down'),
])
def test_lookup_row_states(find_kwargs, expected_state, expected_label, expected_message):
    with _patch_find(**find_kwargs):
        row = lookup_row(DatadogOffboardingClient(), EMAIL)
    assert (row.state, row.label, row.message) == (expected_state, expected_label, expected_message)


@override_settings(OFFBOARDING_PLATFORMS=PLATFORMS)
class TestExecuteRow(TestCase):

    def test_success_is_logged(self):
        with _patch_find(ACCOUNT), _patch_offboard() as offboard:
            row = execute_row(DatadogOffboardingClient(), EMAIL, 'admin@dimagi.com')
        offboard.assert_called_once_with(ACCOUNT)
        assert (row.state, row.label, row.message) == (
            'done', ACCOUNT.label, 'Disabled Datadog user Jane')
        log = PlatformDeactivationLog.objects.get()
        assert (
            log.performed_by, log.target_email, log.platform, log.account_label, log.succeeded, log.detail,
        ) == ('admin@dimagi.com', EMAIL, 'datadog', ACCOUNT.label, True, 'Disabled Datadog user Jane')

    def test_failure_is_logged(self):
        error = OffboardingClientError('Datadog returned HTTP 403: forbidden')
        with _patch_find(ACCOUNT), _patch_offboard(side_effect=error):
            row = execute_row(DatadogOffboardingClient(), EMAIL, 'admin@dimagi.com')
        assert (row.state, row.message) == ('failed', 'Datadog returned HTTP 403: forbidden')
        log = PlatformDeactivationLog.objects.get()
        assert (log.succeeded, log.detail) == (False, 'Datadog returned HTTP 403: forbidden')

    def test_overlong_label_is_truncated_in_log(self):
        account = AccountInfo('u-1', 'x' * 300)
        with _patch_find(account), _patch_offboard():
            row = execute_row(DatadogOffboardingClient(), EMAIL, 'admin@dimagi.com')
        assert row.state == 'done'
        log = PlatformDeactivationLog.objects.get()
        assert len(log.account_label) == 255
        assert log.account_label.endswith('…')

    def test_lookup_error_skips_offboard_and_log(self):
        error = OffboardingClientError('Datadog returned HTTP 503: unavailable')
        with _patch_find(side_effect=error), _patch_offboard() as offboard:
            row = execute_row(DatadogOffboardingClient(), EMAIL, 'admin@dimagi.com')
        assert (row.state, row.message) == ('error', 'Datadog returned HTTP 503: unavailable')
        offboard.assert_not_called()
        assert not PlatformDeactivationLog.objects.exists()

    def test_missing_account_skips_offboard_and_log(self):
        with _patch_find(None), _patch_offboard() as offboard:
            row = execute_row(DatadogOffboardingClient(), EMAIL, 'admin@dimagi.com')
        assert row.state == 'not_found'
        offboard.assert_not_called()
        assert not PlatformDeactivationLog.objects.exists()

    def test_inactive_account_skips_offboard_and_log(self):
        with _patch_find(INACTIVE_ACCOUNT), _patch_offboard() as offboard:
            row = execute_row(DatadogOffboardingClient(), EMAIL, 'admin@dimagi.com')
        assert row.state == 'inactive'
        offboard.assert_not_called()
        assert not PlatformDeactivationLog.objects.exists()


@override_settings(OFFBOARDING_PLATFORMS=PLATFORMS)
class TestExternalPlatformOffboardingView(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.superuser = WebUser.create(None, 'super@dimagi.com', 'password', None, None, is_superuser=True)
        cls.addClassCleanup(cls.superuser.delete, None, None)
        cls.regular_user = WebUser.create(None, 'regular@dimagi.com', 'password', None, None)
        cls.addClassCleanup(cls.regular_user.delete, None, None)
        cls.url = reverse('offboard_external_platforms')

    def login(self, user):
        assert self.client.login(username=user.username, password='password')

    def test_non_superuser_is_redirected(self):
        self.login(self.regular_user)
        response = self.client.get(self.url)
        assert response.status_code == 302

    def test_non_superuser_cannot_execute(self):
        self.login(self.regular_user)
        response = self.client.post(self.url, {'email': EMAIL, 'platforms': ['datadog']},
                                    headers={'HQ-HX-Action': 'execute'})
        assert response.status_code == 302
        assert not PlatformDeactivationLog.objects.exists()

    def test_blank_page(self):
        self.login(self.superuser)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.context['rows'] == []
        assert b'platform-rows' not in response.content

    def test_invalid_email_shows_error_and_no_rows(self):
        self.login(self.superuser)
        response = self.client.get(self.url, {'email': 'nope'})
        assert response.status_code == 200
        assert response.context['email_error'] == 'Enter a valid email address.'
        assert response.context['rows'] == []

    def test_valid_email_renders_a_loading_row_per_platform(self):
        self.login(self.superuser)
        response = self.client.get(self.url, {'email': ' Jane@Dimagi.com '})
        assert response.status_code == 200
        rows = response.context['rows']
        assert [(r.client.slug, r.state) for r in rows] == [
            ('datadog', 'loading'), ('sentry', 'loading'), ('sumologic', 'loading'), ('hubspot', 'loading'),
        ]
        assert response.context['email'] == EMAIL
        assert response.context['is_dimagi_email'] is True
        assert response.context['platforms']['sentry'] == {'name': 'Sentry', 'verb': 'Remove', 'reversible': False}
        assert b'is not a dimagi.com address' not in response.content

    def test_non_dimagi_email_shows_warning(self):
        self.login(self.superuser)
        response = self.client.get(self.url, {'email': 'jane@contractor.org'})
        assert response.context['is_dimagi_email'] is False
        assert b'is not a dimagi.com address' in response.content

    def test_lookup_action_renders_found_row(self):
        self.login(self.superuser)
        with _patch_find(ACCOUNT):
            response = self.client.get(self.url, {'email': EMAIL, 'platform': 'datadog'},
                                       headers={'HQ-HX-Action': 'lookup'})
        assert response.status_code == 200
        assert response.context['row'].state == 'found'
        content = response.content.decode()
        assert 'name="platforms"' in content
        assert 'value="datadog"' in content
        assert 'Jane Doe &lt;jane@dimagi.com&gt;' in content

    def test_lookup_action_renders_error_row_with_retry(self):
        self.login(self.superuser)
        with _patch_find(side_effect=OffboardingClientError('Datadog returned HTTP 503: down')):
            response = self.client.get(self.url, {'email': EMAIL, 'platform': 'datadog'},
                                       headers={'HQ-HX-Action': 'lookup'})
        content = response.content.decode()
        assert 'Datadog returned HTTP 503: down' in content
        assert 'Retry' in content
        assert 'name="platforms"' not in content

    def test_lookup_action_rejects_unknown_platform(self):
        self.login(self.superuser)
        response = self.client.get(self.url, {'email': EMAIL, 'platform': 'myspace'},
                                   headers={'HQ-HX-Action': 'lookup'})
        assert response.status_code == 400

    def test_lookup_action_rejects_invalid_email(self):
        self.login(self.superuser)
        response = self.client.get(self.url, {'email': 'nope', 'platform': 'datadog'},
                                   headers={'HQ-HX-Action': 'lookup'})
        assert response.status_code == 400

    def test_execute_action_acts_only_on_selected_platforms(self):
        self.login(self.superuser)
        with _patch_find(ACCOUNT), _patch_offboard() as offboard, \
                patch.object(SentryOffboardingClient, 'find_account') as sentry_find:
            response = self.client.post(self.url, {'email': EMAIL, 'platforms': ['datadog']},
                                        headers={'HQ-HX-Action': 'execute'})
        assert response.status_code == 200
        offboard.assert_called_once_with(ACCOUNT)
        sentry_find.assert_not_called()
        states = [(ctx['row'].client.slug, ctx['row'].state) for ctx in response.context]
        assert states == [
            ('datadog', 'done'), ('sentry', 'loading'), ('sumologic', 'loading'), ('hubspot', 'loading')]
        log = PlatformDeactivationLog.objects.get()
        assert (log.performed_by, log.platform, log.succeeded) == ('super@dimagi.com', 'datadog', True)

    def test_execute_action_requires_a_selection(self):
        self.login(self.superuser)
        response = self.client.post(self.url, {'email': EMAIL}, headers={'HQ-HX-Action': 'execute'})
        assert response.status_code == 400
        assert not PlatformDeactivationLog.objects.exists()

    def test_execute_action_rejects_unknown_platform(self):
        self.login(self.superuser)
        response = self.client.post(self.url, {'email': EMAIL, 'platforms': ['datadog', 'myspace']},
                                    headers={'HQ-HX-Action': 'execute'})
        assert response.status_code == 400
        assert not PlatformDeactivationLog.objects.exists()

    @override_settings(OFFBOARDING_PROTECTED_EMAILS=[EMAIL])
    def test_protected_email_page_shows_warning_and_no_rows(self):
        self.login(self.superuser)
        response = self.client.get(self.url, {'email': EMAIL})
        assert response.status_code == 200
        assert response.context['is_protected_email'] is True
        assert response.context['rows'] == []
        assert b'is on the protected list' in response.content
        assert b'platform-rows' not in response.content

    @override_settings(OFFBOARDING_PROTECTED_EMAILS=[EMAIL])
    def test_protected_email_lookup_is_refused(self):
        self.login(self.superuser)
        with _patch_find(ACCOUNT) as find:
            response = self.client.get(self.url, {'email': EMAIL, 'platform': 'datadog'},
                                       headers={'HQ-HX-Action': 'lookup'})
        assert response.status_code == 403
        find.assert_not_called()

    @override_settings(OFFBOARDING_PROTECTED_EMAILS=[EMAIL])
    def test_protected_email_execute_is_refused(self):
        self.login(self.superuser)
        with _patch_find(ACCOUNT), _patch_offboard() as offboard:
            response = self.client.post(self.url, {'email': EMAIL, 'platforms': ['datadog']},
                                        headers={'HQ-HX-Action': 'execute'})
        assert response.status_code == 403
        offboard.assert_not_called()
        assert not PlatformDeactivationLog.objects.exists()

    def test_execute_without_action_header_is_not_allowed(self):
        self.login(self.superuser)
        response = self.client.post(self.url, {'email': EMAIL, 'platforms': ['datadog']})
        assert response.status_code == 405
