import datetime

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.parsing import json_format_datetime

from corehq.sql_db.util import estimate_row_count
from corehq.util.couch_helpers import paginate_view
from corehq.util.test_utils import unit_testing_only

from .const import (
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
    RECORD_EMPTY_STATE,
)


def get_pending_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_PENDING_STATE)


def get_failure_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_FAILURE_STATE)


def get_success_repeat_record_count(domain, repeater_id):
    return (
        get_repeat_record_count(domain, repeater_id, RECORD_SUCCESS_STATE)
        + get_repeat_record_count(domain, repeater_id, RECORD_EMPTY_STATE)
    )


def get_cancelled_repeat_record_count(domain, repeater_id):
    # Does not include RECORD_EMPTY_STATE
    return get_repeat_record_count(domain, repeater_id, RECORD_CANCELLED_STATE)


def get_repeat_record_count(domain, repeater_id=None, state=None, datespan=None):
    from .models import are_repeat_records_migrated

    if are_repeat_records_migrated(domain):
        return get_sql_repeat_record_count(domain, repeater_id, state, datespan=datespan)
    return get_couch_repeat_record_count(domain, repeater_id, state, datespan=datespan)


def get_couch_repeat_record_count(domain, repeater_id=None, state=None, datespan=None):
    from .models import RepeatRecord
    kwargs = dict(
        include_docs=False,
        reduce=True,
        descending=True,
    )
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id, state, datespan=datespan))
    result = RepeatRecord.get_db().view('repeat_records_by_last_checked/view', **kwargs).one()
    return result['value'] if result else 0


def get_sql_repeat_record_count(domain, repeater_id=None, state=None, datespan=None):
    from .models import SQLRepeatRecord

    queryset = SQLRepeatRecord.objects.filter(domain=domain)
    if repeater_id:
        queryset = queryset.filter(repeater__repeater_id=repeater_id)
    if state:
        queryset = queryset.filter(state=state)
    if datespan:
        queryset = queryset.filter(
            sqlrepeatrecordattempt__created_at__range=(datespan.startdate, datespan.enddate))
    return estimate_row_count(queryset)


def get_overdue_repeat_record_count(overdue_threshold=datetime.timedelta(minutes=10)):
    from .models import RepeatRecord
    overdue_datetime = datetime.datetime.utcnow() - overdue_threshold
    results = RepeatRecord.view(
        "repeaters/repeat_records_by_next_check",
        startkey=[None],
        endkey=[None, json_format_datetime(overdue_datetime)],
        reduce=True,
    ).one()
    return results['value'] if results else 0


def _get_startkey_endkey_all_records(domain, repeater_id=None, state=None, datespan=None):
    """A util to construct startkey and endkey filters to be applied
         on "repeaters/repeat_records_by_next_check" couch view.

    datespan -- a DateSpan object to filter by last_checked.
                  assumes the query has descending=True
    """
    kwargs = {}

    if datespan:
        # reversed because descending:True
        enddatekey = json_format_datetime(datespan.startdate) if datespan.startdate else ""
        startdatekey = json_format_datetime(datespan.enddate) if datespan.enddate else ""
        kwargs['endkey'] = [domain, repeater_id, state, enddatekey]
        kwargs['startkey'] = [domain, repeater_id, state, startdatekey]
    elif state:
        kwargs['endkey'] = [domain, repeater_id, state]
        kwargs['startkey'] = [domain, repeater_id, state, {}]
    elif repeater_id:
        kwargs['endkey'] = [domain, repeater_id]
        kwargs['startkey'] = [domain, repeater_id, None, {}]
    else:
        kwargs['endkey'] = [domain, None, None]
        kwargs['startkey'] = [domain, None, None, {}]

    return kwargs


def get_paged_repeat_records(domain, skip, limit, repeater_id=None, state=None,
        datespan=None):
    from .models import are_repeat_records_migrated

    if are_repeat_records_migrated(domain):
        return get_paged_sql_repeat_records(domain, skip, limit, repeater_id, state,
            datespan=datespan)
    return get_paged_couch_repeat_records(domain, skip, limit, repeater_id, state,
        datespan=datespan)


def get_paged_couch_repeat_records(domain, skip, limit, repeater_id=None, state=None,
        datespan=None):
    from .models import RepeatRecord
    kwargs = {
        'include_docs': True,
        'reduce': False,
        'limit': limit,
        'skip': skip,
        'descending': True,
    }
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id, state, datespan=datespan))

    results = RepeatRecord.get_db().view('repeat_records_by_last_checked/view', **kwargs).all()

    return [RepeatRecord.wrap(result['doc']) for result in results]


