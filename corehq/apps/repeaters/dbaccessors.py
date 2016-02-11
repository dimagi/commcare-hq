from .const import RECORD_PENDING_STATE, RECORD_FAILURE_STATE, RECORD_SUCCESS_STATE


def get_pending_repeat_record_count(domain, repeater_id):
    return _get_repeat_record_count(domain, repeater_id, RECORD_PENDING_STATE)


def get_failure_repeat_record_count(domain, repeater_id):
    return _get_repeat_record_count(domain, repeater_id, RECORD_FAILURE_STATE)


def get_success_repeat_record_count(domain, repeater_id):
    return _get_repeat_record_count(domain, repeater_id, RECORD_SUCCESS_STATE)


def _get_repeat_record_count(domain, repeater_id, state):
    from .models import RepeatRecord

    result = RepeatRecord.get_db().view('receiverwrapper/repeat_records',
        key=[domain, repeater_id, state],
        reduce=True,
    ).one()
    return result['value'] if result else 0


def get_repeat_records(domain, repeater_id=None, state=None):
    from .models import RepeatRecord
    key = [domain]
    if repeater_id:
        key.append(repeater_id)

    results = RepeatRecord.get_db().view('receiverwrapper/repeat_records',
        startkey=key,
        endkey=key + [{}],
        include_docs=True,
        reduce=False,
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
