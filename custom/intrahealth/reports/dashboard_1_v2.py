# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.intrahealth.filters import YeksiNaaLocationFilter, DateRangeFilter, ProgramsAndProductsFilter
from custom.intrahealth.sqldata import AvailabilityData, RuptureRateByPPSData
from custom.intrahealth.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard1ReportV2(MultiReport):
    title = "Tableau de Bord 1 v2"
    fields = [DateRangeFilter, ProgramsAndProductsFilter, YeksiNaaLocationFilter]
    name = "Tableau de Bord 1 v2"
    slug = 'tableau_de_bord_1_v2'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            AvailabilityData(config=self.report_config),
            RuptureRateByPPSData(config=self.report_config),
        ]
