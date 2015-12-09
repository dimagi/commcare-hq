from collections import namedtuple
from corehq.apps.app_manager.models import Application
from corehq.util.couch import stale_ok
from corehq.util.quickcache import quickcache
from couchforms.analytics import get_last_form_submission_by_xmlns
from couchforms.models import XFormInstance


FormInfo = namedtuple('FormInfo', ['app_id', 'xmlns'])


def update_reports_analytics_indexes():
    XFormInstance.get_db().view('reports_forms/all_forms', limit=1).all()


@quickcache(['domain', 'xmlns'], timeout=5 * 60)
def guess_form_name_from_submissions_using_xmlns(domain, xmlns):
    last_form = get_last_form_submission_by_xmlns(domain, xmlns)
    return last_form.form.get('@name') if last_form else None


def get_all_form_definitions_grouped_by_app_and_xmlns(domain):
    def _row_to_form_info(row):
        return FormInfo(app_id=row['key'][3], xmlns=row['key'][2])

    startkey = ["xmlns app", domain]
    return [
        _row_to_form_info(r) for r in Application.get_db().view(
            'reports_forms/by_app_info',
            startkey=startkey,
            endkey=startkey + [{}],
            group=True,
            stale=stale_ok(),
        ).all()
    ]
