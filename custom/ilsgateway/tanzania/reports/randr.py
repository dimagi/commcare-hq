from datetime import datetime
from functools import partial
from corehq.apps.locations.models import SQLLocation, Location
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.ilsgateway.models import OrganizationSummary, GroupSummary, SupplyPointStatusTypes, DeliveryGroups
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.mixins import RandRSubmissionData
from custom.ilsgateway.tanzania.reports.utils import randr_value, get_default_contact_for_location, get_span, \
    rr_format_percent, link_format, make_url
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport
from django.utils.translation import ugettext as _


class RRStatus(ILSData):
    show_table = True
    title = "R&R Status"
    slug = "rr_status"
    show_chart = False

    @property
    def rows(self):
        rows = []
        locations = SQLLocation.objects.filter(parent_location_id=self.config['location_id'])
        for child in locations:
            try:
                org_summary = OrganizationSummary.objects.get(
                    date__range=(self.config['startdate'],
                                 self.config['enddate']),
                    supply_point=child.location_id
                )
            except OrganizationSummary.DoesNotExist:
                return []

            rr_data = GroupSummary.objects.get(
                title=SupplyPointStatusTypes.R_AND_R_FACILITY,
                org_summary=org_summary
            )

            fp_partial = partial(rr_format_percent, denominator=rr_data.total)

            total_responses = 0
            total_possible = 0
            group_summaries = GroupSummary.objects.filter(
                org_summary__date__lte=datetime(int(self.config['year']), int(self.config['month']), 1),
                org_summary__supply_point=child.location_id,
                title='rr_fac'
            )

            for g in group_summaries:
                if g:
                    total_responses += g.responded
                    total_possible += g.total
            hist_resp_rate = rr_format_percent(total_responses, total_possible)

            args = (child.location_id, self.config['month'], self.config['year'])

            url = make_url(RRreport, self.config['domain'], '?location_id=%s&month=%s&year=%s', args)

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

    def __init__(self, config=None, css_class='row_chart'):
        super(RRReportingHistory, self).__init__(config, css_class)
        self.config = config or {}
        self.css_class = css_class
        month = self.config.get('month')
        if month:
            self.title = "R&R Reporting History (Group %s)" % DeliveryGroups(int(month)).current_submitting_group()
        else:
            self.title = "R&R Reporting History"

    @property
    def rows(self):
        rows = []
        location = Location.get(self.config['location_id'])
        dg = DeliveryGroups().submitting(location.children, int(self.config['month']))
        for child in dg:
            total_responses = 0
            total_possible = 0
            group_summaries = GroupSummary.objects.filter(
                org_summary__date__lte=datetime(int(self.config['year']), int(self.config['month']), 1),
                org_summary__supply_point=child._id, title='rr_fac'
            )

            for g in group_summaries:
                if g:
                    total_responses += g.responded
                    total_possible += g.total
            hist_resp_rate = rr_format_percent(total_responses, total_possible)

            url = make_url(FacilityDetailsReport, self.config['domain'], '?location_id=%s', (child._id, ))

            rr_value = randr_value(child._id, int(self.config['month']), int(self.config['year']))
            contact = get_default_contact_for_location(self.config['domain'], child._id)

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
                    get_span(rr_value) % (format(rr_value, "d M Y") if rr_value else "Not reported"),
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
    title = 'R & R'
    use_datatables = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        data_providers = [RandRSubmissionData(config=config, css_class='row_chart_all')]
        if config['location_id']:
            location = Location.get(config['location_id'])
            if location.location_type in ['REGION', 'MOHSW']:
                data_providers.append(RRStatus(config=config, css_class='row_chart_all'))
            else:
                data_providers.append(RRReportingHistory(config=config, css_class='row_chart_all'))
        return data_providers