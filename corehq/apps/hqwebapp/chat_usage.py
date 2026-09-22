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


def get_chat_usage(user_id, refresh=False):
    current_month = datetime.now(timezone.utc).strftime('%Y-%m')
    return _get_chat_usage(user_id, current_month, refresh)


@quickcache(
    ['user_id', 'current_month'], skip_arg='refresh', timeout=_CACHE_TIMEOUT
)
def _get_chat_usage(user_id, current_month, refresh=False):
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
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise ChatUsageUnavailable(
            'Invalid or unavailable OCS usage response'
        ) from exc

    return _validate_message_count(used)


def _validate_message_count(used):
    if type(used) is not int or used < 0:
        raise ChatUsageUnavailable('Invalid OCS message count')
    return used
