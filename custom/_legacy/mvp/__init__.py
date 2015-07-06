from mvp.reports import mvis, chw, va, va_deintentifiedreport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        mvis.HealthCoordinatorReport,
        chw.CHWManagerReport,
        va.VerbalAutopsyReport,
        va_deintentifiedreport.VerbalAutopsyDeintentifiedReport,
    )),
)

from mvp.indicator_admin import custom

INDICATOR_ADMIN_INTERFACES = (
    ('MVP Custom Indicators', (
       custom.MVPDaysSinceLastTransmissionAdminInterface,
       custom.MVPActiveCasesAdminInterface,
       custom.MVPChildCasesByAgeAdminInterface,
    )),
)

