"""OCS message usage for HQ users, cached per UTC calendar month."""

from datetime import datetime, timezone

import requests
from django.conf import settings

from corehq.util.quickcache import quickcache

# Longer than any calendar month
_CACHE_TIMEOUT = 60 * 60 * 24 * 32
_USAGE_URL = 'https://openchatstudio.com/api/v2/usage/'


class ChatUsageUnavailable(Exception):
    """OCS usage could not be obtained or validated."""


def _current_month():
    return datetime.now(timezone.utc).strftime('%Y-%m')


def get_cached_chat_usage(user_id):
    return _get_cached_chat_usage(user_id, _current_month())


def increment_chat_usage(user_id):
    current_month = _current_month()
    used = _get_cached_chat_usage(user_id, current_month) + 1
    _cached_chat_usage.set_cached_value(user_id, current_month).to(used)
    return used


def _get_cached_chat_usage(user_id, current_month):
    cached_usage = _cached_chat_usage.get_cached_value(user_id, current_month)
    # If the cache is not set, return 0
    if cached_usage is Ellipsis:
        cached_usage = 0
    return cached_usage


def fetch_chat_usage_from_ocs(user_id):
    api_key = settings.OCS_API_KEY
    if not user_id or not api_key:
        raise ChatUsageUnavailable(
            'Missing user identity or OCS usage configuration'
        )

    try:
        response = requests.get(
            _USAGE_URL,
            headers={'X-api-key': api_key},
            params={
                'metric': 'messages',
                'participant_remote_id': user_id,
                'platform': 'embedded_widget',
                'period': 'current_month',
                'tz': 'UTC',
            },
            timeout=(5, 15),
        )
        if response.status_code != 200:
            raise ChatUsageUnavailable('OCS usage request failed')
        used = response.json()['results']['messages']['human']
        assert used >= 0
    except (requests.RequestException, ValueError, KeyError, TypeError, AssertionError) as exc:
        raise ChatUsageUnavailable(
            'Invalid or unavailable OCS usage response'
        ) from exc

    _cached_chat_usage.set_cached_value(user_id, _current_month()).to(used)
    return used


@quickcache(['user_id', 'current_month'], timeout=_CACHE_TIMEOUT)
def _cached_chat_usage(user_id, current_month):
    """Keyed cache for monthly usage; use get/set_cached_value instead of calling."""
    raise AssertionError('_cached_chat_usage should not be called directly')
