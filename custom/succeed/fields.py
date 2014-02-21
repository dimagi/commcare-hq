from django.utils.translation import ugettext_noop
from corehq.apps.reports.fields import ReportSelectField


class CareSite(ReportSelectField):
    slug = "care_site"
    name = ugettext_noop("Care Site")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Sites"
    options = [dict(val="Harbor-UCLA", text=ugettext_noop("Harbor-UCLA")),
               dict(val="LAC-USC", text=ugettext_noop("LAC-USC")),
               dict(val="Olive View Medical Center", text=ugettext_noop("Olive View Medical Center")),
               dict(val="Rancho Los Amigos", text=ugettext_noop("Rancho Los Amigos"))]


class ResponsibleParty(ReportSelectField):
    slug = "responsible_party"
    name = ugettext_noop("Responsible Party")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Roles"
    options = [dict(val="Care Manager", text=ugettext_noop("Care Manager")),
               dict(val="Community Health Worker", text=ugettext_noop("Community Health Worker"))]


class PatientStatus(ReportSelectField):
    slug = "patient_status"
    name = ugettext_noop("Patient Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Patients"
    options = [dict(val="Active", text=ugettext_noop("Active")),
               dict(val="Not Active", text=ugettext_noop("Not Active"))]
