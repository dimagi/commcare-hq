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
        startkey = [domain, ids[0], state]
        endkey = [domain, ids[-1], state]

    results = RepeatRecord.get_db().view('receiverwrapper/repeat_records',
        startkey=startkey,
        endkey=endkey,
        include_docs=True,
        reduce=False,
        limit=limit,
        skip=skip,
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

    return [result['_id'] for result in results]
