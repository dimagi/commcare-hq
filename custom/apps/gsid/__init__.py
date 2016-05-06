from custom.apps.gsid.reports.sql_reports import GSIDSQLPatientReport, GSIDSQLByDayReport, GSIDSQLTestLotsReport, \
	GSIDSQLByAgeReport, PatientMapReport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        GSIDSQLPatientReport,
        GSIDSQLByDayReport,
        GSIDSQLTestLotsReport,
        GSIDSQLByAgeReport,
        PatientMapReport
    )),

)
