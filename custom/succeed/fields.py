from django.utils.translation import ugettext_noop
from corehq.apps.reports.fields import ReportSelectField


class CareSite(ReportSelectField):
    slug = "care_site"
    name = ugettext_noop("Care Site")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Sites"
    options = [dict(val="harbor", text=ugettext_noop("Harbor-UCLA")),
               dict(val="lac-usc", text=ugettext_noop("LAC-USC")),
               dict(val="oliveview", text=ugettext_noop("Olive View Medical Center")),
               dict(val="rancho", text=ugettext_noop("Rancho Los Amigos"))]


class ResponsibleParty(ReportSelectField):
    slug = "responsible_party"
    name = ugettext_noop("Responsible Party")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Roles"
    options = [
        dict(val="PM", text=ugettext_noop("Project Manager")),
        dict(val="CM", text=ugettext_noop("Care Manager")),
        dict(val="CHW", text=ugettext_noop("Community Health Worker")),
    ]


class PatientStatus(ReportSelectField):
    slug = "patient_status"
    name = ugettext_noop("Patient Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Patients"
    options = [dict(val="active", text=ugettext_noop("Active")),
               dict(val="not_active", text=ugettext_noop("Not Active"))]
