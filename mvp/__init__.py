from mvp.reports import mvis, chw

CUSTOM_REPORTS = (
    ('Custom Reports', (
        mvis.HealthCoordinatorReport,
        chw.CHWManagerReport
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

