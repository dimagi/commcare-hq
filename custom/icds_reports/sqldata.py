from StringIO import StringIO
from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn
from sqlagg.filters import EQ

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn
from custom.icds_reports.utils import ICDSMixin
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response


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
    engine_id = 'ucr'

    def __init__(self, config=None, loc_level='state'):
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
        return ['%s_name' % self.loc_level]

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
