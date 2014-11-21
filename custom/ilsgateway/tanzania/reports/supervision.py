from datetime import datetime
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, OrganizationSummary
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.utils import make_url, format_percent, link_format, latest_status_or_none
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from django.utils import html


class SupervisionSummaryData(ILSData):
    title = 'Supervision Summary'
    slug = 'supervision_summary'

    @property
    def rows(self):
        super_data = []
        if self.config['org_summary']:
            super_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                                  org_summary=self.config['org_summary'])
        return super_data


class SupervisionData(ILSData):
    title = 'Supervision'
    slug = 'supervision_table'
    show_chart = False
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('% Supervision Received')),
            DataTablesColumn(_('% Supervision Not Received')),
            DataTablesColumn(_('% Supervision Not Responding')),
            DataTablesColumn(_('Historical Response Rate')),
        ])

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                facilities = SQLLocation.objects.filter(parent=loc).count()
                org_summary = OrganizationSummary.objects.filter(date__range=(self.config['startdate'],
                                                                 self.config['enddate']),
                                                                 supply_point=loc.location_id)[0]

                soh_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                                    org_summary=org_summary)

                total_responses = 0
                total_possible = 0
                for g in GroupSummary.objects.filter(org_summary__date__lte=datetime(int(self.config['year']),
                                                                                     int(self.config['month']), 1),
                                                     org_summary__supply_point=loc.location_id,
                                                     title=SupplyPointStatusTypes.SUPERVISION_FACILITY):
                    if g:
                        total_responses += g.responded
                        total_possible += g.total

                if total_possible:
                    response_rate = "%.1f%%" % (100.0 * total_responses / total_possible)
                else:
                    response_rate = "<span class='no_data'>None</span>"

                url = make_url(SupervisionReport, self.config['domain'],
                               '?location_id=%s&month=%s&year=%s',
                               (loc.location_id, self.config['month'], self.config['year']))

                rows.append([
                    link_format(loc.name, url),
                    format_percent(float(soh_data.received) * 100 / float(facilities)),
                    format_percent(float(soh_data.not_received) * 100 / float(facilities)),
                    format_percent(float(soh_data.not_responding) * 100 / float(facilities)),
                    response_rate
                ])
        return rows


class DistrictSupervisionData(ILSData):
    title = 'Supervision'
    slug = 'district_supervision_table'
    show_chart = False
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('MSD Code')),
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Supervision This Quarter')),
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Historical Response Rate')),
        ])

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                total_responses = 0
                total_possible = 0
                for g in GroupSummary.objects.filter(org_summary__date__lte=datetime(int(self.config['year']),
                                                                                     int(self.config['month']), 1),
                                                     org_summary__supply_point=loc.location_id,
                                                     title=SupplyPointStatusTypes.SUPERVISION_FACILITY):
                    if g:
                        total_responses += g.responded
                        total_possible += g.total

                if total_possible:
                    response_rate = "%.1f%%" % (100.0 * total_responses / total_possible)
                else:
                    response_rate = "<span class='no_data'>None</span>"

                try:
                    url = html.escape(FacilityDetailsReport.get_url(
                        domain=self.config['domain']) +
                        '?location_id=%s' % loc.location_id)
                except KeyError:
                    url = None

                latest = latest_status_or_none(loc.location_id, SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                               int(self.config['month']), int(self.config['year']))

                rows.append([
                    loc.site_code,
                    link_format(loc.name, url),
                    latest.name if latest else None,
                    latest.status_date if latest else None,
                    response_rate
                ])
        return rows


class SupervisionReport(DetailsReport):
    slug = "supervision_report"
    name = 'Supervision'
    title = 'Supervision'
    use_datatables = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        data_providers = []
        if config['org_summary']:
            location = SQLLocation.objects.get(location_id=config['org_summary'].supply_point)

            data_providers = [
                SupervisionSummaryData(config=config, css_class='row_chart_all'),
            ]

            if location.location_type.upper() == 'DISTRICT':
                data_providers.append(DistrictSupervisionData(config=config, css_class='row_chart_all'))
            else:
                data_providers.append(SupervisionData(config=config, css_class='row_chart_all'))
        return data_providers

    @property
    def report_context(self):
        ret = super(SupervisionReport, self).report_context
        ret['view_mode'] = 'supervision'
        return ret
