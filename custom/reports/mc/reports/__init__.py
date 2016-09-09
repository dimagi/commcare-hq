from . import sql

CUSTOM_REPORTS = (
    ('Custom Reports', (
        sql.DistrictMonthly,
        sql.HeathFacilityMonthly,
        sql.DistrictWeekly,
        sql.HealthFacilityWeekly,
    )),
)
