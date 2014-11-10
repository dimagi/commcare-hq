from corehq.apps.locations.models import Location
from custom.ilsgateway.reports import RandRSubmissionData, RRStatus, RRReportingHistory
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.ilsgateway.reports.stock_on_hand import DetailsReport


class RRreport(DetailsReport):
    slug = "rr_report"
    name = 'R & R'
    title = 'R & R'
    use_datatables = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        location = Location.get(config['location_id'])
        data_providers = [RandRSubmissionData(config=config)]
        if location.location_type in ['REGION', 'MOHSW']:
            data_providers.append(RRStatus(config=config))
        else:
            data_providers.append(RRReportingHistory(config=config))
        return data_providers