"""
CaseES
------

Here's an example getting pregnancy cases that are either still open or were
closed after May 1st.

.. code-block:: python

    from corehq.apps.es import cases as case_es

    q = (case_es.CaseES()
         .domain('testproject')
         .case_type('pregnancy')
         .OR(case_es.is_closed(False),
             case_es.closed_range(gte=datetime.date(2015, 05, 01))))
"""
from .es_query import HQESQuery
from . import filters


class CaseES(HQESQuery):
    index = 'cases'

    @property
    def builtin_filters(self):
        return [
            opened_range,
            closed_range,
            is_closed,
            case_type,
            owner,
        ] + super(CaseES, self).builtin_filters


def opened_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('opened_on', gt, gte, lt, lte)


def closed_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('closed_on', gt, gte, lt, lte)


def is_closed(closed=True):
    return filters.term('closed', closed)


def case_type(type_):
    return filters.term('type.exact', type_)


def owner(owner_id):
    return filters.term('owner_id', owner_id)
