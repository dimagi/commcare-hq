from StringIO import StringIO

import pytz
from dateutil.rrule import rrule, MONTHLY
from django.db.models.functions import datetime
from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn
from sqlagg.filters import EQ, OR, BETWEEN
from sqlagg.sorting import OrderBy

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn, Column
from custom.icds_reports.utils import ICDSMixin
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response


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


def percent(x, y):
    return "%.2f %%" % ((x or 0) * 100 / float(y or 1))


def percent_num(x, y):
    return (x or 0) * 100 / float(y or 1)


class ExportableMixin(object):
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level=1):
        self.config = config
        self.loc_level = loc_level

    @property
    def filters(self):
        filters = []
        for key, value in self.config.iteritems():
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


class AggChildHealthMonthlyDataSource(SqlData):
    table_name = 'agg_child_health_monthly'
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level='state'):
        super(AggChildHealthMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_site_code' % loc_level
        self.config.update({
            'age_0': '0',
            'age_6': '6',
            'age_12': '12',
            'age_24': '24',
            'age_36': '36',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72'
        })

    @property
    def group_by(self):
        return ['month']

    @property
    def filters(self):
        filters = [EQ('aggregation_level', 'aggregation_level')]
        if self.loc_key in self.config and self.config[self.loc_key]:
            filters.append(EQ(self.loc_key, self.loc_key))
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
                'Percent children immunized with 1st year immunizations ',
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
                    filters=self.filters + [EQ('age_tranche', 'age_0')]
                ),
                slug='zero'
            ),
            DatabaseColumn(
                'Children (28 Days - 6 mo) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [EQ('age_tranche', 'age_6')]
                ),
                slug='one'
            ),
            DatabaseColumn(
                'Children (6 mo - 1 year) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [EQ('age_tranche', 'age_12')]
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
                    ])]
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
                    ])]
                ),
                slug='four'
            )
        ]


