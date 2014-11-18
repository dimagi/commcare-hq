from datetime import datetime
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport
from custom.ilsgateway.models import OrganizationSummary, DeliveryGroups, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reports.mixins import DeliverySubmissionData
from custom.ilsgateway.tanzania.reports.utils import make_url, link_format, latest_status_or_none,\
    get_this_lead_time, get_avg_lead_time
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from django.utils.translation import ugettext as _


class LeadTimeHistory(ILSData):
    show_table = True
    title = "Lead Time History"
    slug = "lead_time_history"
    show_chart = False

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Average Lead Time In Days'))
        )

    @property
    def rows(self):
        locations = SQLLocation.objects.filter(parent_location_id=self.config['location_id'])
        date = datetime(int(self.config['year']), int(self.config['month']), 1)
        rows = []
        for loc in locations:
            try:
                org_summary = OrganizationSummary.objects.get(supply_point=loc.location_id, date=date)
            except OrganizationSummary.DoesNotExist:
                continue

            avg_lead_time = org_summary.average_lead_time_in_days

            if avg_lead_time:
                avg_lead_time = "%.1f" % avg_lead_time
            else:
                avg_lead_time = "None"

            args = (loc.location_id, self.config['month'], self.config['year'])
            url = make_url(DeliveryReport, self.config['domain'], '?location_id=%s&month=%s&year=%s', args)

            rows.append([link_format(loc.name, url), avg_lead_time])
        return rows


class DeliveryStatus(ILSData):
    show_table = True
    slug = "delivery_status"
    show_chart = False

    def __init__(self, config=None, css_class='row_chart'):
        super(DeliveryStatus, self).__init__(config, css_class)
        self.config = config or {}
        self.css_class = css_class
        month = self.config.get('month')
        if month:
            self.title = "Delivery Status: Group " + DeliveryGroups(int(month)).current_delivering_group()
        else:
            self.title = "Delivery Status"

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Code')),
            DataTablesColumn(_('Facility Name')),
            DataTablesColumn(_('Delivery Status')),
            DataTablesColumn(_('Delivery Date')),
            DataTablesColumn(_('This Cycle Lead Time')),
            DataTablesColumn(_('Average Lead Time In Days'))
        )

    @property
    def rows(self):
        rows = []
        locations = SQLLocation.objects.filter(parent_location_id=self.config['location_id'])
        dg = DeliveryGroups().delivering(locations, int(self.config['month']))
        for child in dg:
            latest = latest_status_or_none(
                child.location_id,
                SupplyPointStatusTypes.DELIVERY_FACILITY,
                int(self.config['month']),
                int(self.config['year'])
            )
            status_name = latest.name if latest else ""
            status_date = format(latest.status_date, "d M Y") if latest else "None"

            url = make_url(FacilityDetailsReport, self.config['domain'], '?location_id=%s', (child.location_id, ))

            cycle_lead_time = get_this_lead_time(
                child.location_id,
                int(self.config['month']),
                int(self.config['year'])
            )
            avg_lead_time = get_avg_lead_time(child.location_id, int(self.config['month']),
                                              int(self.config['year']))
            rows.append(
                [
                    child.site_code,
                    link_format(child.name, url),
                    status_name,
                    status_date,
                    cycle_lead_time,
                    avg_lead_time
                ]
            )
        return rows


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
            location = SQLLocation.objects.get(location_id=config['location_id'])
            if location.location_type in ['REGION', 'MOHSW']:
                data_providers.append(LeadTimeHistory(config=config, css_class='row_chart_all'))
            else:
                data_providers.append(DeliveryStatus(config=config, css_class='row_chart_all'))
        return data_providers
