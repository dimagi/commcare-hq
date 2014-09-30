from corehq.apps.reports.filters.dates import DatespanFilter
from custom.world_vision.filters import LocationFilter
from custom.world_vision.reports import TTCReport
from dimagi.utils.decorators.memoized import memoized
from custom.world_vision.sqldata import MotherRegistrationOverview, ClosedMotherCasesBreakdown, \
    PregnantMotherBreakdownByTrimester, DeliveryLiveBirthDetails, DeliveryStillBirthDetails, PostnatalCareOverview, \
    CauseOfMaternalDeaths, AnteNatalCareServiceOverviewExtended


class MotherTTCReport(TTCReport):
    report_title = 'Mother Report'
    name = 'Mother Report'
    slug = 'mother_report'
    fields = [DatespanFilter, LocationFilter]
    default_rows = 10
    exportable = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            MotherRegistrationOverview(config=config),
            ClosedMotherCasesBreakdown(config=config),
            PregnantMotherBreakdownByTrimester(config=config),
            AnteNatalCareServiceOverviewExtended(config=config),
            #DeliveryPlaceDetailsExtended(config=config),
            DeliveryLiveBirthDetails(config=config),
            DeliveryStillBirthDetails(config=config),
            PostnatalCareOverview(config=config),
            #FamilyPlanningMethods(config=config),
            CauseOfMaternalDeaths(config=config)
        ]