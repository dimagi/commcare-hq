from StringIO import StringIO
from collections import OrderedDict
import datetime

import pytz
from dateutil.rrule import rrule, MONTHLY
from django.http.response import Http404
from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn
from sqlagg.filters import EQ, OR, BETWEEN, RawFilter, EQFilter, IN, NOT
from sqlagg.sorting import OrderBy

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn, Column
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.icds_reports.queries import get_test_state_locations_id
from custom.icds_reports.utils import ICDSMixin
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response

from custom.utils.utils import clean_IN_filter_value
from dimagi.utils.decorators.memoized import memoized

india_timezone = pytz.timezone('Asia/Kolkata')


class BaseIdentification(object):

    title = 'a. Identification'
    slug = 'identification'
    has_sections = False
    subtitle = []
    posttitle = None

    def __init__(self, config):
        self.config = config

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Name', sortable=False),
            DataTablesColumn('Code', sortable=False)
        )


class BaseOperationalization(ICDSMixin):

    title = 'c. Status of operationalization of AWCs'
    slug = 'operationalization'

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('', sortable=False),
            DataTablesColumn('Sanctioned', sortable=False),
            DataTablesColumn('Functioning', sortable=False),
            DataTablesColumn('Reporting', sortable=False)
        )

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            return [
                [
                    'No. of AWCs',
                    self.awc_number,
                    0,
                    data['owner_id']
                ],
                [
                    'No. of Mini AWCs',
                    0,
                    0,
                    0
                ]
            ]


class BasePopulation(ICDSMixin):

    slug = 'population'

    def __init__(self, config):
        super(BasePopulation, self).__init__(config)
        self.config.update(dict(
            location_id=config['location_id']
        ))

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        if self.config['location_id']:
            data = self.custom_data(selected_location=self.selected_location, domain=self.config['domain'])
            return [
                [
                    "Total Population of the project:",
                    data['open_count']
                ]
            ]


def percent_num(x, y):
    return (x or 0) * 100 / float(y or 1)


def percent(x, y):
    return "%.2f %%" % (percent_num(x, y))


class ExportableMixin(object):
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level=1, show_test=False):
        self.config = config
        self.loc_level = loc_level
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.config['excluded_states'] = self.excluded_states
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = []
        infilter_params = get_INFilter_bindparams('excluded_states', self.excluded_states)

        if not self.show_test:
            filters.append(NOT(IN('state_id', infilter_params)))

        for key, value in self.config.iteritems():
            if key == 'domain' or key in infilter_params:
                continue
            filters.append(EQ(key, key))
        return filters

    @property
    def group_by(self):
        group_by_columns = self.get_columns_by_loc_level
        group_by = ['aggregation_level']
        for column in group_by_columns:
            group_by.append(column.slug)
        return group_by

    @property
    def order_by(self):
        order_by_columns = self.get_columns_by_loc_level
        order_by = []
        for column in order_by_columns:
            order_by.append(OrderBy(column.slug))
        return order_by

    def to_export(self, format, location):
        export_file = StringIO()
        excel_rows = []
        headers = []
        for column in self.columns:
            if isinstance(column, Column):
                headers.append(column.header)
            else:
                headers.append(column['header'])
        excel_rows.append(headers)
        for row in self.get_data():
            row_data = []
            for c in self.columns:
                if isinstance(c, Column):
                    cell = row[c.slug]
                else:
                    cell = row[c['slug']]
                if not isinstance(cell, dict):
                    row_data.append(cell)
                else:
                    row_data.append(cell['sort_key'] if cell and 'sort_key' in cell else cell)
            excel_rows.append(row_data)

        utc_now = datetime.datetime.now(pytz.utc)
        india_now = utc_now.astimezone(india_timezone)

        filters = [['Generated at', india_now.strftime("%H:%M:%S %d %B %Y")]]
        if location:
            locs = SQLLocation.objects.get(location_id=location).get_ancestors(include_self=True)
            for loc in locs:
                filters.append([loc.location_type.name.title(), loc.name])
        if 'aggregation_level' in self.config:
            levels = ['State', 'District', 'Block', 'Supervisor', 'AWC']
            filters.append(['Grouped By', levels[self.config['aggregation_level'] - 1]])
        if 'month' in self.config:
            date = self.config['month']
            filters.append(['Month', date.strftime("%B")])
            filters.append(['Year', date.year])
        excel_data = [
            [
                self.title,
                excel_rows
            ],
            [
                'Filters',
                filters
            ]
        ]

        export_from_tables(excel_data, export_file, format)
        return export_response(export_file, format, self.title)


class NationalAggregationDataSource(SqlData):

    def __init__(self, config, data_source=None):
        super(NationalAggregationDataSource, self).__init__(config)
        self.data_source = data_source

    @property
    def table_name(self):
        return self.data_source.table_name

    @property
    def engine_id(self):
        return self.data_source.engine_id

    @property
    def filters(self):
        return [
            RawFilter('aggregation_level = 1'),
            EQFilter('month', 'previous_month')
        ]

    @property
    def group_by(self):
        return []

    @property
    def columns(self):
        # drop month column because we always fetch data here for previous month
        return self.data_source.columns[1:]


class ProgressReportSqlData(SqlData):

    @property
    def filters(self):
        filters = [
            EQ('aggregation_level', 'aggregation_level')
        ]
        keys = ['state_id', 'district_id', 'block_id', 'supervisor_id']
        for key in keys:
            if key in self.config:
                filters.append(
                    EQ(key, key)
                )
        return filters


