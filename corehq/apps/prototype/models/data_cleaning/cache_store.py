import copy

from django.core.cache import cache

from corehq.apps.prototype.utils.fake_case_data.mother_case import get_case_data_with_issues
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
        "name",
        "dob",
        "height",
        "spoken_language",
        "mother_status",
        "date_of_delivery",
        "edd",
        "time_of_day",
        "last_modified_date",
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


class ApplyChangesSimulationStore(BaseCacheStore):
    slug = 'prototype-apply-changes-sim'
    default_value = 0


class FakeCaseDataStore(BaseCacheStore):
    slug = 'prototype-case-data-store'

    @property
    def default_value(self):
        return _get_fake_data(107)


@quickcache(['num_entries'])
def _get_fake_data(num_entries):
    rows = []
    for row in range(0, num_entries):
        case_data = get_case_data_with_issues()
        rows.append({
            "id": row,
            "selected": False,
            **case_data,
        })
    return rows
