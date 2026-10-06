from datetime import date

from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.urls import reverse

import pytest
import requests_mock
from unmagic import use

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqwebapp import chat_auth, chat_usage
from corehq.apps.users.models import WebUser


@use('db')
@override_settings(ENTERPRISE_MODE=False)
def test_zero_quota_returns_403_without_calling_ocs():
    user = _create_web_user('test@example.com')
    try:
        with requests_mock.Mocker() as http:
            response = chat_auth.chat_token(_token_request(user))
            assert response.status_code == 403
            assert response.content == b''
            assert not http.called
    finally:
        user.delete(None, deleted_by=None)


@use('db')
@pytest.mark.parametrize(
    ('used', 'status'),
    [
        (29, 200),  # used < limit (Standard = 30)
        (30, 403),  # used == limit
    ],
)
@override_settings(
    ENTERPRISE_MODE=False,
    OCS_API_KEY='usage-key',
    OCS_OAUTH_CLIENT_ID='client-id',
    OCS_OAUTH_CLIENT_SECRET='client-secret',
)
def test_usage_against_limit(used, status):
    domain = create_domain('test-domain')
    _subscribe_domain_to_standard_plan(domain.name)
    user = _create_web_user('test@example.com', domain=domain.name)
    try:
        with requests_mock.Mocker() as http:
            http.get(
                chat_usage._USAGE_URL,
                json={'results': {'messages': {'human': used}}},
            )
            http.post(
                chat_auth._TOKEN_URL, json={'access_token': 'widget-token'}
            )
            response = chat_auth.chat_token(_token_request(user))
            assert response.status_code == status
            if status == 200:
                assert response.content == b'widget-token'
                assert http.call_count == 2
            else:
                assert response.content == b''
                assert http.call_count == 1  # fetch usage only
    finally:
        cache.delete(chat_usage._cache_key(user.user_id))
        user.delete(domain.name, deleted_by=None)
        Subscription._get_active_subscription_by_domain.clear(
            Subscription, domain.name
        )
        domain.delete()


@use('db')
@override_settings(
    ENTERPRISE_MODE=False,
    OCS_OAUTH_CLIENT_ID='client-id',
    OCS_OAUTH_CLIENT_SECRET='client-secret',
)
def test_unlimited_returns_plain_text_token():
    user = _create_web_user('staff@dimagi.com')
    try:
        with requests_mock.Mocker() as http:
            http.post(
                chat_auth._TOKEN_URL, json={'access_token': 'widget-token'}
            )
            response = chat_auth.chat_token(_token_request(user))
            assert response.status_code == 200
            assert response.content == b'widget-token'
            assert http.call_count == 1
    finally:
        user.delete(None, deleted_by=None)


def _create_web_user(username, domain=None):
    return WebUser.create(
        domain,
        username,
        'password',
        created_by=None,
        created_via=None,
    )


def _subscribe_domain_to_standard_plan(domain_name):
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
                    edition=SoftwarePlanEdition.STANDARD
                ),
                date_start=date.today(),
                is_active=True,
            )
        ]
    )
    Subscription._get_active_subscription_by_domain.clear(
        Subscription, domain_name
    )


def _token_request(couch_user):
    request = RequestFactory().post(reverse('chat_token'))
    request.user = couch_user.get_django_user()
    request.couch_user = couch_user
    return request