class AggChildHealthMonthlyDataSource(ProgressReportSqlData):
    table_name = 'agg_child_health_monthly'
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level='state', show_test=False):
        super(AggChildHealthMonthlyDataSource, self).__init__(config)
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.loc_key = '%s_id' % loc_level
        self.config.update({
            'age_0': '0',
            'age_6': '6',
            'age_12': '12',
            'age_24': '24',
            'age_36': '36',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72',
            'excluded_states': self.excluded_states
        })
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test

    @property
    def group_by(self):
        return ['month']

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = super(AggChildHealthMonthlyDataSource, self).filters
        if not self.show_test:
            filters.append(NOT(IN('state_id', get_INFilter_bindparams('excluded_states', self.excluded_states))))
        if 'month' in self.config and self.config['month']:
            filters.append(BETWEEN('month', 'two_before', 'month'))
        return filters

    @property
    def order_by(self):
        return [OrderBy('month')]

    @property
    def columns(self):
        return [
            DatabaseColumn('month', SimpleColumn('month')),
            AggregateColumn(
                '% Weighing efficiency (Children <5 weighed)',
                percent_num,
                [
                    SumColumn('nutrition_status_weighed'),
                    SumColumn('wer_eligible', alias='wer_eligible')
                ],
                slug='status_weighed'
            ),
            DatabaseColumn(
                'Total number Unweighed',
                SumColumn('nutrition_status_unweighed')
            ),
            AggregateColumn(
                'Percent Children severely underweight (weight for age)',
                percent_num,
                [
                    SumColumn('nutrition_status_severely_underweight'),
                    AliasColumn('wer_eligible')
                ],
                slug='severely_underweight'
            ),
            AggregateColumn(
                'Percent Children moderately underweight (weight for age)',
                percent_num,
                [
                    SumColumn('nutrition_status_moderately_underweight'),
                    AliasColumn('wer_eligible')
                ],
                slug='moderately_underweight'
            ),
            AggregateColumn(
                'Percent Children normal (weight for age)',
                percent_num,
                [
                    SumColumn('nutrition_status_normal'),
                    AliasColumn('wer_eligible')
                ],
                slug='status_normal'
            ),
            AggregateColumn(
                'Percent children with severe acute malnutrition (weight-for-height)',
                percent_num,
                [
                    SumColumn('wasting_severe'),
                    SumColumn('height_eligible', alias='height_eligible')
                ],
                slug='wasting_severe'
            ),
            AggregateColumn(
                'Percent children with moderate acute malnutrition (weight-for-height)',
                percent_num,
                [
                    SumColumn('wasting_moderate'),
                    AliasColumn('height_eligible')
                ],
                slug='wasting_moderate'
            ),
            AggregateColumn(
                'Percent children normal (weight-for-height)',
                percent_num,
                [
                    SumColumn('wasting_normal'),
                    AliasColumn('height_eligible')
                ],
                slug='wasting_normal'
            ),
            AggregateColumn(
                'Percent children with severe stunting (height for age)',
                percent_num,
                [
                    SumColumn('stunting_severe'),
                    AliasColumn('height_eligible')
                ],
                slug='stunting_severe'
            ),
            AggregateColumn(
                'Percent children with moderate stunting (height for age)',
                percent_num,
                [
                    SumColumn('stunting_moderate'),
                    AliasColumn('height_eligible')
                ],
                slug='stunting_moderate'
            ),
            AggregateColumn(
                'Percent children with normal (height for age)',
                percent_num,
                [
                    SumColumn('stunting_normal'),
                    AliasColumn('height_eligible')
                ],
                slug='stunting_normal'
            ),
            AggregateColumn(
                'Percent children immunized with 1st year immunizations',
                lambda x, y, z: ((x or 0) + (y or 0)) * 100 / float(z or 1),
                [
                    SumColumn('fully_immunized_on_time'),
                    SumColumn('fully_immunized_late'),
                    SumColumn('fully_immunized_eligible')
                ],
                slug='fully_immunized'
            ),
            AggregateColumn(
                'Percent Children breastfed at birth',
                percent_num,
                [
                    SumColumn('bf_at_birth'),
                    SumColumn('born_in_month')
                ],
                slug='breastfed_at_birth'
            ),
            AggregateColumn(
                'Percent Children exclusively breastfed',
                percent_num,
                [
                    SumColumn('ebf_in_month'),
                    SumColumn('ebf_eligible')
                ],
                slug='exclusively_breastfed'
            ),
            AggregateColumn(
                'Percent Children initiated appropriate complementary feeding',
                percent_num,
                [
                    SumColumn('cf_initiation_in_month'),
                    SumColumn('cf_initiation_eligible')
                ],
                slug='cf_initiation'
            ),
            AggregateColumn(
                'Perecent children complementary feeding',
                percent_num,
                [
                    SumColumn('cf_in_month'),
                    SumColumn('cf_eligible')
                ],
                slug='complementary_feeding'
            ),
            AggregateColumn(
                'Percentage of children consuming atleast 4 food groups',
                percent_num,
                [
                    SumColumn('cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='diet_diversity'
            ),
            AggregateColumn(
                'Percentage of children consuming adequate food',
                percent_num,
                [
                    SumColumn('cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='diet_quantity'
            ),
            AggregateColumn(
                'Percentage of children whose mothers handwash before feeding',
                percent_num,
                [
                    SumColumn('cf_handwashing'),
                    AliasColumn('cf_eligible')
                ],
                slug='handwashing'
            ),
            DatabaseColumn(
                'Children (0 - 28 Days) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [EQ('age_tranche', 'age_0')],
                    alias='zero'
                ),
                slug='zero'
            ),
            DatabaseColumn(
                'Children (28 Days - 6 mo) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [EQ('age_tranche', 'age_6')],
                    alias='one'
                ),
                slug='one'
            ),
            DatabaseColumn(
                'Children (6 mo - 1 year) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [EQ('age_tranche', 'age_12')],
                    alias='two'
                ),
                slug='two'
            ),
            DatabaseColumn(
                'Children (1 year - 3 years) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [OR([
                        EQ('age_tranche', 'age_24'),
                        EQ('age_tranche', 'age_36')
                    ])],
                    alias='three'
                ),
                slug='three'
            ),
            DatabaseColumn(
                'Children (3 years - 6 years) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [OR([
                        EQ('age_tranche', 'age_48'),
                        EQ('age_tranche', 'age_60'),
                        EQ('age_tranche', 'age_72')
                    ])],
                    alias='four'
                ),
                slug='four'
            )
        ]


