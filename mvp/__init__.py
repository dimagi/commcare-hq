from mvp.reports import mvis, chw

CUSTOM_REPORTS = (
    ('Custom Reports', (
        mvis.HealthCoordinatorReport,
        chw.CHWManagerReport
    )),
)
