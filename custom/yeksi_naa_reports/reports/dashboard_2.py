# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from custom.yeksi_naa_reports.filters import LocationFilter, MonthsDateFilter
from custom.yeksi_naa_reports.sqldata import LossRateData, ExpirationRateData, RecoveryRateByPPSData, \
    RecoveryRateByDistrictData, RuptureRateByPPSData
from custom.yeksi_naa_reports.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard2Report(MultiReport):
    title = "Tableau de Bord 2"
    fields = [MonthsDateFilter, LocationFilter]
    name = "Tableau de Bord 2"
    slug = 'tableau_de_bord_2'
    default_rows = 10
    exportable = True

    @cached_property
    def data_providers(self):
        config = self.report_config

        if 'pps_id' in config:
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
                RecoveryRateByPPSData(config=config),
                RuptureRateByPPSData(config=config),
            ]
