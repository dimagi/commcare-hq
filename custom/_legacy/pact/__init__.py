from pact.reports import patient_list, dot, patient, chw_list, chw, admin_reports, admin_dot_reports, admin_chw_reports
from corehq.preindex import ExtraPreindexPlugin
from django.conf import settings

ExtraPreindexPlugin('pact', __file__, (None, settings.NEW_CASES_DB))

CUSTOM_REPORTS = (
    ("PACT Reports", (
        patient_list.PatientListDashboardReport,
        dot.PactDOTReport,
        patient.PactPatientInfoReport,
        chw_list.PactCHWDashboard,
        chw.PactCHWProfileReport,
        # admin_reports.PactAdminReport, #TODO
        admin_dot_reports.PactDOTAdminReport,
        admin_chw_reports.PactCHWAdminReport,
        )),
    )
