from custom.icds_reports.reports import IcdsBaseReport
from custom.icds_reports.sqldata import Identification, Operationalization, Sectors, Population, BirthsAndDeaths
from dimagi.utils.decorators.memoized import memoized


class BasicInfoReport(IcdsBaseReport):

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            Identification(config=config),
            Operationalization(config=config),
            Sectors(config=config),
            Population(config=config),
            BirthsAndDeaths(config=config),
            AWCDetails(config=config)
        ]
