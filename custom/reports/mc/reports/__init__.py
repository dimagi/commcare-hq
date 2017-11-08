from __future__ import absolute_import
from . import sql

CUSTOM_REPORTS = (
    ('Custom Reports', (
        sql.DistrictMonthly,
        sql.HeathFacilityMonthly,
        sql.DistrictWeekly,
        sql.HealthFacilityWeekly,
    )),
)
