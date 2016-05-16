from custom.world_vision.reports import AccordionTTCReport
from custom.world_vision.filters import LocationFilter, WVDatespanFilter
from custom.world_vision.sqldata.child_sqldata import ImmunizationDetailsFirstYear, \
    ImmunizationDetailsSecondYear, ChildDeworming, ChildRegistrationDetails, ClosedChildCasesBreakdown, \
    ChildrenDeaths, ChildrenDeathDetails, NutritionMeanMedianBirthWeightDetails, NutritionBirthWeightDetails,\
    NutritionFeedingDetails, EBFStoppingDetails, ChildHealthIndicators, ChildrenDeathsByMonth
from dimagi.utils.decorators.memoized import memoized


class ChildTTCReport(AccordionTTCReport):
    report_template_path = 'world_vision/accordion_report.html'
    report_title = 'Child Report'
    name = 'Child Report'
    title = 'Child Report'
    slug = 'child_report'
    fields = [WVDatespanFilter, LocationFilter]
    default_rows = 25
    exportable = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            [ChildRegistrationDetails(config=config)],
            [ClosedChildCasesBreakdown(config=config)],
            [ImmunizationDetailsFirstYear(config=config)],
            [ImmunizationDetailsSecondYear(config=config)],
            [
                ChildrenDeaths(config=config),
                ChildrenDeathDetails(config=config),
                ChildrenDeathsByMonth(config=config)
            ],
            [
                NutritionMeanMedianBirthWeightDetails(config=config),
                NutritionBirthWeightDetails(config=config),
                NutritionFeedingDetails(config=config)
            ],
            [EBFStoppingDetails(config=config)],
            [ChildHealthIndicators(config=config)],
            [ChildDeworming(config=config)]
        ]
