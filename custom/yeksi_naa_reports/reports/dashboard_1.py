# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.yeksi_naa_reports.filters import LocationFilter, MonthsDateFilter
from custom.yeksi_naa_reports.sqldata import AvailabilityData
from custom.yeksi_naa_reports.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard1Report(MultiReport):
    title = "Dashboard 1"
    fields = [MonthsDateFilter, LocationFilter]
    name = "Dashboard 1"
    slug = 'dashboard_1'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        return [
            AvailabilityData(config=self.report_config),
        ]
