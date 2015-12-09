from corehq.util.quickcache import quickcache
from couchforms.analytics import get_last_form_submission_by_xmlns
from couchforms.models import XFormInstance


def update_reports_analytics_indexes():
    XFormInstance.get_db().view('reports_forms/all_forms', limit=1).all()


@quickcache(['domain', 'xmlns'], timeout=5 * 60)
def guess_form_name_from_submissions_using_xmlns(domain, xmlns):
    last_form = get_last_form_submission_by_xmlns(domain, xmlns)
    return last_form.form.get('@name') if last_form else None
