# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.yeksi_naa_reports.filters import LocationFilter, MonthsDateFilter
from custom.yeksi_naa_reports.sqldata import LossRateData, ExpirationRateData, RecoveryRateByPPSData, \
    RecoveryRateByDistrictData, RuptureRateByPPSData
from custom.yeksi_naa_reports.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard2Report(MultiReport):
    title = "Dashboard 2"
    fields = [MonthsDateFilter, LocationFilter]
    name = "Dashboard 2"
    slug = 'dashboard_2'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        config = self.report_config

        if 'district_id' in config or 'pps_id' in config:
            return [
                LossRateData(config=config),
                ExpirationRateData(config=config),
                RecoveryRateByPPSData(config=config),
                RuptureRateByPPSData(config=config),
            ]
        else:
            return [
                LossRateData(config=config),
                ExpirationRateData(config=config),
                RecoveryRateByDistrictData(config=config),
                RuptureRateByPPSData(config=config),
            ]
