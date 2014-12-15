from corehq.apps.reports.filters.dates import DatespanFilter
from custom.world_vision.filters import LocationFilter, WVDatespanFilter
from custom.world_vision.reports import TTCReport
from custom.world_vision.sqldata.child_sqldata import ChildRegistrationDetails, ClosedChildCasesBreakdown, \
    ChildrenDeaths, ChildrenDeathDetails, NutritionMeanMedianBirthWeightDetails, NutritionBirthWeightDetails, \
    NutritionFeedingDetails, ChildHealthIndicators
from custom.world_vision.sqldata.main_sqldata import AnteNatalCareServiceOverview, DeliveryPlaceDetails, \
    ImmunizationOverview
from custom.world_vision.sqldata.mother_sqldata import MotherRegistrationDetails, ClosedMotherCasesBreakdown, \
    PregnantMotherBreakdownByTrimester, DeliveryLiveBirthDetails, DeliveryStillBirthDetails, PostnatalCareOverview, \
    CauseOfMaternalDeaths, AnteNatalCareServiceOverviewExtended
from dimagi.utils.decorators.memoized import memoized


class MixedTTCReport(TTCReport):
    report_title = 'TTC Overview Report'
    name = 'TTC Overview Report'
    slug = 'mother_child_report'
    title = "TTC Overview Report"
    fields = [WVDatespanFilter, LocationFilter]
    default_rows = 10
    exportable = True
    is_mixed_report = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            MotherRegistrationDetails(config=config),
            ClosedMotherCasesBreakdown(config=config),
            PregnantMotherBreakdownByTrimester(config=config),
            AnteNatalCareServiceOverview(config=config),
            DeliveryPlaceDetails(config=config),
            DeliveryStillBirthDetails(config=config),
            DeliveryLiveBirthDetails(config=config),
            PostnatalCareOverview(config=config),
            AnteNatalCareServiceOverviewExtended(config=config),
            CauseOfMaternalDeaths(config=config),
            ChildRegistrationDetails(config=config),
            ClosedChildCasesBreakdown(config=config),
            ImmunizationOverview(config=config),
            ChildrenDeaths(config=config),
            NutritionMeanMedianBirthWeightDetails(config=config),
            NutritionBirthWeightDetails(config=config),
            NutritionFeedingDetails(config=config),
            ChildHealthIndicators(config=config)
        ]