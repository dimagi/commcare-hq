from StringIO import StringIO
from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn
from sqlagg.filters import EQ, OR
from sqlagg.sorting import OrderBy

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn
from custom.icds_reports.utils import ICDSMixin
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response

from localsettings import ICDS_UCR_TEST_DATABASE_ALIAS


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

    def to_export(self, format):
        export_file = StringIO()
        excel_rows = []
        headers = []
        for column in self.columns:
            headers.append(column.header)
        excel_rows.append(headers)
        for row in self.get_data():
            row_data = []
            for c in self.columns:
                cell = row[c.slug]
                row_data.append(cell['sort_key'] if 'sort_key' in cell else cell)
            excel_rows.append(row_data)

        excel_data = [
            [
                self.title,
                excel_rows
            ]
        ]

        export_from_tables(excel_data, export_file, format)
        return export_response(export_file, format, self.title)


class MCNChildHealth(ExportableMixin, SqlData):
    table_name = 'agg_child_health_monthly'
    engine_id = 'ucr'

    @property
    def columns(self):
            return [
                DatabaseColumn(
                    self.loc_level.title(),
                    SimpleColumn('%s_name' % self.loc_level)
                ),
                AggregateColumn(
                    '% Weighing efficiency (Children <5 weighed)',
                    percent,
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
                    '% Children severely underweight (weight for age)',
                    percent,
                    [
                        SumColumn('nutrition_status_severely_underweight'),
                        AliasColumn('wer_eligible')
                    ],
                    'severely_underweight'
                ),
                AggregateColumn(
                    '% Children moderately underweight (weight for age)',
                    percent,
                    [
                        SumColumn('nutrition_status_moderately_underweight'),
                        AliasColumn('wer_eligible')
                    ],
                    'moderately_underweight'
                ),
                AggregateColumn(
                    '% Children normal (weight for age)',
                    percent,
                    [
                        SumColumn('nutrition_status_normal'),
                        AliasColumn('wer_eligible')
                    ],
                    'status_normal'
                ),
                AggregateColumn(
                    '% Percent children with severe acute malnutrition (weight-for-height)',
                    percent,
                    [
                        SumColumn('wasting_severe'),
                        SumColumn('height_eligible', alias='height_eligible')
                    ],
                    slug='wasting_severe'
                ),
                AggregateColumn(
                    '% Percent children with moderate acute malnutrition (weight-for-height)',
                    percent,
                    [
                        SumColumn('wasting_moderate'),
                        AliasColumn('height_eligible')
                    ],
                    slug='wasting_moderate'
                ),
                AggregateColumn(
                    '% children normal (weight-for-age)',
                    percent,
                    [
                        SumColumn('westing_normal'),
                        AliasColumn('height_eligible')
                    ],
                    slug='westing_normal'
                ),
                AggregateColumn(
                    '% children with severe stunting (height for age)',
                    percent,
                    [
                        SumColumn('stunting_severe'),
                        AliasColumn('height_eligible')
                    ],
                    slug='stunting_severe'
                ),
                AggregateColumn(
                    '% children with moderate stunting (height for age)',
                    percent,
                    [
                        SumColumn('stunting_moderate'),
                        AliasColumn('height_eligible')
                    ],
                    slug='stunting_moderate'
                ),
                AggregateColumn(
                    '% children with normal (height for age)',
                    percent,
                    [
                        SumColumn('stunting_normal'),
                        AliasColumn('height_eligible')
                    ],
                    slug='stunting_normal'
                ),
                AggregateColumn(
                    '% children immunized with 1st year immunizations',
                    lambda x, y, z: ((x or 0) + (y or 0)) * 100 / float(z or 1),
                    [
                        SumColumn('fully_immunized_on_time'),
                        SumColumn('fully_immunized_late'),
                        SumColumn('fully_immunized_eligible')
                    ],
                    slug='fully_immunized'
                ),
                AggregateColumn(
                    '% children breastfed at birth',
                    percent,
                    [
                        SumColumn('bf_at_birth'),
                        SumColumn('born_in_month')
                    ],
                    slug='breastfed_at_birth'
                ),
                AggregateColumn(
                    '% children exclusively breastfed',
                    percent,
                    [
                        SumColumn('ebf_in_month'),
                        SumColumn('ebf_eligible')
                    ],
                    slug='exclusively_breastfed'
                ),
                AggregateColumn(
                    '% children initiated appropriate complementary feeding',
                    percent,
                    [
                        SumColumn('cf_initiation_in_month'),
                        SumColumn('cf_initiation_eligible')
                    ],
                    slug='cf_initiation'
                ),
                AggregateColumn(
                    '% children complementary feeding',
                    percent,
                    [
                        SumColumn('cf_in_month'),
                        SumColumn('cf_eligible')
                    ],
                    slug='complementary_feeding'
                ),
                AggregateColumn(
                    '% children consuming at least 4 food groups',
                    percent,
                    [
                        SumColumn('cf_diet_diversity'),
                        AliasColumn('cf_eligible')
                    ],
                    slug='diet_diversity'
                ),
                AggregateColumn(
                    '% children consuming adequate food',
                    percent,
                    [
                        SumColumn('cf_diet_quantity'),
                        AliasColumn('cf_eligible')
                    ],
                    slug='diet_quantity'
                ),
                AggregateColumn(
                    '% children whose mothers handwash before feeding',
                    percent,
                    [
                        SumColumn('cf_handwashing'),
                        AliasColumn('cf_eligible')
                    ],
                    slug='handwashing'
                )
            ]


