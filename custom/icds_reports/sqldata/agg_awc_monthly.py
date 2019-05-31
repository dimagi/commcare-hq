from __future__ import absolute_import, division
from __future__ import unicode_literals

from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn
from sqlagg.filters import BETWEEN, IN, NOT
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from corehq.apps.reports.util import get_INFilter_bindparams
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.queries import get_test_state_locations_id
from custom.icds_reports.utils import percent_num, person_has_aadhaar_column, person_is_beneficiary_column
from custom.icds_reports.utils.mixins import ProgressReportMixIn
from custom.utils.utils import clean_IN_filter_value


class AggAWCMonthlyDataSource(ProgressReportMixIn, IcdsSqlData):
    table_name = 'agg_awc_monthly'

    def __init__(self, config=None, loc_level='state', show_test=False, beta=False):
        super(AggAWCMonthlyDataSource, self).__init__(config)
        self.loc_key = '%s_id' % loc_level
        self.excluded_states = get_test_state_locations_id(self.domain)
        self.config['excluded_states'] = self.excluded_states
        clean_IN_filter_value(self.config, 'excluded_states')
        self.show_test = show_test
        self.beta = beta

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
    def person_has_aadhaar_column(self):
        return person_has_aadhaar_column(self.beta)

    @property
    def person_is_beneficiary_column(self):
        return person_is_beneficiary_column(self.beta)

    def get_columns(self, filters):
        return [
            DatabaseColumn('month', SimpleColumn('month')),
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
                SumColumn(self.person_is_beneficiary_column, alias=self.person_is_beneficiary_column)
            ),
            AggregateColumn(
                'Percentage of Beneficiaries with Aadhar',
                lambda x, y: (x or 0) * 100 / float(y or 1),
                [
                    SumColumn(self.person_has_aadhaar_column),
                    AliasColumn(self.person_is_beneficiary_column)
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
                '% AWCs reported clean drinking water',
                aggregate_fn=percent_num,
                columns=[
                    SumColumn('infra_clean_water'),
                    SumColumn('num_awc_infra_last_update', alias='awcs')
                ],
                slug='clean_water'
            ),
            AggregateColumn(
                '% AWCs reported functional toilet',
                percent_num,
                [
                    SumColumn('infra_functional_toilet'),
                    AliasColumn('awcs')
                ],
                slug='functional_toilet'
            ),
            AggregateColumn(
                '% AWCs reported medicine kit',
                percent_num,
                [
                    SumColumn('infra_medicine_kits'),
                    AliasColumn('awcs')
                ],
                slug='medicine_kits'
            ),
            AggregateColumn(
                '% AWCs reported weighing scale for mother and child',
                percent_num,
                [
                    SumColumn('infra_adult_weighing_scale'),
                    AliasColumn('awcs')
                ],
                slug='adult_weighing_scale'
            ),
            AggregateColumn(
                '% AWCs reported weighing scale for infants',
                percent_num,
                [
                    SumColumn('infra_infant_weighing_scale'),
                    AliasColumn('awcs')
                ],
                slug='baby_weighing_scale'
            ),
        ]

    @property
    def columns(self):
        return self.get_columns(self.filters)
