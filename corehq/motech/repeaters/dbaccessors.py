from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from dimagi.utils.parsing import json_format_datetime

from corehq.util.couch_helpers import paginate_view
from corehq.util.test_utils import unit_testing_only

from .const import RECORD_PENDING_STATE, RECORD_FAILURE_STATE, RECORD_SUCCESS_STATE, RECORD_CANCELLED_STATE


def get_pending_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_PENDING_STATE)


def get_failure_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_FAILURE_STATE)


def get_success_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_SUCCESS_STATE)


def get_cancelled_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_CANCELLED_STATE)


def get_repeat_record_count(domain, repeater_id=None, state=None, last_checked_after=None):
    from .models import RepeatRecord
    kwargs = dict(
        include_docs=False,
        reduce=True,
        descending=True,
    )
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id, state, last_checked_after))

    result = RepeatRecord.get_db().view('repeaters/repeat_records', **kwargs).one()

    return result['value'] if result else 0


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


def _get_startkey_endkey_all_records(domain, repeater_id=None, state=None, last_checked_after=None):
    kwargs = {}

    if repeater_id and not state:
        kwargs['endkey'] = [domain, repeater_id]
        kwargs['startkey'] = [domain, repeater_id, {}]
    elif repeater_id and state:
        kwargs['endkey'] = [domain, repeater_id, state]
        kwargs['startkey'] = [domain, repeater_id, state, {}]
    elif not repeater_id and state:
        kwargs['endkey'] = [domain, None, state]
        kwargs['startkey'] = [domain, None, state, {}]
    elif not repeater_id and not state:
        kwargs['endkey'] = [domain, None]
        kwargs['startkey'] = [domain, None, {}]

    if last_checked_after:
        assert state, 'You must choose a state in order to query by last_checked'
        kwargs['endkey'].append(json_format_datetime(last_checked_after))

    return kwargs


def get_paged_repeat_records(domain, skip, limit, repeater_id=None, state=None):
    from .models import RepeatRecord
    kwargs = {
        'include_docs': True,
        'reduce': False,
        'limit': limit,
        'skip': skip,
        'descending': True,
    }
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id, state))

    results = RepeatRecord.get_db().view('repeaters/repeat_records', **kwargs).all()

    return [RepeatRecord.wrap(result['doc']) for result in results]


def iter_repeat_records_by_domain(domain, repeater_id=None, state=None, since=None, chunk_size=1000):
    from .models import RepeatRecord
    kwargs = {
        'include_docs': True,
        'reduce': False,
        'descending': True,
    }
    kwargs.update(_get_startkey_endkey_all_records(domain, repeater_id, state,
                                                   last_checked_after=since))

    for doc in paginate_view(
            RepeatRecord.get_db(),
            'repeaters/repeat_records',
            chunk_size,
            **kwargs):
        yield RepeatRecord.wrap(doc['doc'])


def get_repeat_records_by_payload_id(domain, payload_id):
    from .models import RepeatRecord
    results = RepeatRecord.get_db().view(
        'repeaters/repeat_records_by_payload_id',
        startkey=[domain, payload_id],
        endkey=[domain, payload_id],
        include_docs=True,
        reduce=False,
        descending=True
    ).all()
    return [RepeatRecord.wrap(result['doc']) for result in results]


def get_repeaters_by_domain(domain):
    from .models import Repeater

    results = Repeater.get_db().view('repeaters/repeaters',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
    ).all()

    return [Repeater.wrap(result['doc']) for result in results
            if Repeater.get_class_from_doc_type(result['doc']['doc_type'])
            ]


def _get_repeater_ids_by_domain(domain):
    from .models import Repeater

    results = Repeater.get_db().view('repeaters/repeaters',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=False,
        reduce=False,
    ).all()

    return [result['id'] for result in results]


def iterate_repeat_records(due_before, chunk_size=10000, database=None):
    from .models import RepeatRecord
    json_now = json_format_datetime(due_before)

    view_kwargs = {
        'reduce': False,
        'startkey': [None],
        'endkey': [None, json_now, {}],
        'include_docs': True
    }
    for doc in paginate_view(
            RepeatRecord.get_db(),
            'repeaters/repeat_records_by_next_check',
            chunk_size,
            **view_kwargs):
        yield RepeatRecord.wrap(doc['doc'])


def get_domains_that_have_repeat_records():
    from .models import RepeatRecord
    return [
        row['key'][0]
        for row in RepeatRecord.view('repeaters/repeat_records', group_level=1).all()
    ]


@unit_testing_only
def delete_all_repeat_records():
    from .models import RepeatRecord
    results = RepeatRecord.get_db().view('repeaters/repeat_records_by_next_check', reduce=False).all()
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
    for repeater in Repeater.get_db().view('repeaters/repeaters', reduce=False, include_docs=True).all():
        Repeater.wrap(repeater['doc']).delete()
