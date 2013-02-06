from pact.reports import patient_list, dot, patient, chw_list, chw

CUSTOM_REPORTS = (
    ("PACT Reports", (
        patient_list.PatientListDashboardReport,
        dot.PactDOTReport,
        patient.PactPatientInfoReport,
        chw_list.PactCHWDashboard,
        chw.PactCHWProfileReport,
        )),
    )

from pact import api