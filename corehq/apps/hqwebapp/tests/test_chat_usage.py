from datetime import datetime, timezone
from uuid import uuid4

from django.core.cache import cache
from django.test import override_settings

import requests_mock
import time_machine

from corehq.apps.hqwebapp import chat_usage
from corehq.apps.users.models import WebUser


def make_user():
    user_id = uuid4().hex
    return WebUser(
        _id=user_id,
        username=f'chat-usage-{user_id}@example.com',
    )


def clear_usage(user, *months):
    for month in months or (datetime.now(timezone.utc).strftime('%Y-%m'),):
        cache.delete(f'ocs-chat-usage:{user.user_id}:{month}')


def stub_ocs_response(http, used):
    http.get(
        chat_usage._USAGE_URL,
        json={'results': {'messages': {'human': used}}},
    )


@override_settings(OCS_API_KEY='test-key')
def test_cache_miss_seeds_from_ocs():
    user = make_user()
    with requests_mock.Mocker() as http:
        stub_ocs_response(http, 7)

        assert chat_usage.get_cached_chat_usage(user.user_id) == 7
        assert chat_usage.get_cached_chat_usage(user.user_id) == 7
        assert http.call_count == 1

    clear_usage(user)


@override_settings(OCS_API_KEY='test-key')
def test_increment_usage():
    user = make_user()
    with requests_mock.Mocker() as http:
        stub_ocs_response(http, 1)

        # First call: key missing, so seed from OCS (count already includes this message).
        assert chat_usage.increment_chat_usage(user.user_id) == 1
        assert http.call_count == 1

        # Later calls: atomic local incr, no OCS.
        assert chat_usage.increment_chat_usage(user.user_id) == 2
        assert chat_usage.increment_chat_usage(user.user_id) == 3
        assert chat_usage.get_cached_chat_usage(user.user_id) == 3
        assert http.call_count == 1

    clear_usage(user)


@override_settings(OCS_API_KEY='test-key')
def test_usage_is_separate_by_utc_month():
    user = make_user()
    with time_machine.travel('2026-10-31 23:59:59+00:00', tick=False) as clock:
        with requests_mock.Mocker() as http:
            stub_ocs_response(http, 1)
            assert chat_usage.increment_chat_usage(user.user_id) == 1

        clock.shift(1)  # into November
        with requests_mock.Mocker() as http:
            stub_ocs_response(http, 0)
            assert chat_usage.get_cached_chat_usage(user.user_id) == 0
            assert chat_usage.increment_chat_usage(user.user_id) == 1
            assert chat_usage.increment_chat_usage(user.user_id) == 2


        clock.shift(-1)  # back to October
        assert chat_usage.get_cached_chat_usage(user.user_id) == 1

    clear_usage(user, '2026-10', '2026-11')


@override_settings(OCS_API_KEY='test-key')
def test_refresh_replaces_cached_usage():
    user_a = make_user()
    user_b = make_user()

    with requests_mock.Mocker() as http:
        stub_ocs_response(http, 1)
        assert chat_usage.increment_chat_usage(user_a.user_id) == 1

    for used in (12, 15, 0):
        with requests_mock.Mocker() as http:
            stub_ocs_response(http, used)
            assert chat_usage.fetch_chat_usage_from_ocs(user_a.user_id) == used
            assert chat_usage.get_cached_chat_usage(user_a.user_id) == used

    with requests_mock.Mocker() as http:
        stub_ocs_response(http, 0)
        assert chat_usage.get_cached_chat_usage(user_b.user_id) == 0

    clear_usage(user_a)
    clear_usage(user_b)
