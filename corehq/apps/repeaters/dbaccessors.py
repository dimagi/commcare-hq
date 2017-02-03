from dimagi.utils.parsing import json_format_datetime

from corehq.util.couch_helpers import paginate_view
from corehq.util.test_utils import unit_testing_only

from .const import RECORD_PENDING_STATE, RECORD_FAILURE_STATE, RECORD_SUCCESS_STATE


def get_pending_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_PENDING_STATE)


def get_failure_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_FAILURE_STATE)


def get_success_repeat_record_count(domain, repeater_id):
    return get_repeat_record_count(domain, repeater_id, RECORD_SUCCESS_STATE)


def get_repeat_record_count(domain, repeater_id=None, state=None):
    from .models import RepeatRecord
    startkey = [domain]
    endkey = [domain, {}]

    if repeater_id and not state:
        startkey = [domain, repeater_id]
        endkey = [domain, repeater_id, {}]
    elif repeater_id and state:
        startkey = [domain, repeater_id, state]
        endkey = [domain, repeater_id, state]
    elif not repeater_id and state:
        ids = sorted(_get_repeater_ids_by_domain(domain))
        if not ids:
            return 0
        startkey = [domain, ids[0], state]
        endkey = [domain, ids[-1], state]

    result = RepeatRecord.get_db().view('receiverwrapper/repeat_records',
        startkey=startkey,
        endkey=endkey,
        include_docs=False,
        reduce=True,
    ).one()

    return result['value'] if result else 0


def get_paged_repeat_records(domain, skip, limit, repeater_id=None, state=None):
    from .models import RepeatRecord
    kwargs = {
        'include_docs': True,
        'reduce': False,
        'limit': limit,
        'skip': skip,
    }

    if repeater_id and not state:
        kwargs['startkey'] = [domain, repeater_id]
        kwargs['endkey'] = [domain, repeater_id, {}]
    elif repeater_id and state:
        kwargs['startkey'] = [domain, repeater_id, state]
        kwargs['endkey'] = [domain, repeater_id, state]
    elif not repeater_id and state:
        kwargs['key'] = [domain, None, state]
    elif not repeater_id and not state:
        kwargs['startkey'] = [domain]
        kwargs['endkey'] = [domain, {}]

    results = RepeatRecord.get_db().view('receiverwrapper/repeat_records',
        **kwargs
    ).all()

    return [RepeatRecord.wrap(result['doc']) for result in results]


def get_repeaters_by_domain(domain):
    from .models import Repeater

    results = Repeater.get_db().view('receiverwrapper/repeaters',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
    ).all()

    return [Repeater.wrap(result['doc']) for result in results]


def _get_repeater_ids_by_domain(domain):
    from .models import Repeater

    results = Repeater.get_db().view('receiverwrapper/repeaters',
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
            'receiverwrapper/repeat_records_by_next_check',
            chunk_size,
            **view_kwargs):
        yield RepeatRecord.wrap(doc['doc'])


@unit_testing_only
def delete_all_repeat_records():
    from .models import RepeatRecord
    results = RepeatRecord.get_db().view('receiverwrapper/repeat_records_by_next_check', reduce=False).all()
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
    for repeater in Repeater.get_db().view('receiverwrapper/repeaters', reduce=False, include_docs=True).all():
        Repeater.wrap(repeater['doc']).delete()
