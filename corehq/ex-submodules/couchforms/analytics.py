import datetime
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
    ).all()
    # if there have been any submissions in the past 30 days
    if len(results) > 0:
        received_on = iso_string_to_datetime(results[0]['key'][2])
        _30_days = datetime.timedelta(days=30)
        return datetime.datetime.utcnow() <= received_on + _30_days
    else:
        return False
