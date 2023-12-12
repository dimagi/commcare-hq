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
