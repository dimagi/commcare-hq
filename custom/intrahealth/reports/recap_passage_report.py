from corehq.apps.reports.standard import MonthYearMixin
from custom.intrahealth.filters import RecapPassageLocationFilter, FRMonthFilter, FRYearFilter
from custom.intrahealth.reports.tableu_de_board_report import MultiReport
from custom.intrahealth.sqldata import RecapPassageData, DateSource
from dimagi.utils.decorators.memoized import memoized

class RecapPassageReport(MonthYearMixin, MultiReport):
    title = "Recap Passage"
    name = "Recap Passage"
    slug = 'recap_passage'
    report_title = "Recap Passage"
    exportable = True
    default_rows = 10
    fields = [FRMonthFilter, FRYearFilter, RecapPassageLocationFilter]

    def config_update(self, config):
        if self.request.GET.get('location_id', ''):
            if self.location.location_type.lower() == 'pps':
                config.update(dict(PPS_name=self.location.name))

    @property
    @memoized
    def data_providers(self):
        dates = sorted(sum(DateSource(config=self.report_config).rows, []))
        data_providers = []
        for date in dates:
            config = self.report_config
            config.update(dict(startdate=date, enddate=date))
            data_providers.append(RecapPassageData(config=config))
        if not data_providers:
            data_providers.append(RecapPassageData(config=self.report_config))
        return data_providers
