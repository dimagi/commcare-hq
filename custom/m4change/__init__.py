from custom.m4change.reports import anc_hmis_report, ld_hmis_report, immunization_hmis_report, all_hmis_report,\
    project_indicators_report, mcct_monthly_aggregate_report

CUSTOM_REPORTS = (
    ('Custom Reports', (
        anc_hmis_report.AncHmisReport,
        ld_hmis_report.LdHmisReport,
        immunization_hmis_report.ImmunizationHmisReport,
        all_hmis_report.AllHmisReport,
        project_indicators_report.ProjectIndicatorsReport,
        mcct_monthly_aggregate_report.McctMonthlyAggregateReport
    )),
)
