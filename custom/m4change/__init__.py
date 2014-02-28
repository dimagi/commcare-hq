from custom.m4change.reports import anc_hmis_report, immunization_hmis_report, project_indicators_report

CUSTOM_REPORTS = (
    ('Custom Reports', (
        anc_hmis_report.AncHmisReport,
        immunization_hmis_report.ImmunizationHmisReport,
        project_indicators_report.ProjectIndicatorsReport
    )),
)