class AggCCSRecordMonthlyDataSource(ProgressReportSqlData):
    table_name = 'agg_ccs_record_monthly'
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level='state', show_test=False):
        super(AggCCSRecordMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_id' % loc_level
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.config['excluded_states'] = self.excluded_states
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test

    @property
    def domain(self):
        return self.config['domain']

    @property
    def group_by(self):
        return ['month']

    @property
    def filters(self):
        filters = super(AggCCSRecordMonthlyDataSource, self).filters
        if not self.show_test:
            filters.append(NOT(IN('state_id', get_INFilter_bindparams('excluded_states', self.excluded_states))))
        if 'month' in self.config and self.config['month']:
            filters.append(BETWEEN('month', 'two_before', 'month'))
        return filters

    @property
    def order_by(self):
        return [OrderBy('month')]

    @property
    def columns(self):
        return [
            DatabaseColumn('month', SimpleColumn('month')),
            AggregateColumn(
                'Percent of pregnant women who are anemic in given month',
                lambda x, y, z: ((x or 0) + (y or 0)) * 100 / float(z or 1),
                [
                    SumColumn('anemic_moderate'),
                    SumColumn('anemic_severe'),
                    SumColumn('pregnant', alias='pregnant')
                ],
                slug='severe_anemic'
            ),
            AggregateColumn(
                'Percent tetanus complete',
                percent_num,
                [
                    SumColumn('tetanus_complete'),
                    AliasColumn('pregnant')
                ],
                slug='tetanus_complete'
            ),
            AggregateColumn(
                'Percent women ANC 1 recieved by deliveryy',
                percent_num,
                [
                    SumColumn('anc1_received_at_delivery'),
                    SumColumn('delivered_in_month', alias='delivered_in_month')
                ],
                slug='anc_1'
            ),
            AggregateColumn(
                'Percent women ANC 2 received by delivery',
                percent_num,
                [
                    SumColumn('anc2_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_2'
            ),
            AggregateColumn(
                'Percent women ANC 3 received by delivery',
                percent_num,
                [
                    SumColumn('anc3_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_3'
            ),
            AggregateColumn(
                'Percent women ANC 4 received by delivery',
                percent_num,
                [
                    SumColumn('anc4_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_4'
            ),
            AggregateColumn(
                'Percent women Resting during pregnancy',
                percent_num,
                [
                    SumColumn('resting_during_pregnancy'),
                    AliasColumn('pregnant')
                ],
                slug='resting'
            ),
            AggregateColumn(
                'Percent eating extra meal during pregnancy',
                percent_num,
                [
                    SumColumn('extra_meal'),
                    AliasColumn('pregnant')
                ],
                slug='extra_meal'
            ),
            AggregateColumn(
                'Percent trimester 3 women Counselled on immediate EBF during home visit',
                percent_num,
                [
                    SumColumn('counsel_immediate_bf'),
                    SumColumn('trimester_3')
                ],
                slug='trimester'
            )
        ]


class AggAWCMonthlyDataSource(ProgressReportSqlData):
    table_name = 'agg_awc_monthly'
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level='state', show_test=False):
        super(AggAWCMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_id' % loc_level
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.config['excluded_states'] = self.excluded_states
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test

    @property
    def domain(self):
        return self.config['domain']

    @property
    def filters(self):
        filters = super(AggAWCMonthlyDataSource, self).filters
        if not self.show_test:
            filters.append(NOT(IN('state_id', get_INFilter_bindparams('excluded_states', self.excluded_states))))

        if 'month' in self.config and self.config['month']:
            filters.append(BETWEEN('month', 'two_before', 'month'))
        return filters

    @property
    def group_by(self):
        return ['month']

    @property
    def order_by(self):
        return [OrderBy('month')]

    @property
    def columns(self):
        return [
            DatabaseColumn('month', SimpleColumn('month')),
            # DatabaseColumn(
            #     'Number of AWCs Open In Month',
            #     SumColumn('num_awcs'),
            #     slug='awc_num_open'
            # ),
            # DatabaseColumn(
            #     'Number of Household Registration Forms',
            #     SumColumn('usage_num_hh_reg')
            # ),
            # DatabaseColumn(
            #     'Number of Pregnancy Registration Forms',
            #     SumColumn('usage_num_add_pregnancy')
            # ),
            # DatabaseColumn(
            #     'Number of PSE Forms with Photo',
            #     SumColumn('usage_num_pse_with_image')
            # ),
            # AggregateColumn(
            #     'Home Visit - Number of Birth Preparedness Forms',
            #     lambda x, y, z: x + y + z,
            #     columns=[
            #         SumColumn('usage_num_bp_tri1'),
            #         SumColumn('usage_num_bp_tri2'),
            #         SumColumn('usage_num_bp_tri3')
            #     ],
            #     slug='num_bp'
            # ),
            # DatabaseColumn(
            #     'Home Visit - Number of Delivery Forms',
            #     SumColumn('usage_num_delivery')
            # ),
            # DatabaseColumn(
            #     'Home Visit - Number of PNC Forms',
            #     SumColumn('usage_num_pnc')
            # ),
            # DatabaseColumn(
            #     'Home Visit - Number of EBF Forms',
            #     SumColumn('usage_num_ebf')
            # ),
            # DatabaseColumn(
            #     'Home Visit - Number of CF Forms',
            #     SumColumn('usage_num_cf')
            # ),
            # DatabaseColumn(
            #     'Number of GM forms',
            #     SumColumn('usage_num_gmp')
            # ),
            # DatabaseColumn(
            #     'Number of THR forms',
            #     SumColumn('usage_num_thr')
            # ),
            # AggregateColumn(
            #     'Number of Due List forms',
            #     lambda x, y: x + y,
            #     [
            #         SumColumn('usage_num_due_list_ccs'),
            #         SumColumn('usage_num_due_list_child_health')
            #     ],
            #     slug='due_list'
            # ),
            DatabaseColumn(
                'Number of Households',
                SumColumn('cases_household'),
            ),
            DatabaseColumn(
                'Total Number of Household Members',
                SumColumn('cases_person_all')
            ),
            DatabaseColumn(
                'Total Number of Members Enrolled for Services for services at AWC ',
                SumColumn('cases_person', alias='cases_person')
            ),
            AggregateColumn(
                'Percentage of Beneficiaries with Aadhar',
                lambda x, y: (x or 0) * 100 / float(y or 1),
                [
                    SumColumn('cases_person_has_aadhaar'),
                    AliasColumn('cases_person')
                ],
                slug='aadhar'
            ),
            DatabaseColumn(
                'Total Pregnant women',
                SumColumn('cases_ccs_pregnant_all')
            ),
            DatabaseColumn(
                'Total Pregnant Women Enrolled for services at AWC',
                SumColumn('cases_ccs_pregnant')
            ),
            DatabaseColumn(
                'Total Lactating women',
                SumColumn('cases_ccs_lactating_all')
            ),
            DatabaseColumn(
                'Total Lactating women registered for services at AWC',
                SumColumn('cases_ccs_lactating')
            ),
            DatabaseColumn(
                'Total Children (0-6 years)',
                SumColumn('cases_child_health_all')
            ),
            DatabaseColumn(
                'Total Chldren (0-6 years) registered for service at AWC',
                SumColumn('cases_child_health')
            ),
            DatabaseColumn(
                'Adolescent girls (11-14 years)',
                SumColumn('cases_person_adolescent_girls_11_14_all')
            ),
            DatabaseColumn(
                'Adolescent girls (15-18 years)',
                SumColumn('cases_person_adolescent_girls_15_18_all')
            ),
            DatabaseColumn(
                'Adolescent girls (11-14 years) Seeking Services',
                SumColumn('cases_person_adolescent_girls_11_14')
            ),
            DatabaseColumn(
                'Adolescent girls (15-18 years) Seeking Services',
                SumColumn('cases_person_adolescent_girls_15_18')
            ),
            AggregateColumn(
                '% AWCs with Clean Drinking Water',
                aggregate_fn=percent_num,
                columns=[
                    SumColumn('infra_clean_water'),
                    SumColumn('num_awcs', alias='awcs')
                ],
                slug='clean_water'
            ),
            AggregateColumn(
                '% AWCs with functional toilet',
                percent_num,
                [
                    SumColumn('infra_functional_toilet'),
                    AliasColumn('awcs')
                ],
                slug='functional_toilet'
            ),
            AggregateColumn(
                '% AWCs with Medicine Kit',
                percent_num,
                [
                    SumColumn('infra_medicine_kits'),
                    AliasColumn('awcs')
                ],
                slug='medicine_kits'
            ),
            AggregateColumn(
                '% AWCs with Adult Scale',
                percent_num,
                [
                    SumColumn('infra_adult_weighing_scale'),
                    AliasColumn('awcs')
                ],
                slug='adult_weighing_scale'
            ),
            AggregateColumn(
                '% AWCs with Baby Scale',
                percent_num,
                [
                    SumColumn('infra_infant_weighing_scale'),
                    AliasColumn('awcs')
                ],
                slug='baby_weighing_scale'
            ),
        ]


class ChildrenExport(ExportableMixin, SqlData):
    title = 'Children'
    table_name = 'agg_child_health_monthly'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.extend([
                DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'),
                DatabaseColumn('Gender', SimpleColumn('gender'), slug='gender'),
                DatabaseColumn('Age', SimpleColumn('age_tranche'), slug='age_tranche'),
                DatabaseColumn('Caste', SimpleColumn('caste'), slug='caste'),
                DatabaseColumn('Disabled', SimpleColumn('disabled'), slug='disabled'),
                DatabaseColumn('Minority', SimpleColumn('minority'), slug='minority'),
                DatabaseColumn('Resident', SimpleColumn('resident'), slug='resident')
            ])
        return columns

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            AggregateColumn(
                'Weighing efficiency',
                percent,
                [
                    SumColumn('nutrition_status_weighed'),
                    SumColumn('wer_eligible')
                ],
                slug='percent_weight_efficiency'
            ),
            DatabaseColumn(
                'Total number of unweighed children',
                SumColumn('nutrition_status_unweighed'),
                slug='total_number_unweighed'
            ),
            AggregateColumn(
                'Percentage of severely underweight children',
                percent,
                [
                    SumColumn('nutrition_status_severely_underweight'),
                    AliasColumn('wer_eligible')
                ],
                slug='percent_severe_underweight'
            ),
            AggregateColumn(
                'Percentage of moderately underweight children',
                percent,
                [
                    SumColumn('nutrition_status_moderately_underweight'),
                    AliasColumn('wer_eligible')
                ],
                slug='percent_moderate_underweight'
            ),
            AggregateColumn(
                'Percentage of normal weight-for-age children',
                percent,
                [
                    SumColumn('nutrition_status_normal'),
                    AliasColumn('wer_eligible')
                ],
                slug='percent_normal_weight'
            ),
            AggregateColumn(
                'Percentage of children with severe wasting',
                percent,
                [
                    SumColumn('wasting_severe'),
                    SumColumn('height_eligible')
                ],
                slug='percent_severe_wasting'
            ),
            AggregateColumn(
                'Percentage of children with moderate wasting',
                percent,
                [
                    SumColumn('wasting_moderate'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_moderate_wasting'
            ),
            AggregateColumn(
                'Percentage of children with normal weight-for-height',
                percent,
                [
                    SumColumn('wasting_normal'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_normal_wasting'
            ),
            AggregateColumn(
                'Percentage of children with severe stunting',
                percent,
                [
                    SumColumn('stunting_severe'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_severe_stunting'
            ),
            AggregateColumn(
                'Percentage of children with moderate stunting',
                percent,
                [
                    SumColumn('stunting_moderate'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_moderate_stunting'
            ),
            AggregateColumn(
                'Percentage of children with normal height-for-age',
                percent,
                [
                    SumColumn('stunting_normal'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_normal_stunting'
            ),
            AggregateColumn(
                'Percentage of children with completed 1 year immunizations',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('fully_immunized_on_time'),
                    SumColumn('fully_immunized_late'),
                    SumColumn('fully_immunized_eligible')
                ],
                slug='percent_completed_1year_immunizations'
            ),
            AggregateColumn(
                'Percentage of children breastfed at birth',
                percent,
                [
                    SumColumn('bf_at_birth'),
                    SumColumn('born_in_month')
                ],
                slug='percent_breastfed_at_birth'
            ),
            AggregateColumn(
                'Percentage of children with early initiation of breastfeeding',
                percent,
                [
                    SumColumn('ebf_in_month'),
                    SumColumn('ebf_eligible')
                ],
                slug='percent_ebf'
            ),
            AggregateColumn(
                'Percentage of children initiated complementary feeding (in the past 30 days)',
                percent,
                [
                    SumColumn('cf_initiation_in_month'),
                    SumColumn('cf_initiation_eligible')
                ],
                slug='percent_initiated_on_cf'
            ),
            AggregateColumn(
                'Percentage of children initiated appropriate complementary feeding (cumulative)',
                percent,
                [
                    SumColumn('cf_in_month'),
                    SumColumn('cf_eligible')
                ],
                slug='percent_appropriate_cf'
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet diversity',
                percent,
                [
                    SumColumn('cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_diversity'
            ),
            AggregateColumn(
                'Percentage of children receiving complementary feeding with adequate diet quanity',
                percent,
                [
                    SumColumn('cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_quanity'
            ),
            AggregateColumn(
                "Percentage of children receiving complementary feeding "
                "with appropriate handwashing before feeding",
                percent,
                [
                    SumColumn('cf_handwashing'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_handwashing_before_feeding'
            ),
        ]
        return columns + agg_columns


class PregnantWomenExport(ExportableMixin, SqlData):
    title = 'Pregnant Women'
    table_name = 'agg_ccs_record_monthly'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.extend([
                DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'),
                DatabaseColumn('CCS Status', SimpleColumn('ccs_status'), slug='ccs_status'),
                DatabaseColumn('Trimester', SimpleColumn('trimester'), slug='trimester'),
                DatabaseColumn('Caste', SimpleColumn('caste'), slug='caste'),
                DatabaseColumn('Disabled', SimpleColumn('disabled'), slug='disabled'),
                DatabaseColumn('Minority', SimpleColumn('minority'), slug='minority'),
                DatabaseColumn('Resident', SimpleColumn('resident'), slug='resident')
            ])
        return columns

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            DatabaseColumn('Number of lactating women', SumColumn('lactating'), slug='lactating'),
            DatabaseColumn('Number of pregnant women', SumColumn('pregnant'), slug='pregnant'),
            DatabaseColumn('Number of postnatal women', SumColumn('postnatal'), slug='postnatal'),
            AggregateColumn(
                'Percentage Anemia',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('anemic_moderate'),
                    SumColumn('anemic_severe'),
                    AliasColumn('pregnant')
                ],
                slug='percent_anemia'
            ),
            AggregateColumn(
                'Percentage Tetanus Completed',
                percent,
                [
                    SumColumn('tetanus_complete'),
                    AliasColumn('pregnant')
                ],
                slug='percent_tetanus_complete'
            ),
            AggregateColumn(
                'Percentage of women who received ANC 1 by delivery',
                percent,
                [
                    SumColumn('anc1_received_at_delivery'),
                    SumColumn('delivered_in_month')
                ],
                slug='percent_anc1_received_by_delivery'
            ),
            AggregateColumn(
                'Percentage of women who received ANC 2 by delivery',
                percent,
                [
                    SumColumn('anc2_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc2_received_by_delivery'
            ),
            AggregateColumn(
                'Percentage of women who received ANC 3 by delivery',
                percent,
                [
                    SumColumn('anc3_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc3_received_by_delivery'
            ),
            AggregateColumn(
                'Percentage of women who received ANC 4 by delivery',
                percent,
                [
                    SumColumn('anc4_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc4_received_by_delivery'
            ),
            AggregateColumn(
                'Percentage of women resting during pregnancy',
                percent,
                [
                    SumColumn('resting_during_pregnancy'),
                    AliasColumn('pregnant')
                ],
                slug='percent_resting_during_pregnancy'
            ),
            AggregateColumn(
                'Percentage of women eating extra meal during pregnancy',
                percent,
                [
                    SumColumn('extra_meal'),
                    AliasColumn('pregnant')
                ],
                slug='percent_eating_extra_meal_during_pregnancy'
            ),
            AggregateColumn(
                'Percentage of trimester 3 women counselled on immediate breastfeeding',
                percent,
                [
                    SumColumn('counsel_immediate_bf'),
                    SumColumn('trimester_3')
                ],
                slug='percent_trimester_3_women_counselled_on_immediate_bf'
            )
        ]
        return columns + agg_columns


class DemographicsChildHealth(ExportableMixin, SqlData):
    engine_id = 'icds-test-ucr'

    table_name = 'agg_child_health_monthly'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.append(DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'))
        return columns

    @property
    def group_by(self):
        group_by_columns = self.get_columns_by_loc_level
        group_by = ['aggregation_level']
        for column in group_by_columns:
            group_by.append(column.slug)
        return group_by

    @property
    def order_by(self):
        order_by_columns = self.get_columns_by_loc_level
        order_by = []
        for column in order_by_columns:
            order_by.append(OrderBy(column.slug))
        return order_by

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            DatabaseColumn(
                'num_children_0_6mo_enrolled_for_services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [
                        OR([
                            RawFilter("age_tranche = '0'"),
                            RawFilter("age_tranche = '6'")
                        ])
                    ],
                    alias='num_children_0_6mo_enrolled_for_services'
                ),
                slug='num_children_0_6mo_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_6mo3yr_enrolled_for_services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [
                        OR([
                            RawFilter("age_tranche = '12'"),
                            RawFilter("age_tranche = '24'"),
                            RawFilter("age_tranche = '36'")
                        ])
                    ],
                    alias='num_children_6mo3yr_enrolled_for_services'
                ),
                slug='num_children_6mo3yr_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_3yr6yr_enrolled_for_services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [
                        OR([
                            RawFilter("age_tranche = '48'"),
                            RawFilter("age_tranche = '60'"),
                            RawFilter("age_tranche = '72'")
                        ])
                    ],
                    alias='num_children_3yr6yr_enrolled_for_services'
                ),
                slug='num_children_3yr6yr_enrolled_for_services'
            ),
        ]
        return columns + agg_columns


class DemographicsAWCMonthly(ExportableMixin, SqlData):
    table_name = 'agg_awc_monthly'
    engine_id = 'icds-test-ucr'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.append(DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'))
        return columns

    @property
    def group_by(self):
        group_by_columns = self.get_columns_by_loc_level
        group_by = ['aggregation_level']
        for column in group_by_columns:
            group_by.append(column.slug)
        return group_by

    @property
    def order_by(self):
        order_by_columns = self.get_columns_by_loc_level
        order_by = []
        for column in order_by_columns:
            order_by.append(OrderBy(column.slug))
        return order_by

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            DatabaseColumn(
                'num_households',
                SumColumn('cases_household'),
                slug='num_households'
            ),
            DatabaseColumn(
                'num_people',
                SumColumn('cases_person_all'),
                slug='num_people'
            ),
            DatabaseColumn(
                'num_people_enrolled_for_services',
                SumColumn('cases_person'),
                slug='num_people_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_people_with_aadhar',
                SumColumn('cases_person_has_aadhaar'),
                slug='num_people_with_aadhar'
            ),
            DatabaseColumn(
                'num_pregnant_women',
                SumColumn('cases_ccs_pregnant_all'),
                slug='num_pregnant_women'
            ),
            DatabaseColumn(
                'num_pregnant_women_enrolled_for_services',
                SumColumn('cases_ccs_pregnant'),
                slug='num_pregnant_women_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_lactating_women',
                SumColumn('cases_ccs_lactating_all'),
                slug='num_lactating_women'
            ),
            DatabaseColumn(
                'num_lactating_women_enrolled_for_services',
                SumColumn('cases_ccs_lactating'),
                slug='num_lactating_women_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_0_6years',
                SumColumn('cases_child_health_all'),
                slug='num_children_0_6years'
            ),
            DatabaseColumn(
                'num_children_0_6years_enrolled_for_services',
                SumColumn('cases_child_health'),
                slug='num_children_0_6years_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_adolescent_girls_11yr14yr',
                SumColumn('cases_person_adolescent_girls_11_14_all'),
                slug='num_adolescent_girls_11yr14yr'
            ),
            DatabaseColumn(
                'num_adolescent_girls_15yr18yr',
                SumColumn('cases_person_adolescent_girls_15_18_all'),
                slug='num_adolescent_girls_15yr18yr'
            ),
            DatabaseColumn(
                'num_adolescent_girls_11yr14yr_enrolled_for_services',
                SumColumn('cases_person_adolescent_girls_11_14'),
                slug='num_adolescent_girls_11yr14yr_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_adolescent_girls_15yr18yr_enrolled_for_services',
                SumColumn('cases_person_adolescent_girls_15_18'),
                slug='num_adolescent_girls_15yr18yr_enrolled_for_services'
            )
        ]
        return columns + agg_columns


class DemographicsExport(ExportableMixin):
    title = 'Demographics'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            {
                'header': 'State',
                'slug': 'state_name'
            }
        ]
        if self.loc_level > 1:
            columns.append(
                {
                    'header': 'District',
                    'slug': 'district_name'
                }
            )
        if self.loc_level > 2:
            columns.append(
                {
                    'header': 'Block',
                    'slug': 'block_name'
                }
            )
        if self.loc_level > 3:
            columns.append(
                {
                    'header': 'Supervisor',
                    'slug': 'supervisor_name'
                }
            )
        if self.loc_level > 4:
            columns.append(
                {
                    'header': 'AWC',
                    'slug': 'awc_name'
                }
            )
        return columns

    def get_data(self):
        awc_monthly = DemographicsAWCMonthly(self.config, self.loc_level).get_data()
        child_health = DemographicsChildHealth(self.config, self.loc_level).get_data()
        connect_column = 'state_name'
        if self.loc_level == 2:
            connect_column = 'district_name'
        elif self.loc_level == 3:
            connect_column = 'block_name'
        elif self.loc_level == 4:
            connect_column = 'supervisor_name'
        elif self.loc_level == 5:
            connect_column = 'awc_name'

        for awc_row in awc_monthly:
            for child_row in child_health:
                if awc_row[connect_column] == child_row[connect_column]:
                    awc_row.update(child_row)
                    break

        return awc_monthly

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        return columns + [
            {
                'header': 'Number of households',
                'slug': 'num_households'
            },
            {
                'header': 'Number of people',
                'slug': 'num_people'
            },
            {
                'header': 'Number of people enrolled for services',
                'slug': 'num_people_enrolled_for_services'
            },
            {
                'header': 'Number of people with aadhar',
                'slug': 'num_people_with_aadhar'
            },
            {
                'header': 'Number of pregnant women',
                'slug': 'num_pregnant_women'
            },
            {
                'header': 'Number of pregnant women enrolled for services',
                'slug': 'num_pregnant_women_enrolled_for_services'
            },
            {
                'header': 'Number of lactating women',
                'slug': 'num_lactating_women'
            },
            {
                'header': 'Number of lactating women enrolled for services',
                'slug': 'num_lactating_women_enrolled_for_services'
            },
            {
                'header': 'Number of children 0-6 years old',
                'slug': 'num_children_0_6years'
            },
            {
                'header': 'Number of children 0-6 years old enrolled for services',
                'slug': 'num_children_0_6years_enrolled_for_services'
            },
            {
                'header': 'Number of children 0-6 months old enrolled for services',
                'slug': 'num_children_0_6mo_enrolled_for_services'
            },
            {
                'header': 'Number of children 6 months to 3 years old enrolled for services',
                'slug': 'num_children_6mo3yr_enrolled_for_services'
            },
            {
                'header': 'Number of children 3 to 6 years old enrolled for services',
                'slug': 'num_children_3yr6yr_enrolled_for_services'
            },
            {
                'header': 'Number of adolescent girls 11 to 14 years old',
                'slug': 'num_adolescent_girls_11yr14yr'
            },
            {
                'header': 'Number of adolescent girls 15 to 18 years old',
                'slug': 'num_adolescent_girls_15yr18yr'
            },
            {
                'header': 'Number of adolescent girls 11 to 14 years old that are enrolled for services',
                'slug': 'num_adolescent_girls_11yr14yr_enrolled_for_services'
            },
            {
                'header': 'Number of adolescent girls 15 to 18 years old that are enrolled for services',
                'slug': 'num_adolescent_girls_15yr18yr_enrolled_for_services'
            }
        ]


class SystemUsageExport(ExportableMixin, SqlData):
    title = 'System Usage'
    table_name = 'agg_awc_monthly'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.append(DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'))
        return columns

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            DatabaseColumn(
                'Number of days AWC was open in the given month',
                SumColumn('awc_num_open'),
                format_fn=lambda x: (x or 0),
                slug='num_awc_open'
            ),
            DatabaseColumn(
                'Number of household registration forms',
                SumColumn('usage_num_hh_reg'),
                slug='num_hh_reg_forms'
            ),
            DatabaseColumn(
                'Number of add pregnancy forms',
                SumColumn('usage_num_add_pregnancy'),
                slug='num_add_pregnancy_forms'
            ),
            AggregateColumn(
                'Number of birth preparedness forms',
                lambda x, y, z: x + y + z,
                [
                    SumColumn('usage_num_bp_tri1'),
                    SumColumn('usage_num_bp_tri2'),
                    SumColumn('usage_num_bp_tri3')
                ],
                slug='num_bp_forms'
            ),
            DatabaseColumn(
                'Number of birth preparedness forms',
                SumColumn('usage_num_delivery'),
                slug='num_delivery_forms'
            ),
            DatabaseColumn('Number of PNC forms', SumColumn('usage_num_pnc'), slug='num_pnc_forms'),
            DatabaseColumn(
                'Number of early initiation of breastfeeding forms',
                SumColumn('usage_num_ebf'),
                slug='num_ebf_forms'
            ),
            DatabaseColumn(
                'Number of complementary feeding forms',
                SumColumn('usage_num_cf'),
                slug='num_cf_forms'
            ),
            DatabaseColumn(
                'Number of growth monitoring forms',
                SumColumn('usage_num_gmp'),
                slug='num_gmp_forms'
            ),
            DatabaseColumn(
                'Number of take home rations forms',
                SumColumn('usage_num_thr'),
                slug='num_thr_forms'
            ),
            AggregateColumn(
                'Number of due list forms',
                lambda x, y: x + y,
                [
                    SumColumn('usage_num_due_list_ccs'),
                    SumColumn('usage_num_due_list_child_health')
                ],
                slug='num_due_list_forms')
        ]
        return columns + agg_columns


class AWCInfrastructureExport(ExportableMixin, SqlData):
    title = 'AWC Infrastructure'
    table_name = 'agg_awc_monthly'

    @property
    def get_columns_by_loc_level(self):
        columns = [
            DatabaseColumn('State', SimpleColumn('state_name'))
        ]
        if self.loc_level > 1:
            columns.append(DatabaseColumn('District', SimpleColumn('district_name'), slug='district_name'))
        if self.loc_level > 2:
            columns.append(DatabaseColumn('Block', SimpleColumn('block_name'), slug='block_name'))
        if self.loc_level > 3:
            columns.append(DatabaseColumn('Supervisor', SimpleColumn('supervisor_name'), slug='supervisor_name'))
        if self.loc_level > 4:
            columns.append(DatabaseColumn('AWC', SimpleColumn('awc_name'), slug='awc_name'))
        return columns

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            AggregateColumn(
                'Percentage AWCs with drinking water',
                percent,
                [
                    SumColumn('infra_clean_water'),
                    SumColumn('num_awcs')
                ],
                slug='percent_with_drinking_water'
            ),
            AggregateColumn(
                'Percentage AWCs with functional toilet',
                percent,
                [
                    SumColumn('infra_functional_toilet'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_with_functional_toilet'
            ),
            AggregateColumn(
                'Percentage AWCs with medicine kit',
                percent,
                [
                    SumColumn('infra_medicine_kits'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_with_medicine_kit'
            ),
            AggregateColumn(
                'Percentage AWCs with weighing scale: infants',
                percent,
                [
                    SumColumn('infra_adult_weighing_scale'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_adult_scale'
            ),
            AggregateColumn(
                'Percentage AWCs with weighing scale: mother and child',
                percent,
                [
                    SumColumn('infra_baby_weighing_scale'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_baby_scale'
            )
        ]
        return columns + agg_columns


class ICDSDatabaseColumn(DatabaseColumn):
    def get_raw_value(self, row):
        return (self.view.get_value(row) or '') if row else ''


class BeneficiaryExport(ExportableMixin, SqlData):
    title = 'Child Beneficiary'
    table_name = 'child_health_monthly_view'

    @property
    def group_by(self):
        group_by_columns = self.get_columns_by_loc_level
        group_by = []
        for column in group_by_columns:
            if column.slug != 'current_age':
                group_by.append(column.slug)
        return group_by

    @property
    def order_by(self):
        return [OrderBy('person_name')]

    @property
    def get_columns_by_loc_level(self):

        def current_age(dob):
            return int(round((self.config['month'] - dob).days / 365.25))

        columns = [
            DatabaseColumn(
                'Name',
                SimpleColumn('person_name'),
                slug='person_name'
            ),
            DatabaseColumn(
                'Date of Birth',
                SimpleColumn('dob'),
                slug='dob'
            ),
            DatabaseColumn(
                'Current Age (In years)',
                AliasColumn('dob'),
                format_fn=current_age,
                slug='current_age'
            ),
            DatabaseColumn(
                'Sex ',
                SimpleColumn('sex'),
                slug='sex'
            ),
            ICDSDatabaseColumn(
                '1 Year Immunizations Complete',
                SimpleColumn('fully_immunized_date'),
                format_fn=lambda x: 'Yes' if x != '' else 'No'
            ),
            DatabaseColumn(
                'Month for data shown',
                SimpleColumn('month'),
                slug='month'
            ),
            DatabaseColumn(
                'Weight recorded',
                SimpleColumn('recorded_weight'),
                slug='recorded_weight'
            ),
            DatabaseColumn(
                'Height recorded',
                SimpleColumn('recorded_height'),
                slug='recorded_height'
            ),
            DatabaseColumn(
                'Weight-for-Age Status',
                SimpleColumn('current_month_nutrition_status'),
                slug='current_month_nutrition_status'
            ),
            DatabaseColumn(
                'Weight-for-Height Status',
                SimpleColumn('current_month_stunting'),
                slug="current_month_stunting"
            ),
            DatabaseColumn(
                'Height-for-Age status',
                SimpleColumn('current_month_wasting'),
                slug="current_month_wasting"
            ),
            DatabaseColumn(
                'PSE Attendance',
                SimpleColumn('pse_days_attended'),
                slug="pse_days_attended"
            ),
        ]
        return columns

    @property
    def columns(self):
        return self.get_columns_by_loc_level


class ProgressReport(object):

    def __init__(self, config=None, loc_level='state', show_test=False):
        self.loc_level = loc_level
        self.config = config
        self.show_test = show_test

    @property
    def new_table_config(self):
        return [
            {
                'category': 'maternal_and_child_nutrition',
                'title': 'Maternal and Child Nutrition',
                'sections': [
                    {
                        'section_title': 'Nutrition Status of Children',
                        'slug': 'nutrition_status_of_children',
                        'rows_config': [
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Weighing Efficiency (Children <5 weighed)',
                                'slug': 'status_weighed',
                                'average': [],
                                'format': 'percent',
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Total number of unweighed children',
                                'slug': 'nutrition_status_unweighed',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 0 - 5 years who are '
                                          'severely underweight (weight-for-age)',
                                'slug': 'severely_underweight',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 0-5 years who '
                                          'are moderately underweight (weight-for-age)',
                                'slug': 'moderately_underweight',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 0-5 years who are at normal weight-for-age',
                                'slug': 'status_normal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 60 months with severe acute '
                                          'malnutrition (weight-for-height)',
                                'slug': 'wasting_severe',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    'Children from 6 - 60 months with moderate '
                                    'acute malnutrition (weight-for-height)'
                                ),
                                'slug': 'wasting_moderate',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 60 months with normal weight-for-height',
                                'slug': 'wasting_normal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 60 months with severe stunting (height-for-age)',
                                'slug': 'stunting_severe',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 60 months with moderate stunting (height-for-age)',
                                'slug': 'stunting_moderate',
                                'average': [],
                                'format': 'percent',
                                'reverseColors': True,
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 60 months with normal height-for-age',
                                'slug': 'stunting_normal',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'interventions',
                'title': 'Interventions',
                'sections': [
                    {
                        'section_title': 'Nutrition Status of Children',
                        'slug': 'nutrition_status_of_children',
                        'rows_config': [
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children 1 year+ who have recieved complete '
                                          'immunization required by age 1.',
                                'slug': 'fully_immunized',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    },
                    {
                        'section_title': 'Nutrition Status of Pregnant Women',
                        'slug': 'nutrition_status_of_pregnant_women',
                        'rows_config': [
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who are anemic',
                                'slug': 'severe_anemic',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women with tetanus completed',
                                'slug': 'tetanus_complete',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who received ANC 1 by delivery',
                                'slug': 'anc_1',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who received ANC 2 by delivery',
                                'slug': 'anc_2',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who received ANC 3 by delivery',
                                'slug': 'anc_3',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Pregnant women who received ANC 4 by delivery',
                                'slug': 'anc_4',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'behavior_change',
                'title': 'Behavior Change',
                'sections': [
                    {
                        'section_title': 'Child Feeding Indicators',
                        'slug': 'child_feeding_indicators',
                        'rows_config': [
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children who were put to the breast within one hour of birth.',
                                'slug': 'breastfed_at_birth',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Infants 0-6 months of age who '
                                          'are fed exclusively with breast milk.',
                                'slug': 'exclusively_breastfed',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': (
                                    "Children between 6 - 8 months given timely introduction to solid, "
                                    "semi-solid or soft food."
                                ),
                                'slug': 'cf_initiation',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months complementary feeding',
                                'slug': 'complementary_feeding',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months consuming at least 4 food groups',
                                'slug': 'diet_diversity',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months consuming adequate food',
                                'slug': 'diet_quantity',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children from 6 - 24 months '
                                          'whose mothers handwash before feeding',
                                'slug': 'handwashing',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    },
                    {
                        'section_title': 'Nutrition Status of Pregnant Women',
                        'slug': 'nutrition_status_of_pregnant_women',
                        "rows_config": [
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Women resting during pregnancy',
                                'slug': 'resting',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': 'Women eating an extra meal during pregnancy',
                                'slug': 'extra_meal',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggCCSRecordMonthlyDataSource',
                                'header': (
                                    "Pregnant women in 3rd trimester counselled "
                                    "on immediate and exclusive "
                                    "breastfeeding during home visit"
                                ),
                                'slug': 'trimester',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'water_sanitation_and_hygiene',
                'title': 'Water Sanitation And Hygiene',
                "sections": [
                    {
                        'section_title': 'AWC Infrastructure',
                        'slug': 'awc_infrastructure',
                        'rows_config': [
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs with clean drinking water',
                                'slug': 'clean_water',
                                'average': [],
                                'format': 'percent'
                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'AWCs with functional toilet',
                                'slug': 'functional_toilet',
                                'average': [],
                                'format': 'percent'
                            }
                        ]
                    }
                ]
            },
            {
                'category': 'demographics',
                'title': 'Demographics',
                'sections': [
                    {
                        'section_title': 'Demographics',
                        'slug': 'demographics',
                        'rows_config': [
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Number of Households',
                                'slug': 'cases_household',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total Number of Household Members',
                                'slug': 'cases_person_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total number of members enrolled at AWC',
                                'slug': 'cases_person',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adhaar seeded beneficiaries',
                                'slug': 'aadhar',
                                'format': 'percent',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total pregnant women ',
                                'slug': 'cases_ccs_pregnant_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total pregnant women enrolled for servics at AWC',
                                'slug': 'cases_ccs_pregnant',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total lactating women',
                                'slug': 'cases_ccs_lactating_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total lactating women registered for services at AWC',
                                'slug': 'cases_ccs_lactating',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total children (0-6 years)',
                                'slug': 'cases_child_health_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Total chldren (0-6 years) enrolled for ICDS services',
                                'slug': 'cases_child_health',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (0-28 days)  enrolled for ICDS services',
                                'slug': 'zero',
                                'average': [],
                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (28 days - 6 months)  enrolled for ICDS services',
                                'slug': 'one',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (6 months - 1 year)  enrolled for ICDS services',
                                'slug': 'two',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (1 year - 3 years)  enrolled for ICDS services',
                                'slug': 'three',
                                'average': [],

                            },
                            {
                                'data_source': 'AggChildHealthMonthlyDataSource',
                                'header': 'Children (3 years - 6 years)  enrolled for ICDS services',
                                'slug': 'four',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (11-14 years)',
                                'slug': 'cases_person_adolescent_girls_11_14_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (15-18 years)',
                                'slug': 'cases_person_adolescent_girls_15_18_all',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (11-14 years)  enrolled for ICDS services',
                                'slug': 'cases_person_adolescent_girls_11_14',
                                'average': [],

                            },
                            {
                                'data_source': 'AggAWCMonthlyDataSource',
                                'header': 'Adolescent girls (15-18 years)  enrolled for ICDS services',
                                'slug': 'cases_person_adolescent_girls_15_18',
                                'average': [],

                            }
                        ]
                    },
                ]
            }
        ]

    @property
    def data_sources(self):
        return {
            'AggChildHealthMonthlyDataSource': AggChildHealthMonthlyDataSource(
                config=self.config,
                loc_level=self.loc_level,
                show_test=self.show_test
            ),
            'AggCCSRecordMonthlyDataSource': AggCCSRecordMonthlyDataSource(
                config=self.config,
                loc_level=self.loc_level,
                show_test=self.show_test
            ),
            'AggAWCMonthlyDataSource': AggAWCMonthlyDataSource(
                config=self.config,
                loc_level=self.loc_level,
                show_test=self.show_test
            )
        }

    @memoized
    def get_data_for_national_aggregatation(self, data_source_name):
        return NationalAggregationDataSource(self.config, self.data_sources[data_source_name]).get_data()

    def _get_collected_sections(self, config_list):
        sections_by_slug = OrderedDict()
        for config in config_list:
            for section in config['sections']:
                slug = section['slug']
                if slug not in sections_by_slug:
                    sections_by_slug[slug] = {
                        'slug': slug,
                        'section_title': section['section_title'],
                        'rows_config': section['rows_config']
                    }
                else:
                    sections_by_slug[slug]['rows_config'].extend(section['rows_config'])
        return sections_by_slug.values()

    def _get_needed_data_sources(self, config):
        needed_data_sources = set()
        for section in config['sections']:
            for row in section['rows_config']:
                needed_data_sources.add(row['data_source'])
        return needed_data_sources

    def _get_all_data(self, data_sources):
        all_data = []
        first_data_source = data_sources[0]
        for idx in range(0, len(first_data_source)):
            data = first_data_source[idx]
            for other_data_source in data_sources[1:]:
                data.update(other_data_source[idx])
            all_data.append(data)
        return all_data

    @property
    def config_list(self):
        return filter(
            lambda c: c['category'] == self.config['category'] or self.config['category'] == 'all',
            self.new_table_config
        )

    def get_data(self):
        config_list = self.config_list
        if not config_list:
            raise Http404()

        if len(config_list) == 1:
            config = config_list[0]
        else:
            config = {
                'title': 'All',
                'sections': self._get_collected_sections(config_list)
            }

        needed_data_sources = self._get_needed_data_sources(config)

        data_sources = [
            data_source.get_data()
            for k, data_source in self.data_sources.iteritems()
            if k in needed_data_sources
        ]

        all_data = self._get_all_data(data_sources)

        months = [
            dt.strftime("%b %Y") for dt in rrule(
                MONTHLY,
                dtstart=self.config['two_before'],
                until=self.config['month'])
        ]

        for month in months:
            data_for_month = False
            month_data = {}
            for row_data in all_data:
                m = row_data['month'].strftime("%b %Y")
                if month == m:
                    month_data = row_data
                    data_for_month = True

            for section in config['sections']:
                section['months'] = months
                for row in section['rows_config']:
                    if 'data' not in row:
                        row['data'] = [{'html': row['header']}]

                    if data_for_month:
                        if 'average' in row:
                            row['average'] = self.get_data_for_national_aggregatation(
                                row['data_source']
                            )[0][row['slug']]
                        row['data'].append((month_data[row['slug']] or {'html': 0}))
                    else:
                        row['data'].append({'html': 0})

        return {'config': config}
