from pact.reports import patient_list, dot, patient, chw_list, chw, admin_reports, admin_dot_reports, admin_chw_reports

CUSTOM_REPORTS = (
    ("PACT Reports", (
        patient_list.PatientListDashboardReport,
        dot.PactDOTReport,
        patient.PactPatientInfoReport,
        chw_list.PactCHWDashboard,
        chw.PactCHWProfileReport,
        admin_reports.PactAdminReport,
        admin_dot_reports.PactDOTAdminReport,
        admin_chw_reports.PactCHWAdminReport,
        )),
    )
