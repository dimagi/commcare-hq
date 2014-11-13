from corehq.apps.locations.models import Location
from custom.ilsgateway.reports import DeliverySubmissionData, LeadTimeHistory
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.ilsgateway.reports.stock_on_hand import DetailsReport


class DeliveryReport(DetailsReport):
    slug = "delivery_report"
    name = 'Delivery'
    title = 'Delivery Report'
    use_datatables = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    @memoized
    def data_providers(self):
        data_providers = [
            DeliverySubmissionData(config=self.report_config, css_class='row_chart_all'),
        ]
        config = self.report_config
        if config['location_id']:
            location = Location.get(config['location_id'])
            if location.location_type in ['REGION', 'MOHSW']:
                data_providers.append(LeadTimeHistory(config=config))
            else:
                pass
        return data_providers
