import datetime
from dimagi.utils.couch.database import get_db

from dimagi.utils.parsing import json_format_datetime
from corehq.util.couch import stale_ok
from corehq.util.dates import iso_string_to_datetime
from couchforms.models import XFormInstance


def update_analytics_indexes():
    """
    Mostly for testing; wait until analytics data sources are up to date
    so that calls to analytics functions return up-to-date
    """
    XFormInstance.get_db().view('reports_forms/all_forms', limit=1).all()


def domain_has_submission_in_last_30_days(domain):
    last_submission = get_last_form_submission_received(domain)
    # if there have been any submissions in the past 30 days
    if last_submission:
        _30_days = datetime.timedelta(days=30)
        return datetime.datetime.utcnow() <= last_submission + _30_days
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


def app_has_been_submitted_to_in_last_30_days(domain, app_id):
    now = datetime.datetime.utcnow()
    _30_days = datetime.timedelta(days=30)
    then = json_format_datetime(now - _30_days)
    now = json_format_datetime(now)

    key = ['submission app', domain, app_id]
    row = XFormInstance.get_db().view(
        "reports_forms/all_forms",
        startkey=key + [then],
        endkey=key + [now],
        limit=1,
        stale=stale_ok(),
    ).all()
    return True if row else False


def get_username_in_last_form_user_id_submitted(domain, user_id):
    assert domain
    user_info = XFormInstance.get_db().view(
        'reports_forms/all_forms',
        startkey=["submission user", domain, user_id],
        limit=1,
        descending=True,
        reduce=False
    ).one()
    try:
        return user_info['value']['username']
    except KeyError:
        return None


def get_all_user_ids_submitted(domain):
    key = ["submission user", domain]
    submitted = XFormInstance.get_db().view(
        'reports_forms/all_forms',
        startkey=key,
        endkey=key + [{}],
        group=True,
        group_level=3
    ).all()
    return {user['key'][2] for user in submitted}
