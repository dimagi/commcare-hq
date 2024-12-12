import random

from corehq.apps.prototype.utils.fake_case_data.mother_case import get_case_data_with_issues

from corehq.apps.prototype.models.cache_store import CacheStore
from corehq.util.quickcache import quickcache


class VisibleColumnStore(CacheStore):
    slug = 'visible-column'
    initial_value = [
        "name",
        "dob",
        "height",
        "mother_status",
        "date_of_delivery",
        "edd",
        "last_modified_date",
        "status",
    ]


class FilterColumnStore(CacheStore):
    slug = 'filter-column-test-001'
    initial_value = []


class SlowSimulatorStore(CacheStore):
    slug = 'prototype-slow-simulator'
    initial_value = 0


class ShowWhitespacesStore(CacheStore):
    slug = 'prototype-slow-simulator'
    initial_value = False


class ApplyChangesSimulationStore(CacheStore):
    slug = 'prototype-apply-changes-sim'
    initial_value = 0


class FakeCaseDataHistoryStore(CacheStore):
    slug = 'prototype-case-data-history-store'
    initial_value = []


class FakeCaseDataStore(CacheStore):
    slug = 'prototype-case-data-store'

    @property
    def initial_value(self):
        return _get_fake_data_for_username(self.username)

    def delete(self):
        super().delete()
        _get_fake_data_for_username.clear(self.username)


@quickcache(['username'])
def _get_fake_data_for_username(username):
    return _get_fake_data(random.choice(range(103, 154)))


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
