from dateutil import rrule
from django.db.models.aggregates import Avg
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.ilsgateway.filters import ProgramFilter, ILSDateFilter, ILSAsyncLocationFilter
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport, InventoryHistoryData, \
    RegistrationData, RandRHistory, Notes, RecentMessages
from custom.ilsgateway.models import OrganizationSummary, DeliveryGroups, SupplyPointStatusTypes, GroupSummary
from custom.ilsgateway.tanzania.reports.mixins import DeliverySubmissionData
from custom.ilsgateway.tanzania.reports.utils import make_url, link_format, latest_status_or_none,\
    get_this_lead_time, get_avg_lead_time
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


class LeadTimeHistory(ILSData):
    show_table = True
    title = "Lead Time History"
    slug = "lead_time_history"
    show_chart = False
    searchable = True
    use_datatables = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Average Lead Time In Days'))
        )

    @property
    def rows(self):
        locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
        rows = []
        for loc in locations:
            try:
                org_summary = OrganizationSummary.objects.filter(
                    location_id=loc.location_id,
                    date__range=(self.config['startdate'], self.config['enddate'])
                ).aggregate(average_lead_time_in_days=Avg('average_lead_time_in_days'))
            except OrganizationSummary.DoesNotExist:
                continue

            avg_lead_time = org_summary['average_lead_time_in_days']

            if avg_lead_time:
                avg_lead_time = "%.1f" % avg_lead_time
            else:
                avg_lead_time = "None"

            url = make_url(DeliveryReport, self.config['domain'],
                           '?location_id=%s&filter_by_program=%s&'
                           'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                           (loc.location_id,
                            self.config['program'], self.config['datespan_type'],
                            self.config['datespan_first'], self.config['datespan_second']))

            rows.append([link_format(loc.name, url), avg_lead_time])
        return rows


class DeliveryStatus(ILSData):
    show_table = True
    slug = "delivery_status"
    show_chart = False
    searchable = True

    def __init__(self, config=None, css_class='row_chart'):
        super(DeliveryStatus, self).__init__(config, css_class)
        self.config = config or {}
        self.css_class = css_class
        datespan_type = self.config.get('datespan_type')
        if datespan_type == 1:
            self.title = "Delivery Status: Group %s" %\
                         DeliveryGroups(int(self.config['datespan_first'])).current_delivering_group()
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
        locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
        dg = []
        for date in list(rrule.rrule(rrule.MONTHLY, dtstart=self.config['startdate'],
                                     until=self.config['enddate'])):
            dg.extend(DeliveryGroups().delivering(locations, date.month))

        for child in dg:
            group_summary = GroupSummary.objects.filter(
                org_summary__date__lte=self.config['startdate'],
                org_summary__location_id=child.location_id,
                title=SupplyPointStatusTypes.DELIVERY_FACILITY,
                total=1
            ).exists()
            if not group_summary:
                continue

            latest = latest_status_or_none(
                child.location_id,
                SupplyPointStatusTypes.DELIVERY_FACILITY,
                self.config['startdate'],
                self.config['enddate']
            )
            status_name = latest.name if latest else ""
            status_date = latest.status_date.strftime("%d-%m-%Y") if latest else "None"

            url = make_url(FacilityDetailsReport, self.config['domain'],
                           '?location_id=%s&filter_by_program=%s&'
                           'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                           (child.location_id,
                            self.config['program'], self.config['datespan_type'],
                            self.config['datespan_first'], self.config['datespan_second']))

            cycle_lead_time = get_this_lead_time(
                child.location_id,
                self.config['startdate'],
                self.config['enddate']
            )
            avg_lead_time = get_avg_lead_time(child.location_id, self.config['startdate'],
                                              self.config['enddate'])
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


class DeliveryData(ILSData):
    show_table = True
    show_chart = False
    slug = 'delivery_data'
    title = 'Delivery Data'
    searchable = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Category'), sort_direction="desc"),
            DataTablesColumn(_('# Facilities')),
            DataTablesColumn(_('% of total')),
        )

    @property
    def rows(self):
        data = DeliverySubmissionData(config=self.config, css_class='row_chart_all').rows

        if data:
            dg = data[0]
            percent_format = lambda x, y: x * 100 / (y or 1)

            return [
                [_('Didn\'t Respond'), '%d' % dg.not_responding,
                 '%.1f%%' % percent_format(dg.not_responding, dg.total)],
                [_('Not Received'), '%d' % dg.not_received, '%.1f%%' % percent_format(dg.not_received, dg.total)],
                [_('Received'), '%d' % dg.received, '%.1f%%' % percent_format(dg.received, dg.total)],
                [_('Total'), '%d' % dg.total, '100%'],
            ]


class DeliveryReport(DetailsReport):
    slug = "delivery_report"
    name = 'Delivery'
    use_datatables = True

    @property
    def title(self):
        title = _('Delivery Report {0}'.format(self.title_month))
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            return "{0} ({1}) Group {2}".format(self.location.name,
                                                self.location.site_code,
                                                self.location.metadata.get('group', '---'))
        return title

    @property
    def fields(self):
        fields = [ILSAsyncLocationFilter, ILSDateFilter, ProgramFilter]
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            fields = []
        return fields

    @property
    @memoized
    def data_providers(self):
        data_providers = [
            DeliverySubmissionData(config=self.report_config, css_class='row_chart_all'),
        ]
        config = self.report_config
        if config['location_id']:
            location = SQLLocation.objects.get(location_id=config['location_id'])
            if location.location_type.name.upper() in ['REGION', 'MSDZONE', 'MOHSW']:
                data_providers.append(DeliveryData(config=config, css_class='row_chart_all'))
                data_providers.append(LeadTimeHistory(config=config, css_class='row_chart_all'))
            elif location.location_type.name.upper() == 'FACILITY':
                return [
                    InventoryHistoryData(config=config),
                    RandRHistory(config=config),
                    Notes(config=config),
                    RecentMessages(config=config),
                    RegistrationData(config=dict(loc_type='FACILITY', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='DISTRICT', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='REGION', **config), css_class='row_chart_all')
                ]
            else:
                data_providers.append(DeliveryStatus(config=config, css_class='row_chart_all'))
        return data_providers

    @property
    def report_context(self):
        ret = super(DeliveryReport, self).report_context
        ret['view_mode'] = 'delivery'
        return ret
