from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.users.models import CouchUser, WebUser
from custom.succeed.utils import _is_succeed_admin, CONFIG, _is_pm_or_pi


class CareSite(ReportSelectField):
    slug = "care_site"
    name = ugettext_noop("Care Site")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Sites"

    @property
    def options(self):
        user = self.request.couch_user
        options = []
        if isinstance(user, WebUser) or _is_succeed_admin(user):
            options = CONFIG['groups']
        else:
            groups = user.get_group_ids()
            for group_id in groups:
                group = Group.get(group_id)
                for grp in CONFIG['groups']:
                    if group.name == grp['text']:
                        options.append(grp)
        return options


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
        if isinstance(user, WebUser) or _is_succeed_admin(user) or _is_pm_or_pi(user):
            options = [
                dict(val='', text=ugettext_noop("All Roles")),
                dict(val=CONFIG['pm_role'], text=ugettext_noop("Project Manager")),
                cm,
                chw
            ]
        else:
            role = user.user_data['role']
            if role == CONFIG['cm_role']:
                options.append(cm)
                self.selected = cm['val']
            elif role == CONFIG['chw_role']:
                options.append(chw)
                self.selected = chw['val']
        return options


class PatientStatus(ReportSelectField):
    slug = "patient_status"
    name = ugettext_noop("Patient Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Patients"
    options = [dict(val="active", text=ugettext_noop("Active")),
               dict(val="not_active", text=ugettext_noop("Not Active"))]