def get_paged_sql_repeat_records(domain, skip, limit, repeater_id=None, state=None,
        datespan=None):
    from .models import SQLRepeatRecord

    queryset = SQLRepeatRecord.objects.filter(domain=domain)
    if repeater_id:
        queryset = queryset.filter(repeater__repeater_id=repeater_id)
    if state:
        queryset = queryset.filter(state=state)
    if datespan:
        queryset = queryset.filter(
            sqlrepeatrecordattempt__created_at__range=(datespan.startdate, datespan.enddate))
    return (queryset.order_by('-registered_at')[skip:skip + limit]
            .select_related('repeater')
            .prefetch_related('sqlrepeatrecordattempt_set'))


def iter_repeat_records_by_domain(domain, repeater_id=None, state=None, chunk_size=1000):
    from .models import RepeatRecord
    kwargs = {
        'include_docs': True,
        'reduce': False,
        'descending': True,
    }
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id, state))

    for doc in paginate_view(
            RepeatRecord.get_db(),
            'repeat_records_by_last_checked/view',
            chunk_size,
            **kwargs):
        yield RepeatRecord.wrap(doc['doc'])


def iter_repeat_records_by_repeater(domain, repeater_id, chunk_size=1000):
    return _iter_repeat_records_by_repeater(domain, repeater_id, chunk_size,
                                            include_docs=True)


def iter_repeat_record_ids_by_repeater(domain, repeater_id, chunk_size=1000):
    return _iter_repeat_records_by_repeater(domain, repeater_id, chunk_size,
                                            include_docs=False)


def _iter_repeat_records_by_repeater(domain, repeater_id, chunk_size,
                                     include_docs):
    from corehq.motech.repeaters.models import RepeatRecord
    kwargs = {
        'include_docs': include_docs,
        'reduce': False,
        'descending': True,
    }
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id))
    for doc in paginate_view(
            RepeatRecord.get_db(),
            'repeat_records_by_last_checked/view',
            chunk_size,
            **kwargs):
        if include_docs:
            yield RepeatRecord.wrap(doc['doc'])
        else:
            yield doc['id']


def get_repeat_records_by_payload_id(domain, payload_id):
    repeat_records = get_sql_repeat_records_by_payload_id(domain, payload_id)
    if repeat_records:
        return repeat_records
    return get_couch_repeat_records_by_payload_id(domain, payload_id)


def get_couch_repeat_records_by_payload_id(domain, payload_id):
    return _get_couch_repeat_records_by_payload_id(domain, payload_id,
                                                   include_docs=True)


def get_couch_repeat_record_ids_by_payload_id(domain, payload_id):
    return _get_couch_repeat_records_by_payload_id(domain, payload_id,
                                                   include_docs=False)


def _get_couch_repeat_records_by_payload_id(domain, payload_id, include_docs):
    from .models import RepeatRecord
    results = RepeatRecord.get_db().view(
        'repeaters/repeat_records_by_payload_id',
        startkey=[domain, payload_id],
        endkey=[domain, payload_id],
        include_docs=include_docs,
        reduce=False,
        descending=True
    ).all()
    if include_docs:
        return [RepeatRecord.wrap(result['doc']) for result in results]
    return [result['id'] for result in results]


def get_sql_repeat_records_by_payload_id(domain, payload_id):
    from corehq.motech.repeaters.models import SQLRepeatRecord

    return (SQLRepeatRecord.objects
            .filter(domain=domain, payload_id=payload_id)
            .order_by('-registered_at')
            .all())


def iterate_repeat_records_for_ids(doc_ids):
    from .models import RepeatRecord
    return (RepeatRecord.wrap(doc) for doc in iter_docs(RepeatRecord.get_db(), doc_ids))


def iterate_repeat_record_ids(due_before, chunk_size=10000):
    """
    Yields repeat record ids only.
    Use chunk_size to optimize db query. Has no effect on # of items returned.
    """
    from .models import RepeatRecord
    json_due_before = json_format_datetime(due_before)

    view_kwargs = {
        'reduce': False,
        'startkey': [None],
        'endkey': [None, json_due_before, {}],
        'include_docs': False
    }
    for doc in paginate_view(
            RepeatRecord.get_db(),
            'repeaters/repeat_records_by_next_check',
            chunk_size,
            **view_kwargs):
        yield doc['id']


def get_domains_that_have_repeat_records():
    from .models import RepeatRecord
    return [
        row['key'][0]
        for row in RepeatRecord.view('repeat_records_by_last_checked/view', group_level=1).all()
    ]


@unit_testing_only
def delete_all_repeat_records():
    from .models import RepeatRecord
    results = RepeatRecord.get_db().view('repeat_records_by_last_checked/view', reduce=False).all()
    for result in results:
        try:
            repeat_record = RepeatRecord.get(result['id'])
        except Exception:
            pass
        else:
            repeat_record.delete()


@unit_testing_only
def delete_all_repeaters():
    from .models import Repeater
    Repeater.objects.all().delete()