class MCNCCSRecord(ExportableMixin, SqlData):
    table_name = 'agg_ccs_record_monthly'
    engine_id = 'ucr'

    @property
    def columns(self):
        return [
            DatabaseColumn(
                self.loc_level.title(),
                SimpleColumn('%s_name' % self.loc_level)
            ),
            AggregateColumn(
                '% severe anemic',
                lambda x, y, z: ((x or 0) + (y or 0) / float(z or 1)),
                [
                    SumColumn('anemic_moderate'),
                    SumColumn('anemic_severe'),
                    SumColumn('pregnant', alias='pregnant')
                ],
                slug='severe_anemic'
            ),
            AggregateColumn(
                '% tatanus complete',
                percent,
                [
                    SumColumn('tatanus_complete'),
                    AliasColumn('pregnant')
                ],
                slug='tatanus_complete'
            ),
            AggregateColumn(
                '% women ANC 1 received by delivery',
                percent,
                [
                    SumColumn('anc1_received_at_delivery'),
                    SumColumn('delivered_in_month', alias='delivered_in_month')
                ],
                slug='anc_1'
            ),
            AggregateColumn(
                '% women ANC 2 received by delivery',
                percent,
                [
                    SumColumn('anc2_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_2'
            ),
            AggregateColumn(
                '% women ANC 3 received by delivery',
                percent,
                [
                    SumColumn('anc3_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_3'
            ),
            AggregateColumn(
                '% women ANC 4 received by delivery',
                percent,
                [
                    SumColumn('anc4_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='anc_4'
            ),
            AggregateColumn(
                '% women Resting during pregnancy',
                percent,
                [
                    SumColumn('resting_during_pregnancy'),
                    AliasColumn('pregnant')
                ],
                slug='resting'
            ),
            AggregateColumn(
                '% eating extra meal during pregnancy',
                percent,
                [
                    SumColumn('extra_meal'),
                    AliasColumn('pregnant')
                ],
                slug='extra_meal'
            ),
            AggregateColumn(
                '% trimester 3 women Counselled on immediate EBF during home visit',
                percent,
                [
                    SumColumn('counsel_immediate_bf'),
                    SumColumn('trimester_3')
                ],
                slug='trimester'
            )
        ]


class MCN(ExportableMixin):
    title = 'MCN'

    @property
    def columns(self):
        return [
            {'header': self.loc_level.title(), 'slug': self.loc_level.title()},
            {'header': '% Weighing efficiency (Children <5 weighed)', 'slug': 'status_weighed'},
            {'header': 'Total number Unweighed', 'slug': 'nutrition_status_unweighed'},
            {'header': '% Children severely underweight (weight for age)', 'slug': 'severely_underweight'},
            {'header': '% Children moderately underweight (weight for age)', 'slug': 'moderately_underweight'},
            {'header': '% Children normal (weight for age)', 'slug': 'status_normal'},
            {
                'header': '% Percent children with severe acute malnutrition (weight-for-height)',
                'slug': 'wasting_severe'
            },
            {
                'header': '% Percent children with moderate acute malnutrition (weight-for-height)',
                'slug': 'wasting_moderate'
            },
            {'header': '% children normal (weight-for-age)', 'slug': 'westing_normal'},
            {'header': '% children with severe stunting (height for age)', 'slug': 'stunting_severe'},
            {'header': '% children with moderate stunting (height for age)', 'slug': 'stunting_moderate'},
            {'header': '% children with normal (height for age)', 'slug': 'stunting_normal'},
            {'header': '% children immunized with 1st year immunizations', 'slug': 'fully_immunized'},
            {'header': '% children breastfed at birth', 'slug': 'breastfed_at_birth'},
            {'header': '% children exclusively breastfed', 'slug': 'exclusively_breastfed'},
            {'header': '% children initiated appropriate complementary feeding', 'slug': 'cf_initiation'},
            {'header': '% children complementary feeding', 'slug': 'complementary_feeding'},
            {'header': '% children consuming at least 4 food groups', 'slug': 'diet_diversity'},
            {'header': '% children consuming adequate food', 'slug': 'diet_quantity'},
            {'header': '% children whose mothers handwash before feeding', 'slug': 'handwashing'},
            {'header': '% severe anemic', 'slug': 'severe_anemic'},
            {'header': '% tatanus complete', 'slug': 'tatanus_complete'},
            {'header': '% women ANC 1 received by delivery', 'slug': 'anc_1'},
            {'header': '% women ANC 2 received by delivery', 'slug': 'anc_2'},
            {'header': '% women ANC 3 received by delivery', 'slug': 'anc_3'},
            {'header': '% women ANC 4 received by delivery', 'slug': 'anc_4'},
            {'header': '% women Resting during pregnancy', 'slug': 'resting'},
            {'header': '% eating extra meal during pregnancy', 'slug': 'extra_meal'},
            {'header': '% trimester 3 women Counselled on immediate EBF during home visit', 'slug': 'trimester'}
        ]

    @property
    def get_data(self):
        mcn_health = MCNChildHealth(config=self.config, loc_level=self.loc_level).get_data()
        mcn_ccs = MCNCCSRecord(config=self.config, loc_level=self.loc_level).get_data()
        for health in mcn_health:
            health_loc = health[self.loc_level.title()]
            for ccs in mcn_ccs:
                ccs_loc = ccs[self.loc_level.title()]
                if health_loc == ccs_loc:
                    health.update(ccs)
                    break
        return mcn_health


class SystemUsage(ExportableMixin, SqlData):
    title = 'System Usage'
    table_name = 'agg_awc_monthly'
    engine_id = 'ucr'

    @property
    def columns(self):
        return [
            DatabaseColumn(
                self.loc_level.title(),
                SimpleColumn('%s_name' % self.loc_level)
            ),
            DatabaseColumn(
                'Number of AWCs Open in Month',
                SumColumn('awc_open')
            ),
            DatabaseColumn(
                'Number of Household Registration Forms',
                SumColumn('usage_num_hh_reg')
            ),
            DatabaseColumn(
                'Number of Pregnancy Registration Forms',
                SumColumn('usage_num_add_pregnancy')
            ),
            DatabaseColumn(
                'Number of PSE Forms with Photo',
                SumColumn('usage_num_pse_with_image')
            ),
            AggregateColumn(
                'Home Visit - Number of Birth Preparedness Forms',
                lambda x, y, z: x + y + z,
                columns=[
                    SumColumn('usage_num_bp_tri1'),
                    SumColumn('usage_num_bp_tri2'),
                    SumColumn('usage_num_bp_tri3')
                ],
                slug='num_bp'
            ),
            DatabaseColumn(
                'Home Visit - Number of Delivery Forms',
                SumColumn('usage_num_delivery')
            ),
            DatabaseColumn(
                'Home Visit - Number of PNC Forms',
                SumColumn('usage_num_pnc')
            ),
            DatabaseColumn(
                'Home Visit - Number of EBF Forms',
                SumColumn('usage_num_ebf')
            ),
            DatabaseColumn(
                'Home Visit - Number of CF Forms',
                SumColumn('usage_num_cf')
            ),
            DatabaseColumn(
                'Number of GM Forms',
                SumColumn('usage_num_gmp')
            ),
            DatabaseColumn(
                'Number of THR forms',
                SumColumn('usage_num_thr')
            ),
            AggregateColumn(
                'Number of Due List forms',
                lambda x, y: x + y,
                [
                    SumColumn('usage_num_due_list_ccs'),
                    SumColumn('usage_num_due_list_child_health')
                ],
                slug='due_list'
            )

        ]


class DemographicsAwcMonthly(ExportableMixin, SqlData):
    table_name = 'agg_awc_monthly'

    @property
    def columns(self):
        return [
            DatabaseColumn(
                self.loc_level.title(),
                SimpleColumn('%s_name' % self.loc_level)
            ),
            DatabaseColumn(
                'Number of Households',
                SumColumn('cases_household'),
            ),
            DatabaseColumn(
                'Total Number of Household Members',
                SumColumn('cases_person_all')
            ),
            DatabaseColumn(
                'Total Number of Members Enrolled for Services for services at AWC',
                SumColumn('cases_person')
            ),
            DatabaseColumn(
                'Total Pregnant women',
                SumColumn('cases_pregnant_all')
            ),
            DatabaseColumn(
                'Total Pregnant Women Enrolled for services at AWC',
                SumColumn('cases_pregnant')
            ),
            DatabaseColumn(
                'Total Lactating women',
                SumColumn('cases_lactating_all')
            ),
            DatabaseColumn(
                'Total Lactating women registered for services at AWC',
                SumColumn('cases_lactating')
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
                SumColumn('cases_adoloscent_girls_11_14')
            ),
            DatabaseColumn(
                'Adolescent girls (15-18 years)',
                SumColumn('cases_adoloscent_girls_15_18')
            )
        ]


class DemographicsChildHealthMonthly(ExportableMixin, SqlData):
    title = 'Demographics'
    table_name = 'agg_awc_monthly'

    @property
    def columns(self):
        return [
            DatabaseColumn(
                self.loc_level.title(),
                SimpleColumn('%s_name' % self.loc_level)
            ),
            DatabaseColumn(
                'Children (0 - 28 Days) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters.append(EQ('age_tranche', 'zero'))
                ),
                slug='zero'
            ),
            DatabaseColumn(
                'Children (28 Days - 6 mo) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters.append(EQ('age_tranche', 'zero'))
                ),
                slug='one'
            ),
            DatabaseColumn(
                'Children (6 mo - 1 year) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters.append(EQ('age_tranche', 'zero'))
                ),
                slug='two'
            ),
            DatabaseColumn(
                'Children (1 year - 3 years) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters.append(EQ('age_tranche', 'zero'))
                ),
                slug='three'
            ),
            DatabaseColumn(
                'Children (3 years - 6 years) Seeking Services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters.append(EQ('age_tranche', 'zero'))
                ),
                slug='four'
            )
        ]


class Demographics(ExportableMixin):
    title = 'Demographics'

    @property
    def columns(self):
        return [
            {'header': self.loc_level.title(), 'slug': self.loc_level.title()},
            {'header': 'Number of Households', 'slug': 'cases_household'},
            {'header': 'Total Number of Household Members', 'slug': 'cases_person_all'},
            {'header': 'Total Number of Members Enrolled for Services for services at AW', 'slug': 'cases_person'},
            {'header': 'Total Pregnant women', 'slug': 'cases_pregnant_all'},
            {'header': 'Total Pregnant Women Enrolled for services at AWC', 'slug': 'cases_pregnant'},
            {'header': 'Total Lactating women', 'slug': 'cases_lactating_all'},
            {'header': 'Total Lactating women registered for services at AWC', 'slug': 'cases_lactating'},
            {'header': 'Total Children (0-6 years', 'slug': 'cases_child_health_all'},
            {'header': 'Total Chldren (0-6 years) registered for service at AWC', 'slug': 'cases_child_health'},
            {'header': 'Children (0 - 28 Days) Seeking Services', 'slug': 'zero'},
            {'header': 'Children (28 Days - 6 mo) Seeking Services', 'slug': 'one'},
            {'header': 'Children (6 mo - 1 year) Seeking Services', 'slug': 'two'},
            {'header': 'Children (1 year - 3 years) Seeking Services', 'slug': 'three'},
            {'header': 'Children (3 years - 6 years) Seeking Services', 'slug': 'four'},
            {'header': 'Adolescent girls (11-14 years)', 'slug': 'cases_adoloscent_girls_11_14'},
            {'header': 'Adolescent girls (15-18 years)', 'slug': 'cases_adoloscent_girls_15_18'}
        ]

    @property
    def get_data(self):
        awc_monthly = DemographicsAwcMonthly(config=self.config, loc_level=self.loc_level).get_data()
        health_monthly = DemographicsChildHealthMonthly(config=self.config, loc_level=self.loc_level).get_data()
        for awc in awc_monthly:
            awc_loc = awc[self.loc_level.title()]
            for health in health_monthly:
                health_loc = health[self.loc_level.title()]
                if awc_loc == health_loc:
                    awc.update(health)
                    break
        return awc_monthly


class AWCInfrastructure(ExportableMixin, SqlData):
    title = 'AWC Infrastructure'
    table_name = 'agg_awc_monthly'

    @property
    def columns(self):

        return [
            DatabaseColumn(
                self.loc_level.title(),
                SimpleColumn('%s_name' % self.loc_level)
            ),
            AggregateColumn(
                '% AWCs with Clean Drinking Water',
                aggregate_fn=percent,
                columns=[
                    SumColumn('infra_clean_water'),
                    SumColumn('num_awcs', alias='awcs')
                ],
                slug='clean_water'
            ),
            AggregateColumn(
                '% AWCs with functional toilet',
                percent,
                [
                    SumColumn('infra_functional_toilet'),
                    AliasColumn('awcs')
                ],
                slug='functional_toilet'
            ),
            AggregateColumn(
                '% AWCs with Medicine Kit',
                percent,
                [
                    SumColumn('infra_medicine_kits'),
                    AliasColumn('awcs')
                ],
                slug='medicine_kits'
            ),
        ]


class ChildrenExport(ExportableMixin, SqlData):
    title = 'AWC Infrastructure'
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
            AggregateColumn(
                'percent_weight_efficiency',
                percent,
                [
                    SumColumn('nutrition_status_weighed'),
                    SumColumn('wer_eligible')
                ],
                slug='percent_weight_efficiency'
            ),
            DatabaseColumn(
                'total_number_unweighed',
                SumColumn('nutrition_status_unweighed'),
                slug='total_number_unweighed'
            ),
            AggregateColumn(
                'percent_severe_underweight',
                percent,
                [
                    SumColumn('nutrition_status_severely_underweight'),
                    AliasColumn('wer_eligible')
                ],
                slug='percent_severe_underweight'
            ),
            AggregateColumn(
                'percent_moderate_underweight',
                percent,
                [
                    SumColumn('nutrition_status_moderately_underweight'),
                    AliasColumn('wer_eligible')
                ],
                slug='percent_moderate_underweight'
            ),
            AggregateColumn(
                'percent_normal_weight',
                percent,
                [
                    SumColumn('nutrition_status_normal'),
                    AliasColumn('wer_eligible')
                ],
                slug='percent_normal_weight'
            ),
            AggregateColumn(
                'percent_severe_wasting',
                percent,
                [
                    SumColumn('wasting_severe'),
                    SumColumn('height_eligible')
                ],
                slug='percent_severe_wasting'
            ),
            AggregateColumn(
                'percent_moderate_wasting',
                percent,
                [
                    SumColumn('wasting_moderate'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_moderate_wasting'
            ),
            AggregateColumn(
                'percent_normal_wasting',
                percent,
                [
                    SumColumn('wasting_normal'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_normal_wasting'
            ),
            AggregateColumn(
                'percent_severe_stunting',
                percent,
                [
                    SumColumn('stunting_severe'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_severe_stunting'
            ),
            AggregateColumn(
                'percent_moderate_stunting',
                percent,
                [
                    SumColumn('stunting_moderate'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_moderate_stunting'
            ),
            AggregateColumn(
                'percent_normal_stunting',
                percent,
                [
                    SumColumn('stunting_normal'),
                    AliasColumn('height_eligible')
                ],
                slug='percent_normal_stunting'
            ),
            AggregateColumn(
                'percent_completed_1year_immunizations',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('fully_immunized_on_time'),
                    SumColumn('fully_immunized_late'),
                    SumColumn('fully_immunized_eligible')
                ],
                slug='percent_completed_1year_immunizations'
            ),
            AggregateColumn(
                'percent_breastfed_at_birth',
                percent,
                [
                    SumColumn('bf_at_birth'),
                    SumColumn('born_in_month')
                ],
                slug='percent_breastfed_at_birth'
            ),
            AggregateColumn(
                'percent_ebf',
                percent,
                [
                    SumColumn('ebf_in_month'),
                    SumColumn('ebf_eligible')
                ],
                slug='percent_ebf'
            ),
            AggregateColumn(
                'percent_initiated_on_cf',
                percent,
                [
                    SumColumn('cf_initiation_in_month'),
                    SumColumn('cf_initiation_eligible')
                ],
                slug='percent_initiated_on_cf'
            ),
            AggregateColumn(
                'percent_appropriate_cf',
                percent,
                [
                    SumColumn('cf_in_month'),
                    SumColumn('cf_eligible')
                ],
                slug='percent_appropriate_cf'
            ),
            AggregateColumn(
                'percent_cf_diet_diversity',
                percent,
                [
                    SumColumn('cf_diet_diversity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_diversity'
            ),
            AggregateColumn(
                'percent_cf_diet_quanity',
                percent,
                [
                    SumColumn('cf_diet_quantity'),
                    AliasColumn('cf_eligible')
                ],
                slug='percent_cf_diet_quanity'
            ),
            AggregateColumn(
                'percent_cf_handwashing_before_feeding',
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
            DatabaseColumn('Num lactating', SumColumn('lactating'), slug='lactating'),
            DatabaseColumn('Num pregnant', SumColumn('pregnant'), slug='pregnant'),
            DatabaseColumn('Num postnatal', SumColumn('postnatal'), slug='postnatal'),
            AggregateColumn(
                'percent_anemia',
                lambda x, y, z: '%.2f%%' % (((x or 0) + (y or 0)) * 100 / float(z or 1)),
                [
                    SumColumn('anemic_moderate'),
                    SumColumn('anemic_severe'),
                    AliasColumn('pregnant')
                ],
                slug='percent_anemia'
            ),
            AggregateColumn(
                'percent_tetanus_complete',
                percent,
                [
                    SumColumn('tetanus_complete'),
                    AliasColumn('pregnant')
                ],
                slug='percent_tetanus_complete'
            ),
            AggregateColumn(
                'percent_anc1_received_by_delivery',
                percent,
                [
                    SumColumn('anc1_received_at_delivery'),
                    SumColumn('delivered_in_month')
                ],
                slug='percent_anc1_received_by_delivery'
            ),
            AggregateColumn(
                'percent_anc2_received_by_delivery',
                percent,
                [
                    SumColumn('anc2_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc2_received_by_delivery'
            ),
            AggregateColumn(
                'percent_anc3_received_by_delivery',
                percent,
                [
                    SumColumn('anc3_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc3_received_by_delivery'
            ),
            AggregateColumn(
                'percent_anc4_received_by_delivery',
                percent,
                [
                    SumColumn('anc4_received_at_delivery'),
                    AliasColumn('delivered_in_month')
                ],
                slug='percent_anc4_received_by_delivery'
            ),
            AggregateColumn(
                'percent_resting_during_pregnancy',
                percent,
                [
                    SumColumn('resting_during_pregnancy'),
                    AliasColumn('pregnant')
                ],
                slug='percent_resting_during_pregnancy'
            ),
            AggregateColumn(
                'percent_eating_extra_meal_during_pregnancy',
                percent,
                [
                    SumColumn('extra_meal'),
                    AliasColumn('pregnant')
                ],
                slug='percent_eating_extra_meal_during_pregnancy'
            ),
            AggregateColumn(
                'percent_trimester_3_women_counselled_on_immediate_bf',
                percent,
                [
                    SumColumn('counsel_immediate_bf'),
                    SumColumn('trimester_3')
                ],
                slug='percent_trimester_3_women_counselled_on_immediate_bf'
            )
        ]
        return columns + agg_columns


class DemographicsExport(ExportableMixin, SqlData):
    title = 'Demographics'
    table_name = 'agg_Awc_monthly'

    engine_id = 'icds-test-ucr'

    def __init__(self, config=None, loc_level=1):
        super(DemographicsExport, self).__init__(config, loc_level)
        self.config.update({
            'age_0': 0,
            'age_6': 6,
            'age_12': 12,
            'age_24': 24,
            'age_36': 36,
            'age_48': 48,
            'age_60': 60,
            'age_72': 72
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
                'num_households',
                SumColumn('cases_households'),
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
                'num_children_0_28days_enrolled_for_services',
                SumColumn('valid_in_month', filters=self.filters + [EQ('age_tranche', 'age_0')]),
                slug='num_children_0_28days_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_28days6mo_enrolled_for_services',
                SumColumn('valid_in_month', filters=self.filters + [EQ('age_tranche', 'age_6')]),
                slug='num_children_28days6mo_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_6mo1yr_enrolled_for_services',
                SumColumn('valid_in_month', filters=self.filters + [EQ('age_tranche', 'age_12')]),
                slug='num_children_6mo1yr_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_1yr3yr_enrolled_for_services',
                SumColumn(
                    'valid_in_month',
                    filters=self.filters + [
                        OR([
                            EQ('age_tranche', 'age_24'),
                            EQ('age_tranche', 'age_36')
                        ])
                    ]
                ),
                slug='num_children_1yr3yr_enrolled_for_services'
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
            DatabaseColumn(
                'num_adolescent_girls_11yr14yr',
                SumColumn('cases_adolescent_girls_11_14_all'),
                slug='num_adolescent_girls_11yr14yr'
            ),
            DatabaseColumn(
                'num_adolescent_girls_15yr18yr',
                SumColumn('cases_adolescent_girls_15_18_all'),
                slug='num_adolescent_girls_15yr18yr'
            ),
            DatabaseColumn(
                'num_adolescent_girls_11yr14yr_enrolled_for_services',
                SumColumn('cases_adolescent_girls_11_14'),
                slug='num_adolescent_girls_11yr14yr_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_adolescent_girls_15yr18yr_enrolled_for_services',
                SumColumn('cases_adolescent_girls_15_18'),
                slug='num_adolescent_girls_15yr18yr_enrolled_for_services'
            )
        ]
        return columns + agg_columns


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
            DatabaseColumn('num_awc_open', SumColumn('awc_num_open'), slug='num_awc_open'),
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
            AggregateColumn(
                'percent_with_drinking_water',
                percent,
                [
                    SumColumn('infra_clean_water'),
                    SumColumn('num_awcs')
                ],
                slug='percent_with_drinking_water'
            ),
            AggregateColumn(
                'percent_with_functional_toilet',
                percent,
                [
                    SumColumn('infra_functional_toilet'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_with_functional_toilet'
            ),
            AggregateColumn(
                'percent_with_medicine_kit',
                percent,
                [
                    SumColumn('infra_medicine_kits'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_with_medicine_kit'
            ),
            AggregateColumn(
                'percent_adult_scale',
                percent,
                [
                    SumColumn('infra_adult_weighing_scale'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_adult_scale'
            ),
            AggregateColumn(
                'percent_baby_scale',
                percent,
                [
                    SumColumn('infra_baby_weighing_scale'),
                    AliasColumn('num_awcs')
                ],
                slug='percent_baby_scale'
            )
        ]
        return columns + agg_columns
