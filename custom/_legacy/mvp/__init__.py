from mvp.reports import mvis, chw, va, va_deidentifiedreport

CUSTOM_REPORTS = (
    ('Custom Reports', (
        mvis.HealthCoordinatorReport,
        chw.CHWManagerReport,
        va.VerbalAutopsyReport,
        va_deidentifiedreport.VerbalAutopsyDeidentifiedReport,
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

