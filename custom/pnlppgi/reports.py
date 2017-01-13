# coding=utf-8
import datetime
from operator import add

from sqlagg import AliasColumn
from sqlagg.columns import SimpleColumn, CountColumn, SumColumn
from sqlagg.filters import EQ, IN, LTE

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import SqlTabularReport, DatabaseColumn, AggregateColumn, DictDataFormat, \
    DataFormatter
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.style.decorators import use_nvd3
from corehq.apps.userreports.util import get_table_name
from corehq.apps.users.models import CommCareUser
from custom.pnlppgi.filters import WeekFilter, LocationBaseDrilldownOptionFilter
from django.utils.translation import ugettext as _

from custom.pnlppgi.utils import location_filter, users_locations, show_location
from custom.pnlppgi.utils import update_config

EMPTY_CELL = {'sort_key': 0, 'html': '---'}


class SiteReportingRatesReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    slug = 'site_reporting_rates_report'
    name = u'Complétude et promptitude'

    report_template_path = 'pnlppgi/site_reporting.html'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        return super(SiteReportingRatesReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def fields(self):
        return [LocationBaseDrilldownOptionFilter, WeekFilter, YearFilter]

    @property
    def config(self):
        week = int(self.request.GET.get('week'))
        year = self.request.GET.get('year')
        date = "%s-W%s-1" % (year, week + 1)
        monday = datetime.datetime.strptime(date, "%Y-W%W-%w")

        params = {
            'domain': self.domain,
            'week': week,
            'year': year,
            'monday': monday.replace(hour=12)
        }
        location_filter(self.request, params=params)
        update_config(params)
        return params

    @property
    def group_by(self):
        return ['site_id']

    @property
    def filters(self):
        filters = [
            EQ('week', 'week'),
            EQ('year', 'year'),
            IN('owner_id', get_INFilter_bindparams('owner_id', self.config['users']))
        ]
        location_filter(self.request, filters=filters)
        return filters


    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], "site_reporting_rates_report")

    @property
    def columns(self):
        return [
            DatabaseColumn('location_id', SimpleColumn('site_id')),
            DatabaseColumn('Completude', CountColumn('doc_id', alias='completude')),
            DatabaseColumn('Promptitude', CountColumn(
                'doc_id',
                alias='promptitude',
                filters=self.filters + [LTE('opened_on', 'monday')]
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
        chart = MultiBarChart(None, Axis(''), Axis(''))
        chart.height = 400
        chart.marginBottom = 100
        chart.data = self.get_data_for_graph()
        return [chart]

    @property
    def rows(self):

        def cell_format(data):
            percent = 0
            if isinstance(data, dict):
                percent = 100
            return {
                'sort_key': percent,
                'html': "%.2f%%" % percent
            }

        users = CommCareUser.by_domain(self.domain)
        users_dict = {}
        for user in users:
            if user.location_id not in users_dict:
                users_dict.update({user.location_id: [user.get_id]})
            else:
                users_dict[user.location_id].append(user.get_id)

        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        data = formatter.format(self.data, keys=self.keys, group_by=self.group_by)
        selected_location = location_filter(self.request, location_filter_selected=True)
        if selected_location:
            locations = SQLLocation.objects.get(
                location_id=selected_location
            ).get_descendants(include_self=True).filter(location_type__code='centre-de-sante').order_by('name')
        else:
            locations = SQLLocation.objects.filter(
                domain=self.domain,
                location_type__code='centre-de-sante',
                is_archived=False
            ).order_by('name')
        user_locations = users_locations()
        for site in locations:
            loc_data = data.get(site.location_id, {})
            if site.location_id in user_locations:
                yield [
                    site.name,
                    cell_format(loc_data.get('completude', 0)),
                    cell_format(loc_data.get('promptitude', 0)),
                ]


class MalariaReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin):

    @property
    def group_by(self):
        return ['']

    @property
    def engine_id(self):
        return 'ucr'

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], "malaria")


