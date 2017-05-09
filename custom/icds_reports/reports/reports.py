from datetime import datetime
from django.urls import reverse
from sqlagg import AliasColumn
from sqlagg.columns import SimpleColumn, SumColumn
from sqlagg.filters import EQ, IN
from sqlagg.sorting import OrderBy

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn, SqlData
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.maps import GenericMapReport
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.style.decorators import use_maps, use_jquery_ui, use_select2, use_datatables, \
    use_daterangepicker
from custom.icds_reports.asr_sqldata import ASRIdentification, ASROperationalization, ASRPopulation, Annual, \
    DisabledChildren, Infrastructure, Equipment
from custom.icds_reports.filters import ICDSMonthFilter, IcdsLocationFilter, ICDSYearFilter, \
    MinorityFilter, DisabledFilter, StateFilter, GenderFilter, MultiCasteFilter, \
    MultiAgeTrancheFilter, YesNoResidentFilter
from custom.icds_reports.mpr_sqldata import MPRIdentification, MPRSectors, MPRPopulation, MPRBirthsAndDeaths, \
    MPRAWCDetails, MPRSupplementaryNutrition, MPRUsingSalt, MPRProgrammeCoverage, MPRPreschoolEducation, \
    MPRGrowthMonitoring, MPRImmunizationCoverage, MPRVhnd, MPRReferralServices, MPRMonitoring
from custom.icds_reports.mpr_sqldata import MPROperationalization
from custom.icds_reports.reports import IcdsBaseReport
from dimagi.utils.decorators.memoized import memoized

from custom.utils.utils import clean_IN_filter_value


@location_safe
class MPRReport(IcdsBaseReport):

    title = '1. Identification and Basic Information'
    slug = 'mpr_report'
    name = 'Block MPR'

    fields = [AsyncLocationFilter, ICDSMonthFilter, YearFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            MPRIdentification(config=config),
            MPROperationalization(config=config),
            MPRSectors(config=config),
            MPRPopulation(config=config),
            MPRBirthsAndDeaths(config=config),
            MPRAWCDetails(config=config),
            MPRSupplementaryNutrition(config=config),
            MPRUsingSalt(config=config),
            MPRProgrammeCoverage(config=config),
            MPRPreschoolEducation(config=config),
            MPRGrowthMonitoring(config=config),
            MPRImmunizationCoverage(config=config),
            MPRVhnd(config=config),
            MPRReferralServices(config=config),
            MPRMonitoring(config=config)
        ]


@location_safe
class ASRReport(IcdsBaseReport):

    title = '1. Identification and Basic Information'
    slug = 'asr_report'
    name = 'Block ASR'

    fields = [IcdsLocationFilter]

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ASRIdentification(config=config),
            ASROperationalization(config=config),
            ASRPopulation(config=config),
            Annual(config=config),
            DisabledChildren(config=config),
            Infrastructure(config=config),
            Equipment(config=config)
        ]


@location_safe
class TableauReport(CustomProjectReport):

    slug = 'tableau_dashboard'
    name = 'ICDS-CAS Dashboard'

    @classmethod
    def get_url(cls, domain=None, **kwargs):
        domain_to_workbook_mapping = {
            'icds-test': 'DashboardTest',
            'icds-cas': 'DashboardR5',
        }
        workbook_name = domain_to_workbook_mapping.get(domain, domain_to_workbook_mapping['icds-cas'])
        worksheet_name = 'Dashboard'
        return reverse('icds_tableau', args=[domain, workbook_name, worksheet_name])


