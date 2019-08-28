"""
LedgerES
------
.. code-block:: python

    from corehq.apps.es import cases as case_es

    q = (ledgers.LedgerES()
         .domain('testproject')
         .section('stock')
"""
from corehq.pillows.mappings import NULL_VALUE
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
        ] + super(LedgerES, self).builtin_filters


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


def entries(entry_ids):
    return filters.term(
        'entry_id',
        [entry_id if entry_id is not None else NULL_VALUE for entry_id in entry_ids]
    )
