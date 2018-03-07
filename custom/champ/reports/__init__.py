from __future__ import absolute_import
from __future__ import unicode_literals
from custom.champ.reports.reports import PrevisionVsAchievementsGraphReport, ServicesUptakeReport, \
    PrevisionVsAchievementsTableReport

CUSTOM_REPORTS = (
    ('CUSTOM REPORTS', (
        PrevisionVsAchievementsGraphReport,
        PrevisionVsAchievementsTableReport,
        ServicesUptakeReport,
    )),
)