@location_safe
class ChildHealthMonthReport(SqlData):
    table_name = "agg_child_health_monthly"

    @property
    def filter_values(self):
        filter_values = clean_IN_filter_value(super(ChildHealthMonthReport, self).filter_values, 'age_tranche')
        filter_values = clean_IN_filter_value(filter_values, 'caste')
        return filter_values

    @property
    def filters(self):
        filters = [
            EQ('month', 'month'),
            EQ('aggregation_level', 'aggregation_lvl')
        ]
        if self.config['state'] != 'All':
            filters.append(EQ('state_name', 'state'))
        if self.config['gender'] != 'All':
            filters.append(EQ('gender', 'gender'))
        if self.config['age_tranche'] and 'All' not in self.config['age_tranche']:
            filters.append(IN('age_tranche', get_INFilter_bindparams('age_tranche', self.config['age_tranche'])))
        if self.config['caste'] and 'All' not in self.config['caste']:
            filters.append(IN('caste', get_INFilter_bindparams('caste', self.config['caste'])))
        if self.config['minority'] != 'All':
            filters.append(EQ('minority', 'minority'))
        if self.config['disabled'] != 'All':
            filters.append(EQ('disabled', 'disabled'))
        if self.config['resident'] != 'All':
            filters.append(EQ('resident', 'resident'))
        return filters

    @property
    def group_by(self):
        group_by = ['state_name']
        if self.config['aggregation_lvl'] == 2:
            group_by.append('district_name')
        return group_by

    @property
    def order_by(self):
        order_by = [OrderBy('state_name')]
        if self.config['aggregation_lvl'] == 2:
            order_by.append(OrderBy('district_name'))
        return order_by

    @property
    def columns(self):
        def percent_fn(x, y):
            return "%.2f%%" % (float(x or 0) / float(y or 1) * 100)

        def percent_all_fn(a, b, c, d):
            diff = d - a - b - c
            return percent_fn(diff, d)

        def status_fn(a, b, c, d):
            a = float(a or 0)
            b = float(b or 0)
            c = float(c or 0)
            d = float(d or 1)
            no_nutrition = (d - a - b - c) / d
            severely = c / d
            moderately = b / d

            if no_nutrition >= 0.75:
                return 'unknown'
            elif severely > 0.1 or moderately > 0.3:
                return 'severe'
            elif severely > 0.05 or 0.15:
                return 'moderate'
            else:
                return 'normal'

        columns = [
            DatabaseColumn("State", SimpleColumn('state_name'))
        ]

        if self.config['aggregation_lvl'] == 2:
            columns.append(DatabaseColumn("District", SimpleColumn('district_name')))

        return columns + [
            DatabaseColumn(
                "# Valid in month",
                SumColumn(
                    'valid_in_month',
                    alias='sum_valid_in_month'
                )
            ),
            DatabaseColumn(
                "# Nutrition status normal",
                SumColumn(
                    'nutrition_status_normal',
                    alias='sum_nutrition_status_normal'
                )
            ),
            DatabaseColumn(
                "# Nutrition status moderately underweight",
                SumColumn(
                    'nutrition_status_moderately_underweight',
                    alias='sum_nutrition_status_moderately_underweight'
                )
            ),
            DatabaseColumn(
                "# Nutrition status severely underweight",
                SumColumn(
                    'nutrition_status_severely_underweight',
                    alias='sum_nutrition_status_severely_underweight'
                )
            ),
            AggregateColumn(
                "% Normal Weight",
                percent_fn,
                [
                    AliasColumn('sum_nutrition_status_normal'),
                    AliasColumn('sum_valid_in_month')
                ]

            ),
            AggregateColumn(
                "% Moderately Underweight",
                percent_fn,
                [
                    AliasColumn('sum_nutrition_status_moderately_underweight'),
                    AliasColumn('sum_valid_in_month')
                ]

            ),
            AggregateColumn(
                "% Severely Underweight",
                percent_fn,
                [
                    AliasColumn('sum_nutrition_status_severely_underweight'),
                    AliasColumn('sum_valid_in_month')
                ]

            ),
            AggregateColumn(
                "% Normal Weight",
                percent_all_fn,
                [
                    AliasColumn('sum_nutrition_status_normal'),
                    AliasColumn('sum_nutrition_status_moderately_underweight'),
                    AliasColumn('sum_nutrition_status_severely_underweight'),
                    AliasColumn('sum_valid_in_month')
                ]

            ),
            AggregateColumn(
                "Nutrition Status of Location",
                status_fn,
                [
                    AliasColumn('sum_nutrition_status_normal'),
                    AliasColumn('sum_nutrition_status_moderately_underweight'),
                    AliasColumn('sum_nutrition_status_severely_underweight'),
                    AliasColumn('sum_valid_in_month')
                ]

            )
        ]

    @property
    def engine_id(self):
        return 'ucr'


