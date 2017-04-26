from datetime import datetime
from django.urls import reverse
from sqlagg import AliasColumn
from sqlagg.columns import SimpleColumn, SumColumn
from sqlagg.filters import EQ, IN
from sqlagg.sorting import OrderBy

from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn, SqlTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.standard.maps import GenericMapReport
from corehq.apps.reports.util import get_INFilter_bindparams
from corehq.apps.style.decorators import maps_prefer_canvas, use_maps
from custom.icds_reports.asr_sqldata import ASRIdentification, ASROperationalization, ASRPopulation, Annual, \
    DisabledChildren, Infrastructure, Equipment
from custom.icds_reports.filters import ICDSMonthFilter, IcdsLocationFilter, ICDSYearFilter, CasteFilter, \
    MinorityFilter, DisabledFilter, ResidentFilter, MaternalStatusFilter, ChildAgeFilter, THRBeneficiaryType, \
    TableauLocationFilter, StateFilter, GenderFilter, MultiCasteFilter, MultiAgeTrancheFilter, YesNoResidentFilter
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
class ChildHealthMonthReport(SqlTabularReport, CustomProjectReport, ProjectReportParametersMixin):
    table_name = "agg_child_health_monthly"
    name = 'Child Health Monthly'
    title = 'Child Health Monthly'
    slug = 'child_health'

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
            'aggregation_lvl': aggregation_lvl,
            'caste': caste,
            'age_tranche': age_tranche,
            'minority': minority,
            'disabled': disabled,
            'resident': resident,
            'gender': gender
        }

    @property
    def filter_values(self):
        filter_values = clean_IN_filter_value(super(ChildHealthMonthReport, self).filter_values, 'age_tranche')
        filter_values = clean_IN_filter_value(filter_values, 'caste')
        print filter_values
        return filter_values

    @property
    def filters(self):
        filters = [
            EQ('month', 'month'),
            EQ('aggregation_level', 'aggregation_lvl')
        ]
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
        print filters
        return filters

    @property
    def group_by(self):
        group_by = ['month', 'state_name']
        if self.config['aggregation_lvl'] == 2:
            group_by.append('district_name')
        return group_by

    @property
    def order_by(self):
        order_by = [OrderBy('month'), OrderBy('state_name')]
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
            DatabaseColumn("Month", SimpleColumn('month')),
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
    def rows(self):
        if self.config['month']:
            return super(ChildHealthMonthReport, self).rows
        return []

    @property
    def engine_id(self):
        return 'ucr'


@location_safe
class ChildHealthMothlyMapReport(CustomProjectReport, GenericMapReport):

    name = 'Child Health Monthly (Map)'
    title = 'Child Health Monthly (Map)'
    slug = 'map_child_health'

    fields = [
        ICDSMonthFilter,
        ICDSYearFilter,
        IcdsLocationFilter
    ]

    data_source = {
        'adapter': 'legacyreport',
        'geo_column': 'gps',
        'report': 'custom.icds_reports.reports.ChildHealthMonthReport',
        'report_params': {'map': True}
    }

    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Name', sortable=False),
            DataTablesColumn('Code', sortable=False)
        )

    @maps_prefer_canvas
    @use_maps
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(ChildHealthMothlyMapReport, self).decorator_dispatcher(request, *args, **kwargs)

    def _get_data(self):
        adapter = self.data_source['adapter']
        geo_col = self.data_source.get('geo_column', 'geo')

        try:
            loader = getattr(self, '_get_data_%s' % adapter)
        except AttributeError:
            raise RuntimeError('unknown adapter [%s]' % adapter)
        data = loader(self.data_source, dict(self.request.GET.iteritems()))

        return self._to_geojson(data, geo_col)

    @property
    def display_config(self):
        return {}
