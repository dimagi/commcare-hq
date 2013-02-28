from mvp.reports import mvis, chw

CUSTOM_REPORTS = (
    ('Custom Reports', (
        mvis.HealthCoordinatorReport,
        chw.CHWManagerReport
    )),
)

INDICATOR_ADMIN_INTERFACES = (
    ('Custom Indicator Types', (
       # todo fill this in
    )),
)
