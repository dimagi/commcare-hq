from .reports import sql

CUSTOM_REPORTS = (
    ('Custom Reports', (
        sql.TestingAndCounseling,
        sql.CareAndTBHIV,
        sql.IACT,
    )),
)
