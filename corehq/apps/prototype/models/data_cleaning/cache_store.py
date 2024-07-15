import random

from django.core.cache import cache

from corehq.apps.prototype.utils import fake_data
from corehq.util.quickcache import quickcache


class BaseCacheStore:
    slug = None
    timeout = 24 * 60 * 60
    default_value = None

    def __init__(self, request):
        self.username = request.user.username

    @property
    def cache_key(self):
        return f"{self.username}:saas-prototype:{self.slug}"

    def set(self, data):
        cache.set(self.cache_key, data)

    def get(self):
        return cache.get(self.cache_key, self.default_value)


class VisibleColumnStore(BaseCacheStore):
    slug = 'visible-column'
    default_value = [
        "full_name",
        "color",
        "big_cat",
        "submitted_on",
        "app",
        "status",
    ]


class FilterColumnStore(BaseCacheStore):
    slug = 'filter-column-test-001'
    default_value = []


class FakeCaseDataStore(BaseCacheStore):
    slug = 'prototype-case-data-store'

    @property
    def default_value(self):
        return _get_fake_data(100)


@quickcache(['num_entries'])
def _get_fake_data(num_entries):
    rows = []
    status = ('open', 'closed')
    for row in range(0, num_entries):
        rows.append({
            "id": row,
            "selected": False,
            "full_name": f"{fake_data.get_first_name()} {fake_data.get_last_name()}",
            "color": fake_data.get_color(),
            "big_cat": fake_data.get_big_cat(),
            "planet": fake_data.get_planet(),
            "submitted_on": fake_data.get_past_date(),
            "app": fake_data.get_fake_app(),
            "status": random.choice(status),
        })
    return rows
