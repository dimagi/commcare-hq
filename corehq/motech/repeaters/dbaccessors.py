from dimagi.utils.couch.database import iter_docs
from dimagi.utils.parsing import json_format_datetime

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


def get_repeat_record_count(domain, repeater_id=None, state=None):
    from .models import SQLRepeatRecord

    queryset = SQLRepeatRecord.objects.filter(domain=domain)
    if repeater_id:
        queryset = queryset.filter(repeater__id=repeater_id)
    if state is not None:
        queryset = queryset.filter(state=state)
    return queryset.count()


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
        for row in RepeatRecord.view('repeaters/repeat_records', group_level=1).all()
    ]


@unit_testing_only
def delete_all_repeat_records():
    from .models import RepeatRecord
    db = RepeatRecord.get_db()
    results = db.view(
        'repeaters/repeat_records_by_payload_id',
        reduce=False,
        include_docs=True,
    ).all()
    db.bulk_delete([r["doc"] for r in results], empty_on_delete=False)
