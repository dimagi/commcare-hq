from .reports import sql

CUSTOM_REPORTS = (
    ('Custom Reports', (
        sql.HeathFacilityMonthly,
        sql.DistrictMonthly,
    )),
)