class WeeklyMalaria(MalariaReport):
    slug = 'weekly_malaria'
    name = u'Données de la semaine'

    report_template_path = 'pnlppgi/weekly_malaria.html'

    @property
    def fields(self):
        return [LocationBaseDrilldownOptionFilter, WeekFilter, YearFilter]

    @property
    def config(self):
        week = self.request.GET.get('week')
        year = self.request.GET.get('year')
        params = {
            'domain': self.domain,
            'week': week,
            'year': year
        }
        location_filter(self.request, params=params)
        update_config(params)
        return params

    @property
    def filters(self):
        filters = [
            EQ('week', 'week'),
            EQ('year', 'year'),
            IN('owner_id', get_INFilter_bindparams('owner_id', self.config['users']))
        ]
        location_filter(self.request, filters=filters)
        return filters

    @property
    def group_by(self):
        return ['site_id']

    @property
    def columns(self):

        def percent(x):
            return {'sort_key': x, 'html': '%.2f%%' % (x * 100)}

        return [
            DatabaseColumn('site_id', SimpleColumn('site_id')),
            DatabaseColumn('cas_vus_5', SumColumn('cas_vus_5')),
            DatabaseColumn('cas_suspects_5', SumColumn('cas_suspects_5')),
            DatabaseColumn('tests_realises_5', SumColumn('tests_realises_5')),
            DatabaseColumn('cas_confirmes_5', SumColumn('cas_confirmes_5')),
            AggregateColumn('cas_vus_5_10', add, [
                SumColumn('cas_vus_5_10'), SumColumn('cas_vus_10')
            ]),
            AggregateColumn('cas_suspects_5_10', add, [
                SumColumn('cas_suspects_5_10'), SumColumn('cas_suspects_10')
            ]),
            AggregateColumn('tests_realises_5_10', add, [
                SumColumn('tests_realises_5_10'), SumColumn('tests_realises_10')
            ]),
            AggregateColumn('cas_confirmes_5_10', add, [
                SumColumn('cas_confirmes_5_10'), SumColumn('cas_confirmes_10')
            ]),
            DatabaseColumn('cas_vus_fe', SumColumn('cas_vus_fe')),
            DatabaseColumn('cas_suspects_fe', SumColumn('cas_suspects_fe')),
            DatabaseColumn('tests_realises_fe', SumColumn('tests_realises_fe')),
            DatabaseColumn('cas_confirmes_fe', SumColumn('cas_confirmes_fe')),
            DatabaseColumn('cas_vu_total', SumColumn('cas_vu_total')),
            DatabaseColumn('cas_suspect_total', SumColumn('cas_suspect_total')),
            DatabaseColumn('tests_realises_total', SumColumn('tests_realises_total')),
            DatabaseColumn('cas_confirmes_total', SumColumn('cas_confirmes_total')),
            AggregateColumn(
                'div_teasts_cas',
                lambda x, y: (x or 0) / float(y or 1),
                [AliasColumn('tests_realises_total'), AliasColumn('cas_suspect_total')],
                format_fn=percent
            )
        ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Region', sortable=False),
            DataTablesColumn('District', sortable=False),
            DataTablesColumn('Site', sortable=False),
            DataTablesColumnGroup(
                u'Patients Agés de - 5 Ans',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de Tests (TDR) réalisés', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'Patients Agés de 5 ans et +',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de Tests (TDR) réalisés', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'Femmes Enceintes MALADES',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de Tests (TDR) réalisés', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'TOTAL',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects. de paludisme (A)', sortable=False),
                DataTablesColumn('Nombre de Tests (TDR) réalisés (B)', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés (P)', sortable=False),
                DataTablesColumn('Taux de Réalisation des TDR (B) / (A)', sortable=False)
            )
        )

    @property
    def rows(self):
        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        data = formatter.format(self.data, keys=self.keys, group_by=self.group_by)
        selected_location = location_filter(self.request, location_filter_selected=True)
        selected_hierarchy = []
        if selected_location:
            selected_hierarchy = SQLLocation.objects.get(
                location_id=selected_location
            ).get_descendants(
                include_self=True
            ).filter(
                location_type__code='centre-de-sante'
            ).values_list(
                'location_id',
                flat=True
            )
        locations = SQLLocation.objects.filter(
            domain=self.domain,
            location_type__code='region',
            is_archived=False
        ).order_by('name')
        user_locations = users_locations()
        for reg in locations:
            for dis in reg.children.order_by('name'):
                for site in dis.children.order_by('name'):
                    row = data.get(site.location_id, {})
                    if show_location(site, user_locations, selected_hierarchy):
                        yield [
                            reg.name,
                            dis.name,
                            site.name,
                            row.get('cas_vus_5', EMPTY_CELL),
                            row.get('cas_suspects_5', EMPTY_CELL),
                            row.get('tests_realises_5', EMPTY_CELL),
                            row.get('cas_confirmes_5', EMPTY_CELL),
                            row.get('cas_vus_5_10', EMPTY_CELL),
                            row.get('cas_suspects_5_10', EMPTY_CELL),
                            row.get('tests_realises_5_10', EMPTY_CELL),
                            row.get('cas_confirmes_5_10', EMPTY_CELL),
                            row.get('cas_vus_fe', EMPTY_CELL),
                            row.get('cas_suspects_fe', EMPTY_CELL),
                            row.get('tests_realises_fe', EMPTY_CELL),
                            row.get('cas_confirmes_fe', EMPTY_CELL),
                            row.get('cas_vu_total', EMPTY_CELL),
                            row.get('cas_suspect_total', EMPTY_CELL),
                            row.get('tests_realises_total', EMPTY_CELL),
                            row.get('cas_confirmes_total', EMPTY_CELL),
                            row.get('div_teasts_cas', EMPTY_CELL)
                        ]


