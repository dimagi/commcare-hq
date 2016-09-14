import datetime
from sqlagg.columns import SimpleColumn, CountColumn
from sqlagg.filters import LT, EQ

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.userreports.util import get_table_name
from corehq.apps.users.models import CommCareUser
from custom.pnlppgi.filters import WeekFilter
from django.utils.translation import ugettext as _


class SiteReportingRatesReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    slug = 'site_reporting_rates_report'
    name = 'Site Reporting Rates Report'

    @property
    def fields(self):
        return [WeekFilter, YearFilter]

    @property
    def config(self):
        week = self.request.GET.get('week')
        year = self.request.GET.get('year')
        date = "%s-W%s-1" % (year, week)
        monday = datetime.datetime.strptime(date, "%Y-W%W-%w")
        return {
            'domain': self.domain,
            'week': week,
            'year': year,
            'monday': monday.replace(hour=16)
        }

    @property
    def group_by(self):
        return ['location_id', 'location_name']

    @property
    def filters(self):
        return [
            EQ('week', 'week'),
            EQ('year', 'year'),
        ]

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], "site_reporting_rates_report")

    @property
    def columns(self):
        return [
            DatabaseColumn('location_id', SimpleColumn('location_id')),
            DatabaseColumn('location_name', SimpleColumn('location_name')),
            DatabaseColumn('Completude', CountColumn('doc_id', alias='completude')),
            DatabaseColumn('Promptitude', CountColumn(
                'doc_id',
                alias='promptitude',
                filters=self.filters + [LT('opened_on', 'monday')]
            )),
        ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Site'),
            DataTablesColumn('Completude'),
            DataTablesColumn('Promptitude')
        )

    def get_data_for_graph(self):
        com = []
        prom = []

        for row in self.rows:
            com.append({"x": row[0], "y": row[1]['sort_key']})
            prom.append({"x": row[0], "y": row[2]['sort_key']})

        return [
            {"key": "Completude", 'values': com},
            {"key": "Promptitude", 'values': prom},
        ]

    @property
    def charts(self):

        chart = MultiBarChart(None, Axis(_('Sites')), Axis(''))
        chart.data = self.get_data_for_graph()
        return [chart]

    @property
    def rows(self):

        def cell_format(data, all_users):
            percent = 0
            if isinstance(data, dict):
                percent = data['sort_key'] * 100 / float(len(set(all_users)) or 1)
            return {
                'sort_key': percent,
                'html': "%.2f%%" % percent
            }

        data = super(SiteReportingRatesReport, self).rows
        users = CommCareUser.by_domain(self.domain)
        users_dict = {}
        for user in users:
            if user.location_id not in users_dict:
                users_dict.update({user.location_id: [user.get_id]})
            else:
                users_dict[user.location_id].append(user.get_id)

        for row in data:
            all_users = users_dict.get(row[0], [])
            yield [
                row[1],
                cell_format(row[2], all_users),
                cell_format(row[3], all_users)
            ]
