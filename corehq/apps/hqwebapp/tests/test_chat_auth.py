from contextlib import contextmanager
from datetime import date

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

import requests_mock

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqwebapp import chat_auth, chat_usage
from corehq.apps.hqwebapp.chat_quota import CHATBOT_MESSAGE_QUOTA_BY_EDITION
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@override_settings(
    ENTERPRISE_MODE=False,
    OCS_API_KEY='usage-key',
    OCS_OAUTH_CLIENT_ID='client-id',
    OCS_OAUTH_CLIENT_SECRET='client-secret',
)
@flag_enabled('OCS_CHATBOT_PAGE_CONTEXT')
class ChatAuthTokenTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.standard_domain = create_domain('test-domain')
        cls.free_domain = create_domain('test-free-domain')
        _subscribe_domain(cls.standard_domain.name, SoftwarePlanEdition.STANDARD)
        _subscribe_domain(cls.free_domain.name, SoftwarePlanEdition.FREE)
        for project in (cls.standard_domain, cls.free_domain):
            cls.addClassCleanup(
                Subscription._get_active_subscription_by_domain.clear,
                Subscription, project.name,
            )
            cls.addClassCleanup(project.delete)

    @contextmanager
    def mock_auth_token_request(self):
        with requests_mock.Mocker() as http:
            http.post(chat_auth._TOKEN_URL, json={'access_token': 'widget-token'})
            yield http

    def _make_user(self, username, domain):
        user = WebUser.create(
            domain,
            username,
            'password',
            created_by=None,
            created_via=None,
        )
        self.addCleanup(user.delete, domain, deleted_by=None)
        self.addCleanup(cache.delete, chat_usage._cache_key(user.user_id))
        return user

    def test_zero_quota_returns_403_without_calling_ocs(self):
        user = self._make_user('test@example.com', self.free_domain.name)
        with self.mock_auth_token_request() as http:
            response = _call_chat_token(user)
            assert response.status_code == 403
            assert response.content == b''
            assert not http.called

    def test_usage_below_limit_returns_token(self):
        user = self._make_user('test@example.com', self.standard_domain.name)
        limit = CHATBOT_MESSAGE_QUOTA_BY_EDITION[SoftwarePlanEdition.STANDARD]
        with self.mock_auth_token_request() as http:
            http.get(
                chat_usage._USAGE_URL,
                json={'results': {'messages': {'human': limit - 1}}},
            )
            response = _call_chat_token(user)
            assert response.status_code == 200
            assert response.content == b'widget-token'
            assert http.call_count == 2

    def test_usage_at_limit_returns_403(self):
        user = self._make_user('test@example.com', self.standard_domain.name)
        limit = CHATBOT_MESSAGE_QUOTA_BY_EDITION[SoftwarePlanEdition.STANDARD]
        with self.mock_auth_token_request() as http:
            http.get(
                chat_usage._USAGE_URL,
                json={'results': {'messages': {'human': limit}}},
            )
            response = _call_chat_token(user)
            assert response.status_code == 403
            assert response.content == b''
            assert http.call_count == 1  # fetch usage only

    def test_unlimited_returns_plain_text_token(self):
        user = self._make_user('staff@dimagi.com', self.standard_domain.name)
        with self.mock_auth_token_request() as http:
            response = _call_chat_token(user)
            assert response.status_code == 200
            assert response.content == b'widget-token'
            assert http.call_count == 1


def _subscribe_domain(domain_name, edition):
    account = BillingAccount.get_or_create_account_by_domain(
        domain_name,
        created_by='test@example.com',
    )[0]
    subscriber, _ = Subscriber.objects.get_or_create(domain=domain_name)
    Subscription.visible_objects.bulk_create(
        [
            Subscription(
                account=account,
                subscriber=subscriber,
                plan_version=DefaultProductPlan.get_default_plan_version(
                    edition=edition
                ),
                date_start=date.today(),
                is_active=True,
            )
        ]
    )
    Subscription._get_active_subscription_by_domain.clear(
        Subscription, domain_name
    )


def _call_chat_token(couch_user):
    request = RequestFactory().post(reverse('chat_token'))
    request.user = couch_user.get_django_user()
    request.couch_user = couch_user
    return chat_auth.chat_token(request)
