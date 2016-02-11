from .const import RECORD_PENDING_STATE, RECORD_FAILURE_STATE, RECORD_SUCCESS_STATE


def get_pending_repeat_record_count(domain, repeater_id):
    return _get_repeat_record_count(domain, repeater_id, RECORD_PENDING_STATE)


def get_failure_repeat_record_count(domain, repeater_id):
    return _get_repeat_record_count(domain, repeater_id, RECORD_FAILURE_STATE)


def get_success_repeat_record_count(domain, repeater_id):
    return _get_repeat_record_count(domain, repeater_id, RECORD_SUCCESS_STATE)


def _get_repeat_record_count(domain, repeater_id, state):
    from .models import Repeater

    result = Repeater.get_db().view('receiverwrapper/repeat_records',
        key=[domain, repeater_id, state],
        reduce=True,
    ).one()
    return result['value'] if result else 0
