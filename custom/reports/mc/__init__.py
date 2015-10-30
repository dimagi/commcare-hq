from .reports import old_sql
from .reports import sql


CUSTOM_REPORTS = (
    ('Custom Reports', (
        old_sql.DistrictMonthly,
        old_sql.HeathFacilityMonthly,
        old_sql.DistrictWeekly,
        old_sql.HealthFacilityWeekly,
        sql.DistrictMonthly,
        sql.HeathFacilityMonthly,
        sql.DistrictWeekly,
        sql.HealthFacilityWeekly,
    )),
)
