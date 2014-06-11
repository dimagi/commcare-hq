from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from corehq.apps.users.models import CouchUser, WebUser
from custom.succeed.reports import SUBMISSION_SELECT_FIELDS
from custom.succeed.utils import is_succeed_admin, CONFIG, is_pm_or_pi


class CareSite(ReportSelectField):
    slug = "care_site"
    name = ugettext_noop("Care Site")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Sites"

    @property
    def options(self):
        return CONFIG['groups']


class ResponsibleParty(ReportSelectField):
    slug = "responsible_party"
    name = ugettext_noop("Responsible Party")
    cssId = "opened_closed"
    cssClasses = "span3"

    @property
    def options(self):
        user = self.request.couch_user
        cm = dict(val=CONFIG['cm_role'], text=ugettext_noop("Care Manager"))
        chw = dict(val=CONFIG['chw_role'], text=ugettext_noop("Community Health Worker"))
        options = []
        if isinstance(user, WebUser) or is_succeed_admin(user) or is_pm_or_pi(user):
            options = [
                dict(val='', text=ugettext_noop("All Roles")),
                dict(val=CONFIG['pm_role'], text=ugettext_noop("Project Manager")),
                cm,
                chw
            ]
        else:
            role = user.get_role()['name']
            if role == CONFIG['cm_role']:
                options.append(cm)
            elif role == CONFIG['chw_role']:
                options.append(chw)
        return options


class PatientStatus(ReportSelectField):
    slug = "patient_status"
    name = ugettext_noop("Patient Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Patients"
    options = [dict(val="active", text=ugettext_noop("Active")),
               dict(val="not_active", text=ugettext_noop("Not Active"))]

class PatientFormNameFilter(BaseDrilldownOptionFilter):
    label = ugettext_noop("Filter Forms")
    slug = "form_name"
    css_class = "span5"

    @property
    def drilldown_map(self):
        return SUBMISSION_SELECT_FIELDS

    @classmethod
    def get_labels(cls):
        return [
            ('Form Group', 'All Form Groups', 'group'),
            ('Form Name', 'All Form names', 'xmlns'),
        ]