class AggCCSRecordMonthlyDataSource(SqlData):
    table_name = 'agg_ccs_record_monthly'
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level='state'):
        super(AggCCSRecordMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_site_code' % loc_level

    @property
    def group_by(self):
        return ['month']

    @property
    def filters(self):
        filters = [EQ('aggregation_level', 'aggregation_level')]
        if self.loc_key in self.config and self.config[self.loc_key]:
            filters.append(EQ(self.loc_key, self.loc_key))
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


class AggAWCMonthlyDataSource(SqlData):
    table_name = 'agg_awc_monthly'
    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level='state'):
        super(AggAWCMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_site_code' % loc_level

    @property
    def filters(self):
        filters = [EQ('aggregation_level', 'aggregation_level')]
        if self.loc_key in self.config and self.config[self.loc_key]:
            filters.append(EQ(self.loc_key, self.loc_key))
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
                DatabaseColumn('Gender', SimpleColumn('ccs_status'), slug='ccs_status'),
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

    def __init__(self, config=None, loc_level=1):
        super(DemographicsChildHealth, self).__init__(config, loc_level)
        self.config.update({
            'age_0': '0',
            'age_6': '6',
            'age_12': '12',
            'age_24': '24',
            'age_36': '36',
            'age_48': '48',
            'age_60': '60',
            'age_72': '72'
        })

    @property
    def filters(self):
        filters = []
        for key, value in self.config.iteritems():
            if not key.startswith('age'):
                filters.append(EQ(key, key))
        return filters

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
                SumColumn('valid_in_month', filters=self.filters + [
                    OR([
                        EQ('age_tranche', 'age_0'),
                        EQ('age_tranche', 'age_6')
                    ])
                ]),
                slug='num_children_0_6mo_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_6mo3yr_enrolled_for_services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [
                        OR([
                            EQ('age_tranche', 'age_12'),
                            EQ('age_tranche', 'age_24'),
                            EQ('age_tranche', 'age_36')
                        ])
                    ]
                ),
                slug='num_children_6mo3yr_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_3yr6yr_enrolled_for_services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [
                        OR([
                            EQ('age_tranche', 'age_48'),
                            EQ('age_tranche', 'age_60'),
                            EQ('age_tranche', 'age_72')
                        ])
                    ]
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
            DatabaseColumn('num_awc_open', SumColumn('num_awcs'), slug='num_awc_open'),
            DatabaseColumn('num_hh_reg_forms', SumColumn('usage_num_hh_reg'), slug='num_hh_reg_forms'),
            DatabaseColumn(
                'num_add_pregnancy_forms',
                SumColumn('usage_num_add_pregnancy'),
                slug='num_add_pregnancy_forms'
            ),
            DatabaseColumn(
                'num_pse_forms_with_image',
                SumColumn('usage_num_pse_with_image'),
                slug='num_pse_forms_with_image'
            ),
            AggregateColumn(
                'num_bp_forms',
                lambda x, y, z: x + y + z,
                [
                    SumColumn('usage_num_bp_tri1'),
                    SumColumn('usage_num_bp_tri2'),
                    SumColumn('usage_num_bp_tri3')
                ],
                slug='num_bp_forms'
            ),
            DatabaseColumn('num_delivery_forms', SumColumn('usage_num_delivery'), slug='num_delivery_forms'),
            DatabaseColumn('num_pnc_forms', SumColumn('usage_num_pnc'), slug='num_pnc_forms'),
            DatabaseColumn('num_ebf_forms', SumColumn('usage_num_ebf'), slug='num_ebf_forms'),
            DatabaseColumn('num_cf_forms', SumColumn('usage_num_cf'), slug='num_cf_forms'),
            DatabaseColumn('num_gmp_forms', SumColumn('usage_num_gmp'), slug='num_gmp_forms'),
            DatabaseColumn('num_thr_forms', SumColumn('usage_num_thr'), slug='num_thr_forms'),
            AggregateColumn(
                'num_due_list_forms',
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


class ProgressReport(object):

    def __init__(self, config=None, loc_level='state'):
        self.loc_level = loc_level
        self.config = config

    @property
    def table_config(self):
        return [
            {
                'section_title': 'Nutrition Status of Children',
                'rows_config': [
                    {
                        'header': 'Weighing Efficiency (Children <5 weighed)',
                        'slug': 'status_weighed',
                        'average': []
                    },
                    {
                        'header': 'Total number of unweighed children',
                        'slug': 'nutrition_status_unweighed',
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Children from 0 - 5 years who are severely underweight (weight-for-age)',
                        'slug': 'severely_underweight',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Children from 0-5 years who are moderately underweight (weight-for-age)',
                        'slug': 'moderately_underweight',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Children from 0-5 years who are at normal weight-for-age',
                        'slug': 'status_normal',
                        'average': []
                    },
                    {
                        'header': 'Children from 6 - 60 months with severe acute malnutrition (weight-for-height)',
                        'slug': 'wasting_severe',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': (
                            'Children from 6 - 60 months with moderate acute malnutrition (weight-for-height)'
                        ),
                        'slug': 'wasting_moderate',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Children from 6 - 60 months with normal weight-for-height',
                        'slug': 'wasting_normal',
                        'average': []
                    },
                    {
                        'header': 'Children from 6 - 60 months with severe stunting (height-for-age)',
                        'slug': 'stunting_severe',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Children from 6 - 60 months with moderate stunting (height-for-age)',
                        'slug': 'stunting_moderate',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Children from 6 - 60 months with normal height-for-age',
                        'slug': 'stunting_normal',
                        'average': []
                    },
                    {
                        'header': 'Children 1 year+ who have recieved complete immunization required by age 1.',
                        'slug': 'fully_immunized',
                        'average': []
                    }
                ]
            },
            {
                'section_title': 'Child Feeding Indicators',
                'rows_config': [
                    {
                        'header': 'Children who were put to the breast within one hour of birth.',
                        'slug': 'breastfed_at_birth',
                        'average': []
                    },
                    {
                        'header': 'Infants 0-6 months of age who are fed exclusively with breast milk.',
                        'slug': 'exclusively_breastfed',
                        'average': []
                    },
                    {
                        'header': (
                            "Children between 6 - 8 months given timely introduction to solid, "
                            "semi-solid or soft food."
                        ),
                        'slug': 'cf_initiation',
                        'average': []
                    },
                    {
                        'header': 'Children from 6 - 24 months complementary feeding',
                        'slug': 'complementary_feeding',
                        'average': []
                    },
                    {
                        'header': 'Children from 6 - 24 months consuming at least 4 food groups',
                        'slug': 'diet_diversity',
                        'average': []
                    },
                    {
                        'header': 'Children from 6 - 24 months consuming adequate food',
                        'slug': 'diet_quantity',
                        'average': []
                    },
                    {
                        'header': 'Children from 6 - 24 months whose mothers handwash before feeding',
                        'slug': 'handwashing',
                        'average': []
                    }
                ]
            },
            {
                'section_title': 'Nutrition Status of Pregnant Woment',
                'rows_config': [
                    {
                        'header': 'Pregnant women who are anemic',
                        'slug': 'severe_anemic',
                        'average': [],
                        'reverseColors': 'true',
                    },
                    {
                        'header': 'Pregnant women with tetanus completed',
                        'slug': 'tetanus_complete',
                        'average': []
                    },
                    {
                        'header': 'Pregnant women who received ANC 1 by delivery',
                        'slug': 'anc_1',
                        'average': []
                    },
                    {
                        'header': 'Pregnant women who received ANC 2 by delivery',
                        'slug': 'anc_2',
                        'average': []
                    },
                    {
                        'header': 'Pregnant women who received ANC 3 by delivery',
                        'slug': 'anc_3',
                        'average': []
                    },
                    {
                        'header': 'Pregnant women who received ANC 4 by delivery',
                        'slug': 'anc_4',
                        'average': []
                    },
                    {
                        'header': 'Women resting during pregnancy',
                        'slug': 'resting',
                        'average': []
                    },
                    {
                        'header': 'Women eating an extra meal during pregnancy',
                        'slug': 'extra_meal',
                        'average': []
                    },
                    {
                        'header': (
                            "Pregnant women in 3rd trimester counselled on immediate and exclusive "
                            "breastfeeding during home visit"
                        ),
                        'slug': 'trimester',
                        'average': []
                    }
                ]
            },
            # {
            #     'section_title': 'System Usage',
            #     'rows_config': [
            #         {'header': 'Number of AWCs Open in Month', 'slug': 'awc_num_open'},
            #         {'header': 'Number of Household Registration Forms', 'slug': 'usage_num_hh_reg'},
            #         {'header': 'Number of Pregnancy Registration Forms', 'slug': 'usage_num_add_pregnancy'},
            #         {'header': 'Number of PSE Forms with Photo', 'slug': 'usage_num_pse_with_image'},
            #         {'header': 'Home Visit - Number of Birth Preparedness Forms', 'slug': 'num_bp'},
            #         {'header': 'Home Visit - Number of Delivery Forms', 'slug': 'usage_num_delivery'},
            #         {'header': 'Home Visit - Number of PNC Forms', 'slug': 'usage_num_pnc'},
            #         {'header': 'Home Visit - Number of EBF Forms', 'slug': 'usage_num_ebf'},
            #         {'header': 'Home Visit - Number of CF Forms', 'slug': 'usage_num_cf'},
            #         {'header': 'Number of GM Forms', 'slug': 'usage_num_gmp'},
            #         {'header': 'Number of THR forms', 'slug': 'usage_num_thr'},
            #         {'header': 'Number of Due List forms', 'slug': 'due_list'},
            #     ]
            # },
            {
                'section_title': 'Demographics',
                'rows_config': [
                    {'header': 'Number of Households', 'slug': 'cases_household'},
                    {'header': 'Total Number of Household Members', 'slug': 'cases_person_all'},
                    {
                        'header': 'Total number of members enrolled at AWC',
                        'slug': 'cases_person'
                    },
                    {'header': 'Adhaar seeded beneficiaries', 'slug': 'aadhar', 'format': 'percent'},
                    {'header': 'Total pregnant women ', 'slug': 'cases_ccs_pregnant_all'},
                    {'header': 'Total pregnant women enrolled for servics at AWC', 'slug': 'cases_ccs_pregnant'},
                    {'header': 'Total lactating women', 'slug': 'cases_ccs_lactating_all'},
                    {
                        'header': 'Total lactating women registered for services at AWC',
                        'slug': 'cases_ccs_lactating'
                    },
                    {'header': 'Total children (0-6 years)', 'slug': 'cases_child_health_all'},
                    {
                        'header': 'Total chldren (0-6 years) enrolled for ICDS services',
                        'slug': 'cases_child_health'
                    },
                    {'header': 'Children (0-28 days)  enrolled for ICDS services', 'slug': 'zero'},
                    {'header': 'Children (28 days - 6 months)  enrolled for ICDS services', 'slug': 'one'},
                    {'header': 'Children (6 months - 1 year)  enrolled for ICDS services', 'slug': 'two'},
                    {'header': 'Children (1 year - 3 years)  enrolled for ICDS services', 'slug': 'three'},
                    {'header': 'Children (3 years - 6 years)  enrolled for ICDS services', 'slug': 'four'},
                    {
                        'header': 'Adolescent girls (11-14 years)',
                        'slug': 'cases_person_adolescent_girls_11_14_all'
                    },
                    # {
                    #     'header': 'Adolescent girls (15-18 years)',
                    #     'slug': 'cases_person_adolescent_girls_15_18_all'
                    # },
                    {
                        'header': 'Adolescent girls (11-14 years)  enrolled for ICDS services',
                        'slug': 'cases_person_adolescent_girls_11_14'
                    },
                    # {
                    #     'header': 'Adolescent girls (15-18 years)  enrolled for ICDS services',
                    #     'slug': 'cases_person_adolescent_girls_15_18'
                    # }
                ]
            },
            {
                'section_title': 'AWC Infrastructure',
                'rows_config': [
                    {
                        'header': 'AWCs with clean drinking water',
                        'slug': 'clean_water',
                        'average': []
                    },
                    {
                        'header': 'AWCs with functional toilet',
                        'slug': 'functional_toilet',
                        'average': []
                    },
                    {
                        'header': 'AWCs with medicine kit',
                        'slug': 'medicine_kits',
                        'average': []
                    },
                    {
                        'header': 'AWCs with weighing scale for infants',
                        'slug': 'baby_weighing_scale',
                        'average': []
                    },
                    {
                        'header': 'AWCs with weighing scale for mother and child',
                        'slug': 'adult_weighing_scale',
                        'average': []
                    },
                ]
            }
        ]

    def get_data(self):
        health_monthly = AggChildHealthMonthlyDataSource(config=self.config, loc_level=self.loc_level).get_data()
        record_monthly = AggCCSRecordMonthlyDataSource(config=self.config, loc_level=self.loc_level).get_data()
        awc_monthly = AggAWCMonthlyDataSource(config=self.config, loc_level=self.loc_level).get_data()
        all_data = []
        for idx in range(0, len(health_monthly)):
            data = health_monthly[idx]
            data.update(record_monthly[idx])
            data.update(awc_monthly[idx])
            all_data.append(data)

        config = self.table_config

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

            for section in config:
                section['months'] = months
                for row in section['rows_config']:
                    if 'data' not in row:
                        row['data'] = [{'html': row['header']}]

                    if data_for_month:
                        if 'average' in row:
                            row['average'].append(month_data[row['slug']]['html'])
                        row['data'].append((month_data[row['slug']] or {'html': 0}))
                    else:
                        row['data'].append({'html': 0})

        return {'config': config}