class CumulativeMalaria(MalariaReport):
    slug = 'cumulative_malaria'
    name = u'Données Cumulées de S01 à la Dernière Sem transmise'

    report_template_path = 'pnlppgi/cumulative_malaria.html'

    @property
    def fields(self):
        return [LocationBaseDrilldownOptionFilter, YearFilter]

    @property
    def config(self):
        year = self.request.GET.get('year')
        params = {
            'domain': self.domain,
            'year': year
        }
        location_filter(self.request, params=params)
        update_config(params)
        return params

    @property
    def filters(self):
        filters = [
            EQ('year', 'year'),
            IN('owner_id', get_INFilter_bindparams('owner_id', self.config['users']))
        ]
        location_filter(self.request, filters=filters)
        return filters

    @property
    def group_by(self):
        return ['site_id']

    @property
    def columns(self):
        def percent(num, x, y, z, w):
            denom = (x or 0) + (y or 0) + (z or 0) + (w or 0)
            if not denom:
                return {'sort_key': 'NA', 'html': 0}
            div = (num or 1) / float(denom)
            return {'sort_key': div, 'html': '%.2f%%' % (div * 100)}

        return [
            DatabaseColumn('site_id', SimpleColumn('site_id')),
            DatabaseColumn('cas_vus_5', SumColumn('cas_vus_5')),
            DatabaseColumn('cas_suspects_5', SumColumn('cas_suspects_5')),
            DatabaseColumn('cas_confirmes_5', SumColumn('cas_confirmes_5')),
            DatabaseColumn('cas_vus_5_10', SumColumn('cas_vus_5_10')),
            DatabaseColumn('cas_suspects_5_10', SumColumn('cas_suspects_5_10')),
            DatabaseColumn('cas_confirmes_5_10', SumColumn('cas_confirmes_5_10')),
            DatabaseColumn('cas_vus_10', SumColumn('cas_vus_10')),
            DatabaseColumn('cas_suspects_10', SumColumn('cas_suspects_10')),
            DatabaseColumn('cas_confirmes_10', SumColumn('cas_confirmes_10')),

            DatabaseColumn('cas_vus_fe', SumColumn('cas_vus_fe')),
            DatabaseColumn('cas_suspects_fe', SumColumn('cas_suspects_fe')),
            DatabaseColumn('cas_confirmes_fe', SumColumn('cas_confirmes_fe')),
            AggregateColumn('total_cas', lambda x, y, z, w: (x or 0) + (y or 0) + (z or 0) + (w or 0), [
                AliasColumn('cas_confirmes_5'),
                AliasColumn('cas_confirmes_5_10'),
                AliasColumn('cas_confirmes_10'),
                AliasColumn('cas_confirmes_fe'),
            ], slug='total_cas'),
            AggregateColumn('per_cas_5', percent, [
                AliasColumn('cas_confirmes_5'),
                AliasColumn('cas_confirmes_5'),
                AliasColumn('cas_confirmes_5_10'),
                AliasColumn('cas_confirmes_10'),
                AliasColumn('cas_confirmes_fe')
            ], format_fn=lambda x: x),
            AggregateColumn('per_cas_5_10', percent, [
                AliasColumn('cas_confirmes_5_10'),
                AliasColumn('cas_confirmes_5'),
                AliasColumn('cas_confirmes_5_10'),
                AliasColumn('cas_confirmes_10'),
                AliasColumn('cas_confirmes_fe')
            ], format_fn=lambda x: x),
            AggregateColumn('per_cas_10', percent, [
                AliasColumn('cas_confirmes_10'),
                AliasColumn('cas_confirmes_5'),
                AliasColumn('cas_confirmes_5_10'),
                AliasColumn('cas_confirmes_10'),
                AliasColumn('cas_confirmes_fe')
            ], format_fn=lambda x: x),
            AggregateColumn('per_cas_fa', percent, [
                AliasColumn('cas_confirmes_fe'),
                AliasColumn('cas_confirmes_5'),
                AliasColumn('cas_confirmes_5_10'),
                AliasColumn('cas_confirmes_10'),
                AliasColumn('cas_confirmes_fe')
            ], format_fn=lambda x: x)
        ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Region', sortable=False),
            DataTablesColumn('District', sortable=False),
            DataTablesColumn('Site', sortable=False),
            DataTablesColumnGroup(
                u'Patients Agés de - 5 Ans',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'Patients Agés de 5 - 10 ans',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'Patients Agés de 10 ans et +',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'Femmes Enceintes MALADES',
                DataTablesColumn('Nombre Total de cas vus (toutes affections confondues)', sortable=False),
                DataTablesColumn('Nombre de cas Suspects de paludisme', sortable=False),
                DataTablesColumn('Nombre de cas de paludisme confirmés', sortable=False)
            ),
            DataTablesColumnGroup(
                u'Rapport par Catégorie',
                DataTablesColumn('Total Cas', sortable=False),
                DataTablesColumn('% des Moins de 5 ans', sortable=False),
                DataTablesColumn('% des 5 - 10 ans', sortable=False),
                DataTablesColumn('% des Plus de 10 ans', sortable=False),
                DataTablesColumn('% des Femmes Enceinte', sortable=False)
            ),
            DataTablesColumn('Zones', sortable=False)
        )

    @property
    def rows(self):
        formatter = DataFormatter(DictDataFormat(self.columns, no_value=self.no_value))
        data = formatter.format(self.data, keys=self.keys, group_by=self.group_by)

        selected_location = location_filter(self.request, location_filter_selected=True)
        selected_hierarchy = []
        if selected_location:
            selected_hierarchy = SQLLocation.objects.get(
                location_id=selected_location
            ).get_descendants(
                include_self=True
            ).filter(
                location_type__code='centre-de-sante'
            ).values_list(
                'location_id',
                flat=True
            )

        locations = SQLLocation.objects.filter(
            domain=self.domain,
            location_type__code='zone',
            is_archived=False
        ).order_by('name')
        user_locations = users_locations()
        for zone in locations:
            for reg in zone.children.order_by('name'):
                for dis in reg.children.order_by('name'):
                    for site in dis.children.order_by('name'):
                        row = data.get(site.location_id, {})
                        if show_location(site, user_locations, selected_hierarchy):
                            yield [
                                reg.name,
                                dis.name,
                                site.name,
                                row.get('cas_vus_5', EMPTY_CELL),
                                row.get('cas_suspects_5', EMPTY_CELL),
                                row.get('cas_confirmes_5', EMPTY_CELL),
                                row.get('cas_vus_5_10', EMPTY_CELL),
                                row.get('cas_suspects_5_10', EMPTY_CELL),
                                row.get('cas_confirmes_5_10', EMPTY_CELL),
                                row.get('cas_vus_10', EMPTY_CELL),
                                row.get('cas_suspects_10', EMPTY_CELL),
                                row.get('cas_confirmes_10', EMPTY_CELL),
                                row.get('cas_vus_fe', EMPTY_CELL),
                                row.get('cas_suspects_fe', EMPTY_CELL),
                                row.get('cas_confirmes_fe', EMPTY_CELL),
                                row.get('total_cas', EMPTY_CELL),
                                row.get('per_cas_5', EMPTY_CELL),
                                row.get('per_cas_5_10', EMPTY_CELL),
                                row.get('per_cas_10', EMPTY_CELL),
                                row.get('per_cas_fa', EMPTY_CELL),
                                zone.name
                            ]

CUSTOM_REPORTS = (
    ['Custom Reports', (
        SiteReportingRatesReport,
        WeeklyMalaria,
        CumulativeMalaria
    )],
)
