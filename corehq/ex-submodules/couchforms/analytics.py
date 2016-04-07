import datetime

from corehq.apps.es import FormES
from corehq.apps.es.aggregations import TermsAggregation
from corehq.util.quickcache import quickcache

from dimagi.utils.parsing import json_format_datetime
from corehq.util.couch import stale_ok
from corehq.util.dates import iso_string_to_datetime
from couchforms.models import XFormInstance, doc_types


def update_analytics_indexes():
    """
    Mostly for testing; wait until analytics data sources are up to date
    so that calls to analytics functions return up-to-date
    """
    from corehq.apps.app_manager.models import Application
    XFormInstance.get_db().view('couchforms/all_submissions_by_domain', limit=1).all()
    XFormInstance.get_db().view('all_forms/view', limit=1).all()
    XFormInstance.get_db().view('exports_forms_by_xform/view', limit=1).all()
    Application.get_db().view('exports_forms_by_app/view', limit=1).all()


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
            "all_forms/view",
            group=True,
            group_level=2,
            startkey=key,
            endkey=key + [{}],
            stale=stale_ok(),
        ).all()
    }


def get_number_of_forms_in_domain(domain):
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(domain)
    row = XFormInstance.get_db().view(
        "all_forms/view",
        startkey=key,
        endkey=key + [{}],
        stale=stale_ok(),
    ).one()
    return row["value"] if row else 0


def get_first_form_submission_received(domain):
    from corehq.apps.reports.util import make_form_couch_key
    key = make_form_couch_key(domain)
    row = XFormInstance.get_db().view(
        "all_forms/view",
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
        "all_forms/view",
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
        "all_forms/view",
        startkey=key + [then],
        endkey=key + [now],
        limit=1,
        stale=stale_ok(),
    ).all()
    return True if row else False


def get_username_in_last_form_user_id_submitted(domain, user_id):
    assert domain
    user_info = XFormInstance.get_db().view(
        'all_forms/view',
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
        'all_forms/view',
        startkey=key,
        endkey=key + [{}],
        group=True,
        group_level=3
    ).all()
    return {user['key'][2] for user in submitted}


def get_all_xmlns_app_id_pairs_submitted_to_in_domain(domain):
    key = ["submission xmlns app", domain]
    results = XFormInstance.get_db().view(
        'all_forms/view',
        startkey=key,
        endkey=key + [{}],
        group=True,
        group_level=4,
    ).all()
    return {(result['key'][-2], result['key'][-1]) for result in results}


@quickcache(['domain', 'app_id', 'xmlns'], memoize_timeout=0, timeout=5 * 60)
def get_form_analytics_metadata(domain, app_id, xmlns):
    """
    Returns metadata about the form, or None if no info found.

    Here is an example structure:
    {
        "xmlns": "http://openrosa.org/formdesigner/5D563904-4038-4070-A0D4-CC421003E862",
        "form": {
            "name": {
                "en": "Brogramming Project",
                "es": "Projecto de brogramming"
            },
            "id": 1
        },
        "app": {
            "langs": [
                "es",
                "en",
                "fra"
            ],
            "name": "brogrammino",
            "id": "10257bd886ba423eea19a562e95cec07"
        },
        "module": {
            "name": {
                "en": "Dimagi",
                "es": "Brogramminos"
            },
            "id": 0
        },
        "app_deleted": false,
        "submissions": 15
    }
    """
    # todo: wrap this return value in a class/stucture
    from corehq.apps.app_manager.models import Application
    view_results = Application.get_db().view(
        'exports_forms_by_app/view',
        key=[domain, app_id, xmlns],
        stale=stale_ok(),
        group=True
    ).one()
    form_count = get_form_count_for_domain_app_xmlns(domain, app_id, xmlns)
    if view_results:
        result = view_results['value']
        result['submissions'] = form_count
        return result
    elif form_count:
        return {'xmlns': xmlns, 'submissions': form_count}
    else:
        return None


def get_exports_by_form(domain):
    from corehq.apps.app_manager.models import Application
    rows = Application.get_db().view(
        'exports_forms_by_app/view',
        startkey=[domain],
        endkey=[domain, {}],
        group=True,
        stale=stale_ok()
    ).all()
    form_count_breakdown = get_form_count_breakdown_for_domain(domain)

    for row in rows:
        key = tuple(row['key'])
        if key in form_count_breakdown:
            row['value']['submissions'] = form_count_breakdown.pop(key)

    for key, value in form_count_breakdown.items():
        rows.append({'key': list(key), 'value': {'xmlns': key[2], 'submissions': value}})

    rows.sort(key=lambda row: row['key'])
    return rows


def get_form_count_breakdown_for_domain(domain):
    query = (FormES()
             .domain(domain)
             .aggregation(
                TermsAggregation("app_id", "app_id").aggregation(
                    TermsAggregation("xmlns", "xmlns.exact")))
             .remove_default_filter("has_xmlns")
             .remove_default_filter("has_user")
             .size(0))
    query_result = query.run()
    form_counts = {}
    for app_id, bucket in query_result.aggregations.app_id.buckets_dict.iteritems():
        for sub_bucket in bucket.xmlns.buckets_list:
            xmlns = sub_bucket.key
            form_counts[(domain, app_id, xmlns)] = sub_bucket.doc_count
    return form_counts


def get_form_count_for_domain_app_xmlns(domain, app_id, xmlns):
    row = XFormInstance.get_db().view(
        'exports_forms_by_xform/view',
        startkey=[domain, app_id, xmlns],
        endkey=[domain, app_id, xmlns, {}],
        group=True,
    ).one()
    if row:
        return row['value']
    else:
        return 0
