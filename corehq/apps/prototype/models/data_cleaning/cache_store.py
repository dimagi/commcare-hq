import copy
import random

from django.core.cache import cache

from corehq.apps.prototype.utils import fake_data
from corehq.util.quickcache import quickcache


class BaseCacheStore:
    slug = None
    timeout = 2 * 60 * 60
    default_value = None

    def __init__(self, request):
        self.username = request.user.username

    @property
    def cache_key(self):
        return f"{self.username}:saas-prototype:{self.slug}"

    def set(self, data):
        cache.set(self.cache_key, data, self.timeout)

    def get(self):
        return cache.get(self.cache_key, copy.deepcopy(self.default_value))

    def delete(self):
        cache.delete(self.cache_key)


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


class SlowSimulatorStore(BaseCacheStore):
    slug = 'prototype-slow-simulator'
    default_value = 0


class ShowWhitespacesStore(BaseCacheStore):
    slug = 'prototype-slow-simulator'
    default_value = False


class FakeCaseDataStore(BaseCacheStore):
    slug = 'prototype-case-data-store'

    @property
    def default_value(self):
        return _get_fake_data(111)


def _simulate_issues(value, can_be_missing=False):
    is_missing = bool(random.getrandbits(1))
    if is_missing and can_be_missing:
        return ""

    num_pre_space = random.choice([0, 1, 2, 4])
    num_post_space = random.choice([0, 1, 2, 4])
    value = ' ' * num_pre_space + value + ' ' * num_post_space

    newline = bool(random.getrandbits(1))
    if newline:
        value = value + "\n"

    tab = bool(random.getrandbits(1))
    if tab:
        value = "\t" + value
    return value


@quickcache(['num_entries'])
def _get_fake_data(num_entries):
    rows = []
    status = ('open', 'closed')
    for row in range(0, num_entries):
        rows.append({
            "id": row,
            "selected": False,
            "full_name": _simulate_issues(f"{fake_data.get_first_name()} {fake_data.get_last_name()}"),
            "color": _simulate_issues(fake_data.get_color(), True),
            "big_cat": _simulate_issues(fake_data.get_big_cat(), True),
            "planet": _simulate_issues(fake_data.get_planet(), True),
            "submitted_on": fake_data.get_past_date(),
            "app": fake_data.get_fake_app(),
            "status": random.choice(status),
        })
    return rows
