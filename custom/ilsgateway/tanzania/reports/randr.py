from functools import partial
from dateutil import rrule
from corehq.apps.locations.dbaccessors import get_one_user_at_location
from corehq.apps.locations.models import SQLLocation, Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.filters import ProgramFilter, ILSDateFilter
from custom.ilsgateway.models import OrganizationSummary, GroupSummary, SupplyPointStatusTypes, DeliveryGroups
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.mixins import RandRSubmissionData
from custom.ilsgateway.tanzania.reports.utils import randr_value, get_span, \
    rr_format_percent, link_format, make_url
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport, InventoryHistoryData, \
    RegistrationData, RandRHistory, Notes, RecentMessages
from django.utils.translation import ugettext as _


class RRStatus(ILSData):
    show_table = True
    title = "R&R Status"
    slug = "rr_status"
    show_chart = False
    searchable = True

    @property
    def rows(self):
        rows = []
        if self.config['org_summary']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for child in locations:
                try:
                    org_summary = OrganizationSummary.objects.filter(
                        date__range=(self.config['startdate'], self.config['enddate']),
                        location_id=child.location_id
                    )
                except OrganizationSummary.DoesNotExist:
                    return []

                self.config['org_summary'] = org_summary
                rr_data = RandRSubmissionData(config=self.config).rows[0]

                fp_partial = partial(rr_format_percent, denominator=rr_data.total)

                total_responses = 0
                total_possible = 0
                group_summaries = GroupSummary.objects.filter(
                    org_summary__date__lte=self.config['startdate'],
                    org_summary__location_id=child.location_id,
                    title=SupplyPointStatusTypes.R_AND_R_FACILITY
                )

                for group_summary in group_summaries:
                    if group_summary:
                        total_responses += group_summary.responded
                        total_possible += group_summary.total
                hist_resp_rate = rr_format_percent(total_responses, total_possible)

                url = make_url(RRreport, self.config['domain'],
                               '?location_id=%s&filter_by_program=%s&'
                               'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                               (child.location_id,
                                self.config['program'], self.config['datespan_type'],
                                self.config['datespan_first'], self.config['datespan_second']))

                rows.append(
                    [
                        link_format(child.name, url),
                        fp_partial(rr_data.on_time),
                        fp_partial(rr_data.late),
                        fp_partial(rr_data.not_submitted),
                        fp_partial(rr_data.not_responding),
                        hist_resp_rate
                    ]
                )

        return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('% Facilities Submitting R&R On Time')),
            DataTablesColumn(_("% Facilities Submitting R&R Late")),
            DataTablesColumn(_("% Facilities With R&R Not Submitted")),
            DataTablesColumn(_("% Facilities Not Responding To R&R Reminder")),
            DataTablesColumn(_("Historical Response Rate"))
        )


class RRReportingHistory(ILSData):
    show_table = True
    slug = "rr_reporting_history"
    show_chart = False
    searchable = True

    def __init__(self, config=None, css_class='row_chart'):
        super(RRReportingHistory, self).__init__(config, css_class)
        self.config = config or {}
        self.css_class = css_class
        datespan_type = self.config.get('datespan_type')
        if datespan_type == 1:
            self.title = "R&R Reporting History (Group %s)" %\
                         DeliveryGroups(int(self.config['datespan_first'])).current_submitting_group()
        else:
            self.title = "R&R Reporting History"

    @property
    def rows(self):
        rows = []
        locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
        dg = []
        for date in list(rrule.rrule(rrule.MONTHLY, dtstart=self.config['startdate'],
                                     until=self.config['enddate'])):
            dg.extend(DeliveryGroups().submitting(locations, date.month))

        for child in dg:
            total_responses = 0
            total_possible = 0
            submitted, rr_value = randr_value(child.location_id, self.config['startdate'], self.config['enddate'])
            if child.is_archived and not rr_value:
                continue

            group_summaries = GroupSummary.objects.filter(
                org_summary__date__lte=self.config['startdate'],
                org_summary__location_id=child.location_id,
                title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                total=1
            )

            if not group_summaries:
                continue

            for group_summary in group_summaries:
                if group_summary:
                    total_responses += group_summary.responded
                    total_possible += group_summary.total
            hist_resp_rate = rr_format_percent(total_responses, total_possible)

            url = make_url(FacilityDetailsReport, self.config['domain'],
                           '?location_id=%s&filter_by_program=%s&'
                           'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                           (child.location_id,
                            self.config['program'], self.config['datespan_type'],
                            self.config['datespan_first'], self.config['datespan_second']))

            contact = get_one_user_at_location(self.config['domain'], child.location_id)

            if contact:
                role = contact.user_data.get('role') or ""
                args = (contact.first_name, contact.last_name, role, contact.default_phone_number)
                contact_string = "%s %s (%s) %s" % args
            else:
                contact_string = ""

            rows.append(
                [
                    child.site_code,
                    link_format(child.name, url),
                    get_span(submitted) % (rr_value.strftime("%d %b %Y") if rr_value else "Not reported"),
                    contact_string,
                    hist_resp_rate
                ]
            )

        return rows

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Code')),
            DataTablesColumn(_('Facility Name')),
            DataTablesColumn(_('R&R Status')),
            DataTablesColumn(_('Contact')),
            DataTablesColumn(_('Historical Response Rate'))
        )


class RRreport(DetailsReport):
    slug = "rr_report"
    name = 'R & R'
    use_datatables = True

    @property
    def title(self):
        title = _('R & R {0}'.format(self.title_month))
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            return "{0} ({1}) Group {2}".format(self.location.name,
                                                self.location.site_code,
                                                self.location.metadata.get('group', '---'))
        return title

    @property
    def fields(self):
        fields = [AsyncLocationFilter, ILSDateFilter, ProgramFilter]
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            fields = []
        return fields

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        data_providers = []
        if config['location_id']:
            data_providers = [RandRSubmissionData(config=config, css_class='row_chart_all')]
            location = Location.get(config['location_id'])
            if location.location_type in ['REGION', 'MSDZONE', 'MOHSW']:
                data_providers.append(RRStatus(config=config, css_class='row_chart_all'))
            elif location.location_type == 'FACILITY':
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
                data_providers.append(RRReportingHistory(config=config, css_class='row_chart_all'))
        return data_providers

    @property
    def report_context(self):
        ret = super(RRreport, self).report_context
        ret['view_mode'] = 'ror'
        return ret
