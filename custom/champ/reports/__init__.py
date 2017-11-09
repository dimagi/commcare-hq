from custom.champ.reports.reports import PrevisionVsAchievementsGraphReport, ServicesUptakeReport, \
    PrevisionVsAchievementsTableReport

CUSTOM_REPORTS = (
    ('CUSTOM REPORTS', (
        PrevisionVsAchievementsGraphReport,
        PrevisionVsAchievementsTableReport,
        ServicesUptakeReport,
    )),
)
