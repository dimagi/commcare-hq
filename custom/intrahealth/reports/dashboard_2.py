# coding=utf-8
from custom.intrahealth.filters import YeksiNaaLocationFilter, MonthsDateFilter, ProgramFilter
from custom.intrahealth.sqldata import LossRateData, ExpirationRateData, RecoveryRateByPPSData, \
    RecoveryRateByDistrictData
from custom.intrahealth.utils import MultiReport
from django.utils.functional import cached_property


class Dashboard2Report(MultiReport):
    title = "Tableau de Bord 2"
    fields = [MonthsDateFilter, ProgramFilter, YeksiNaaLocationFilter]
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
            ]
        else:
            return [
                LossRateData(config=config),
                ExpirationRateData(config=config),
                RecoveryRateByDistrictData(config=config),
                RecoveryRateByPPSData(config=config),
            ]
