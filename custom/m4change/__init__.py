from custom.m4change.reports import anc_hmis_report


CUSTOM_REPORTS = (
    ('Custom Reports', (
        anc_hmis_report.AncHmisReport,
    )),
)
