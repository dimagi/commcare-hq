"""OCS message usage for HQ users, cached per UTC calendar month."""

from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.cache import cache

from corehq.apps.hqwebapp.exceptions import ChatUsageUnavailable

# Longer than any calendar month
_CACHE_TIMEOUT = 60 * 60 * 24 * 32
_USAGE_URL = 'https://www.openchatstudio.com/api/v2/usage/'


def _cache_key(user_id):
    current_month = datetime.now(timezone.utc).strftime('%Y-%m')
    return f'ocs-chat-usage:{user_id}:{current_month}'


def get_cached_chat_usage(user_id):
    return _get_cached_chat_usage(user_id, _cache_key(user_id))


def increment_chat_usage(user_id):
    key = _cache_key(user_id)
    try:
        return cache.incr(key)
    except ValueError:
        # The sent event fires after OCS has the message; its count includes it.
        return _get_cached_chat_usage(user_id, key)


def _get_cached_chat_usage(user_id, key):
    used = cache.get(key)
    if used is None:
        used = fetch_chat_usage_from_ocs(user_id)
        cache.add(key, used, timeout=_CACHE_TIMEOUT)
        # Preserve any count incremented by another request during the fetch.
        used = cache.get(key, default=used)
    return used


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

    cache.set(_cache_key(user_id), used, timeout=_CACHE_TIMEOUT)
    return used
