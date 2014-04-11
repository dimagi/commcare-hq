from custom.m4change.reports import anc_hmis_report, ld_hmis_report, immunization_hmis_report, all_hmis_report,\
    project_indicators_report, mcct_monthly_aggregate_report, aggregate_facility_web_hmis_report, mcct_project_review

CUSTOM_REPORTS = (
    ('Custom Reports', (
        anc_hmis_report.AncHmisReport,
        ld_hmis_report.LdHmisReport,
        immunization_hmis_report.ImmunizationHmisReport,
        all_hmis_report.AllHmisReport,
        project_indicators_report.ProjectIndicatorsReport,
        aggregate_facility_web_hmis_report.AggregateFacilityWebHmisReport,
        mcct_project_review.McctProjectReview,
        mcct_project_review.McctClientApprovalPage,
        mcct_project_review.McctClientPaymentPage,
        mcct_project_review.McctPaidClientsPage,
        mcct_project_review.McctRejectedClientPage,
        mcct_project_review.McctClientLogPage,
        mcct_monthly_aggregate_report.McctMonthlyAggregateReport
    )),
)
