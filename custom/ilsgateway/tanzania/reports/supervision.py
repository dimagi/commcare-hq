from django.db.models.aggregates import Avg, Max
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.filters import ProgramFilter, ILSDateFilter
from corehq.apps.reports.filters.select import YearFilter
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, OrganizationSummary
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.utils import make_url, format_percent, link_format, latest_status_or_none
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport, InventoryHistoryData, \
    RegistrationData, RandRHistory, Notes, RecentMessages
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


class SupervisionSummaryData(ILSData):
    title = 'Supervision Summary'
    slug = 'supervision_summary'

    @property
    def rows(self):
        if self.config['org_summary']:
            data = GroupSummary.objects.filter(
                title=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                org_summary__in=self.config['org_summary']
            ).aggregate(Avg('responded'), Avg('on_time'), Avg('complete'), Max('total'))

            return [GroupSummary(
                title=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                responded=data['responded__avg'],
                on_time=data['on_time__avg'],
                complete=data['complete__avg'],
                total=data['total__max']
            )]
        else:
            return [
                GroupSummary(
                    title=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                    responded=0,
                    on_time=0,
                    complete=0,
                    total=0
                )
            ]


class SupervisionData(ILSData):
    title = 'Supervision'
    slug = 'supervision_table'
    show_chart = False
    show_table = True
    searchable = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('% Supervision Received')),
            DataTablesColumn(_('% Supervision Not Received')),
            DataTablesColumn(_('% Supervision Not Responding')),
            DataTablesColumn(_('Historical Response Rate')),
        )

    @property
    def rows(self):
        rows = []
        if self.config['location_id'] and self.config['org_summary']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                facilities = loc.get_descendants().filter(location_type__administrative=False).count()
                org_summary = OrganizationSummary.objects.filter(
                    date__range=(self.config['startdate'], self.config['enddate']),
                    location_id=loc.location_id
                )
                self.config['org_summary'] = org_summary
                soh_data = SupervisionSummaryData(config=self.config).rows[0]

                total_responses = 0
                total_possible = 0
                for group_summary in GroupSummary.objects.filter(
                        org_summary__date__lte=self.config['startdate'],
                        org_summary__location_id=loc.location_id,
                        title=SupplyPointStatusTypes.SUPERVISION_FACILITY
                ):
                    if group_summary:
                        total_responses += group_summary.responded
                        total_possible += group_summary.total

                if total_possible:
                    response_rate = "%.1f%%" % (100.0 * total_responses / total_possible)
                else:
                    response_rate = "<span class='no_data'>None</span>"

                url = make_url(SupervisionReport, self.config['domain'],
                               '?location_id=%s&filter_by_program=%s&'
                               'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                               (loc.location_id,
                                self.config['program'], self.config['datespan_type'],
                                self.config['datespan_first'], self.config['datespan_second']))

                rows.append([
                    link_format(loc.name, url),
                    format_percent(float(soh_data.received) * 100 / float(facilities or 1)),
                    format_percent(float(soh_data.not_received) * 100 / float(facilities or 1)),
                    format_percent(float(soh_data.not_responding) * 100 / float(facilities or 1)),
                    response_rate
                ])
        return rows


class DistrictSupervisionData(ILSData):
    title = 'Supervision'
    slug = 'district_supervision_table'
    show_chart = False
    show_table = True
    searchable = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('MSD Code')),
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Supervision This Quarter')),
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Historical Response Rate')),
        )

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                total_responses = 0
                total_possible = 0
                group_summaries = GroupSummary.objects.filter(
                    org_summary__date__lte=self.config['startdate'],
                    org_summary__location_id=loc.location_id,
                    title=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                    total=1
                )

                if not group_summaries:
                    continue

                for group_summary in group_summaries:
                    if group_summary:
                        total_responses += group_summary.responded
                        total_possible += group_summary.total

                if total_possible:
                    response_rate = "%.1f%%" % (100.0 * total_responses / total_possible)
                else:
                    response_rate = "<span class='no_data'>None</span>"

                url = make_url(FacilityDetailsReport, self.config['domain'],
                               '?location_id=%s&filter_by_program=%s&'
                               'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                               (loc.location_id,
                                self.config['program'], self.config['datespan_type'],
                                self.config['datespan_first'], self.config['datespan_second']))

                latest = latest_status_or_none(loc.location_id, SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                               self.config['startdate'], self.config['enddate'])

                rows.append([
                    loc.site_code,
                    link_format(loc.name, url),
                    latest.name if latest else None,
                    latest.status_date.strftime('%b. %d, %Y') if latest else '',
                    response_rate
                ])
        return rows


class SupervisionReport(DetailsReport):
    slug = "supervision_report"
    name = 'Supervision'
    use_datatables = True

    @property
    def title(self):
        title = _('Supervision {0}'.format(self.title_month))
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
        if config['org_summary']:
            location = SQLLocation.objects.get(location_id=config['org_summary'][0].location_id)

            data_providers = [
                SupervisionSummaryData(config=config, css_class='row_chart_all'),
            ]

            if location.location_type.name.upper() == 'DISTRICT':
                data_providers.append(DistrictSupervisionData(config=config, css_class='row_chart_all'))
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
                data_providers.append(SupervisionData(config=config, css_class='row_chart_all'))
        return data_providers

    @property
    def report_context(self):
        ret = super(SupervisionReport, self).report_context
        ret['view_mode'] = 'supervision'
        return ret
