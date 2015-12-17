from collections import namedtuple
from jsonobject import DefaultProperty
from corehq.apps.app_manager.models import Application
from corehq.util.couch import stale_ok
from corehq.util.quickcache import quickcache
from couchforms.analytics import get_last_form_submission_by_xmlns
from couchforms.models import XFormInstance
from dimagi.ext import jsonobject


SimpleFormInfo = namedtuple('FormInfo', ['app_id', 'xmlns'])


class AppInfo(jsonobject.JsonObject):
    id = jsonobject.StringProperty()
    names = jsonobject.StringProperty()
    langs = jsonobject.ListProperty(unicode)


class AppPart(jsonobject.JsonObject):
    id = jsonobject.IntegerProperty()
    names = DefaultProperty()  # this is almost always a dict, but for user registration it's a string


class FormDetails(jsonobject.JsonObject):
    xmlns = jsonobject.StringProperty()
    app = jsonobject.ObjectProperty(AppInfo)
    module = jsonobject.ObjectProperty(AppPart)
    form = jsonobject.ObjectProperty(AppPart)
    is_deleted = jsonobject.BooleanProperty()
    is_user_registration = jsonobject.BooleanProperty(default=False)


def update_reports_analytics_indexes():
    XFormInstance.get_db().view('all_forms/view', limit=1).all()
    XFormInstance.get_db().view('forms_by_app_info/view', limit=1).all()


@quickcache(['domain', 'xmlns'], timeout=5 * 60)
def guess_form_name_from_submissions_using_xmlns(domain, xmlns):
    last_form = get_last_form_submission_by_xmlns(domain, xmlns)
    return last_form.form.get('@name') if last_form else None


def get_all_form_definitions_grouped_by_app_and_xmlns(domain):
    def _row_to_form_info(row):
        return SimpleFormInfo(app_id=row['key'][3], xmlns=row['key'][2])

    startkey = ["xmlns app", domain]
    return [
        _row_to_form_info(r) for r in Application.get_db().view(
            'forms_by_app_info/view',
            startkey=startkey,
            endkey=startkey + [{}],
            group=True,
            stale=stale_ok(),
        ).all()
    ]


def get_all_form_details(domain, deleted=None):
    """
    deleted = None means include all options.
    deleted = True/False will only included deleted/non-deleted apps
    """
    if deleted is None:
        startkey = ["app module form", domain]
    else:
        status = 'deleted' if deleted else 'active'
        startkey = ["status app module form", domain, status]
    return [
        _row_to_form_details(r) for r in Application.get_db().view(
            'forms_by_app_info/view',
            startkey=startkey,
            endkey=startkey + [{}],
            reduce=False,
            stale=stale_ok(),
        ).all()
    ]


def get_form_details_for_xmlns(domain, xmlns):
    startkey = ["xmlns", domain, xmlns]
    return [
        _row_to_form_details(row) for row in Application.get_db().view('forms_by_app_info/view',
            startkey=startkey,
            endkey=startkey + [{}],
            reduce=False,
            stale=stale_ok(),
        ).all()
    ]


def get_form_details_for_app(domain, app_id, deleted=False):
    status = 'deleted' if deleted else 'active'
    startkey = ["status app module form", domain, status, app_id]
    return [
        _row_to_form_details(row) for row in Application.get_db().view('forms_by_app_info/view',
            startkey=startkey,
            endkey=startkey + [{}],
            reduce=False,
            stale=stale_ok(),
        ).all()
    ]


def get_form_details_for_app_and_module(domain, app_id, module_id, deleted=False):
    status = 'deleted' if deleted else 'active'
    startkey = ["status app module form", domain, status, app_id, module_id]
    return [
        _row_to_form_details(row) for row in Application.get_db().view('forms_by_app_info/view',
            startkey=startkey,
            endkey=startkey + [{}],
            reduce=False,
            stale=stale_ok(),
        ).all()
    ]


def get_form_details_for_app_and_xmlns(domain, app_id, xmlns, deleted=False):
    status = 'deleted' if deleted else 'active'
    startkey = ["status xmlns app", domain, status, xmlns, app_id]
    return [
        _row_to_form_details(row) for row in Application.get_db().view('forms_by_app_info/view',
            startkey=startkey,
            endkey=startkey + [{}],
            reduce=False,
            stale=stale_ok(),
        ).all()
    ]


def _row_to_form_details(row):
    return FormDetails.wrap(row['value'])
