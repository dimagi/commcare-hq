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
            modified_range,
            server_modified_range,
            is_closed,
            case_type,
            owner,
            owner_type,
            user,
            user_ids_handle_unknown,
            opened_by,
            active_in_range,
        ] + super(CaseES, self).builtin_filters


def opened_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('opened_on', gt, gte, lt, lte)


def closed_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('closed_on', gt, gte, lt, lte)


def modified_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('modified_on', gt, gte, lt, lte)


def server_modified_range(gt=None, gte=None, lt=None, lte=None):
    return filters.date_range('server_modified_on', gt, gte, lt, lte)


def is_closed(closed=True):
    return filters.term('closed', closed)


def case_type(type_):
    return filters.term('type.exact', type_)


def owner(owner_id):
    return filters.term('owner_id', owner_id)


def owner_type(owner_type):
    return filters.term('owner_type', owner_type)


def user(user_id):
    return filters.term('user_id', user_id)


def opened_by(user_id):
    return filters.term('opened_by', user_id)


def active_in_range(gt=None, gte=None, lt=None, lte=None):
    """Restricts cases returned to those with actions during the range"""
    return filters.nested(
        "actions",
        filters.date_range("actions.date", gt, gte, lt, lte)
    )


def user_ids_handle_unknown(user_ids):
    missing_users = None in user_ids

    user_ids = filter(None, user_ids)

    if not missing_users:
        user_filter = user(user_ids)
    elif user_ids and missing_users:
        user_filter = filters.OR(
            user(user_ids),
            filters.missing('user_id'),
        )
    else:
        user_filter = filters.missing('user_id')
    return user_filter
