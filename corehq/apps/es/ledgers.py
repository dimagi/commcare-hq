"""
LedgerES
------
.. code-block:: python

    from corehq.apps.es import cases as case_es

    q = (ledgers.LedgerES()
         .domain('testproject')
         .section('stock')
"""
from .es_query import HQESQuery
from . import filters


class LedgerES(HQESQuery):
    index = 'ledgers'

    @property
    def builtin_filters(self):
        return [
            case,
            section,
            entry,
            location,
            modified_range,
            filters.domain,
        ]


def case(case_id):
    return filters.term('case_id', case_id)


def section(section_id):
    return filters.term('section_id', section_id)


def entry(entry_id):
    return filters.term('entry_id', entry_id)


def location(location_id):
    return filters.term('location_id', location_id)


def modified_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('last_modified', gt, gte, lt, lte)
