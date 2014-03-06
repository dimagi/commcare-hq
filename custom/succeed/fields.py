from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.reports.fields import ReportSelectField
from corehq.apps.users.models import CouchUser, WebUser


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
        harbor = dict(val="harbor", text=ugettext_noop("Harbor UCLA"))
        lac = dict(val="lac-usc", text=ugettext_noop("LAC-USC"))
        olive = dict(val="oliveview", text=ugettext_noop("Olive View Medical Center"))
        rancho = dict(val="rancho", text=ugettext_noop("Rancho Los Amigos"))
        if isinstance(user, WebUser) or user.get_role()['name'] == "Succeed Admin":
            options = [harbor, lac, olive, rancho]
        else:
            groups = user.get_group_ids()
            for group_id in groups:
                group = Group.get(group_id)
                if group.name == "Harbor UCLA":
                    options.append(harbor)
                elif group.name == "LAC-USC":
                    options.append(lac)
                elif group.name == "Olive View Medical Center":
                    options.append(olive)
                elif group.name == "Rancho Los Amigos":
                    options.append(rancho)
        return options


class ResponsibleParty(ReportSelectField):
    slug = "responsible_party"
    name = ugettext_noop("Responsible Party")
    cssId = "opened_closed"
    cssClasses = "span3"

    @property
    def options(self):
        user = self.request.couch_user
        cm = dict(val="CM", text=ugettext_noop("Care Manager"))
        chw = dict(val="CHW", text=ugettext_noop("Community Health Worker"))
        options = []
        if isinstance(user, WebUser) or user.get_role()['name'] == "Succeed Admin" or user.user_data['role'] in ['PM', 'PI']:
            options = [
                dict(val='', text=ugettext_noop("All Roles")),
                dict(val="PM", text=ugettext_noop("Project Manager")),
                cm,
                chw
            ]
        else:
            role = user.user_data['role']
            if role == 'CM':
                options.append(cm)
                self.selected = cm['val']
            elif role == 'CHW':
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
