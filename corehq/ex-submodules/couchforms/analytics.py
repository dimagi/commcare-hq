import datetime
from corehq.util.couch import stale_ok
from corehq.util.dates import iso_string_to_datetime
from couchforms.models import XFormInstance


def domain_has_submission_in_last_30_days(domain):
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(domain)
    results = XFormInstance.get_db().view(
        'reports_forms/all_forms',
        startkey=key + [{}],
        endkey=key,
        descending=True,
        reduce=False,
        include_docs=False,
        limit=1,
        stale=stale_ok(),
    ).all()
    # if there have been any submissions in the past 30 days
    if len(results) > 0:
        received_on = iso_string_to_datetime(results[0]['key'][2])
        _30_days = datetime.timedelta(days=30)
        return datetime.datetime.utcnow() <= received_on + _30_days
    else:
        return False


def get_number_of_forms_per_domain():
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(None)
    return {
        row["key"][1]: row["value"]
        for row in XFormInstance.get_db().view(
            "reports_forms/all_forms",
            group=True,
            group_level=2,
            startkey=key,
            endkey=key+[{}],
            stale=stale_ok(),
        ).all()
    }


def get_number_of_forms_in_domain(domain):
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(domain)
    row = XFormInstance.get_db().view(
        "reports_forms/all_forms",
        startkey=key,
        endkey=key+[{}],
        stale=stale_ok(),
    ).one()
    return row["value"] if row else 0


def get_first_form_submission_received(domain):
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(domain)
    row = XFormInstance.get_db().view(
        "reports_forms/all_forms",
        reduce=False,
        startkey=key,
        endkey=key + [{}],
        limit=1,
        stale=stale_ok(),
    ).first()
    if row:
        submission_time = iso_string_to_datetime(row["key"][2])
    else:
        submission_time = None
    return submission_time


def get_last_form_submission_received(domain):
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(domain)
    row = XFormInstance.get_db().view(
        "reports_forms/all_forms",
        reduce=False,
        endkey=key,
        startkey=key + [{}],
        descending=True,
        limit=1,
        stale=stale_ok(),
    ).first()
    if row:
        submission_time = iso_string_to_datetime(row["key"][2])
    else:
        submission_time = None
    return submission_time
