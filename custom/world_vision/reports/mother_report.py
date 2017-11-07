from __future__ import absolute_import
from custom.world_vision.filters import LocationFilter, WVDatespanFilter
from custom.world_vision.reports import AccordionTTCReport
from custom.world_vision.sqldata.mother_sqldata import MotherRegistrationDetails, ClosedMotherCasesBreakdown, \
    PregnantMotherBreakdownByTrimester, AnteNatalCareServiceOverviewExtended, DeliveryLiveBirthDetails, \
    DeliveryStillBirthDetails, PostnatalCareOverview, CauseOfMaternalDeaths, FamilyPlanningMethods, \
    DeliveryPlaceMotherDetails, DeliveryPlaceDetailsExtended, NumberOfPNCVisits
from dimagi.utils.decorators.memoized import memoized


class MotherTTCReport(AccordionTTCReport):
    report_template_path = 'world_vision/accordion_report.html'
    report_title = 'Mother Report'
    title = 'Mother Report'
    name = 'Mother Report'
    slug = 'mother_report'
    fields = [WVDatespanFilter, LocationFilter]
    default_rows = 10
    exportable = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            [MotherRegistrationDetails(config=config)],
            [ClosedMotherCasesBreakdown(config=config)],
            [PregnantMotherBreakdownByTrimester(config=config)],
            [AnteNatalCareServiceOverviewExtended(config=config)],
            [
                DeliveryPlaceDetailsExtended(config=config),
                DeliveryPlaceMotherDetails(config=config),
                DeliveryLiveBirthDetails(config=config),
                DeliveryStillBirthDetails(config=config)
            ],
            [
                PostnatalCareOverview(config=config),
                NumberOfPNCVisits(config=config)
            ],
            [FamilyPlanningMethods(config=config)],
            [CauseOfMaternalDeaths(config=config)]
        ]