class ChildHealthMothlyMapReport(CustomProjectReport, GenericMapReport):

    name = 'Child Health Monthly (Map)'
    title = 'Child Health Monthly (Map)'
    slug = 'map_child_health'
    flush_layout = True
    report_partial_path = "icds_reports/partials/icds_map.html"

    fields = [
        StateFilter,
        ICDSMonthFilter,
        ICDSYearFilter,
        GenderFilter,
        MultiAgeTrancheFilter,
        MultiCasteFilter,
        MinorityFilter,
        DisabledFilter,
        YesNoResidentFilter
    ]

    data_source = {
        'adapter': 'report',
        'geojson_adapter': 'geojson',
        'geo_column': 'geo',
        'report': 'custom.icds_reports.reports.reports.ChildHealthMonthReport',
        'path': 'custom/icds_reports/resources/%s.geojson.json',
    }

    @property
    def config(self):
        month = int(self.request.GET.get('month', 0))
        year = int(self.request.GET.get('year', 0))
        date = None
        if month and year:
            date = datetime(year, month, 1).date()
        aggregation_lvl = 1
        state = self.request.GET.get('state', '')
        if state and state != 'All':
            aggregation_lvl = 2

        caste = self.request.GET.getlist('caste', [])
        age_tranche = self.request.GET.getlist('age_tranche', [])
        minority = self.request.GET.get('minority', '')
        disabled = self.request.GET.get('disabled', '')
        resident = self.request.GET.get('resident', '')
        gender = self.request.GET.get('gender', '')

        return {
            'domain': 'icds_test',
            'month': date,
            'state': state,
            'aggregation_lvl': aggregation_lvl,
            'caste': caste,
            'age_tranche': age_tranche,
            'minority': minority,
            'disabled': disabled,
            'resident': resident,
            'gender': gender
        }

    @use_jquery_ui
    @use_select2
    @use_datatables
    @use_daterangepicker
    @use_maps
    def decorator_dispatcher(self, request, *args, **kwargs):
        pass

    def _get_data(self):
        locations = 'states'
        row_location_loc = 'state_name'
        if self.config['aggregation_lvl'] == 2:
            locations = 'districts'
            row_location_loc = 'district_name'

        def_value = {'sort_key': 0, 'html': '0%'}
        def_value_int = {'sort_key': 0, 'html': 0}
        report_adapter = self.data_source['adapter']
        geo_col = self.data_source.get('geo_column', 'geo')
        geo_data_adapter = self.data_source['geojson_adapter']

        try:
            report_loader = getattr(self, '_get_data_%s' % report_adapter)
            geo_data_loader = getattr(self, '_get_data_%s' % geo_data_adapter)
        except AttributeError:
            raise RuntimeError('unknown adapter [%s] or [%s]' % (report_adapter, geo_data_adapter))
        report_data = report_loader(self.data_source, self.config)
        geo_data = geo_data_loader(dict(path=self.data_source['path'] % locations), dict())
        map_data = []
        location_name_col = 'NAME_1' if locations == 'states' else 'NAME_2'
        for geo in geo_data:
            if self.config['state'] != 'All' and geo['NAME_1'] != self.config['state']:
                continue
            columns = {
                row_location_loc: geo[location_name_col],
                'sum_nutrition_status_moderately_underweight': def_value_int,
                'sum_nutrition_status_normal': def_value_int,
                'sum_nutrition_status_severely_underweight': def_value_int,
                'sum_valid_in_month': def_value_int,
                'moderately-underweight': def_value,
                'normal-weight': def_value,
                'severely-underweight': def_value,
                'nutrition-status-of-location': {'sort_key': 'unknown', 'html': 'unknown'},
            }
            for row in report_data:
                if row[row_location_loc] == geo[location_name_col]:
                    columns = row
                    continue
            columns.update(dict(geo=geo['geo']))
            map_data.append(columns)
        return self._to_geojson(map_data, geo_col)

    @property
    def display_config(self):
        name_column = 'district_name' if self.config['aggregation_lvl'] == 2 else 'state_name'
        conf = {
            'name_column': name_column,
            'detail_columns': ['nutrition-status-of-location'],
            'table_columns': [
                'sum_nutrition_status_moderately_underweight',
                'sum_nutrition_status_normal',
                'sum_nutrition_status_severely_underweight',
                'sum_valid_in_month',
                'moderately-underweight',
                'normal-weight',
                'severely-underweight',
                'nutrition-status-of-location'
            ],
            'column_titles': {
                'state_name': 'State',
                'district_name': 'District',
                'sum_nutrition_status_moderately_underweight': 'Nutrition status moderately underweight',
                'sum_nutrition_status_normal': 'Nutrition status normal',
                'sum_nutrition_status_severely_underweight': 'Nutrition status severely underweight',
                'sum_valid_in_month': 'Valid in month',
                'moderately-underweight': 'Moderately underweight',
                'normal-weight': 'Normal weight',
                'severely-underweight': 'Severely underweight',
                'nutrition-status-of-location': 'Nutrition status of location',
            },
            'enum_captions': {},
            'numeric_format': {},
            'display': {
                'table': True
            },
            'metrics': [
                {
                    'default': True,
                    'color': {
                        'column': 'nutrition-status-of-location',
                        'title': 'nutrition-status-of-location',
                        'categories': {
                            'unknown': 'rgba(192, 192, 192, 0.8)',
                            'severe': 'rgba(255, 0, 0, 0.8)',
                            'moderate': 'rgba(255, 128, 0, 0.8)',
                            'normal': 'rgba(0, 153, 0, 0.8)',
                        }
                    }
                }
            ],
            'detail_template': """<div>
                <h3><%= name %></h3>
                <hr />
                <p>Number of children: <%= props['sum_valid_in_month']%></p>
                <p>% Normal Weight: <strong><%= props['normal-weight']%></strong></p>
                <p>% Moderately Underweight: <strong><%= props['moderately-underweight']%></strong></p>
                <p>% Severely Underweight: <strong><%= props['severely-underweight']%></strong></p>
                </div>
            """
        }
        return conf
