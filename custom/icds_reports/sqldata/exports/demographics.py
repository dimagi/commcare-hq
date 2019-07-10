from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.base import AliasColumn
from sqlagg.columns import SumWhen, SumColumn, SimpleColumn
from sqlagg.sorting import OrderBy

from corehq.apps.reports.sqlreport import DatabaseColumn, AggregateColumn
from custom.icds_reports.sqldata.base import IcdsSqlData
from custom.icds_reports.utils.mixins import ExportableMixin
from custom.icds_reports.utils import person_has_aadhaar_column, person_is_beneficiary_column, percent, \
    phone_number_function


class DemographicsChildHealth(ExportableMixin, IcdsSqlData):
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
            columns.append(DatabaseColumn(
                'AWW Phone Number',
                SimpleColumn('contact_phone_number'),
                format_fn=phone_number_function,
                slug='contact_phone_number')
            )
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
        order_by.append(OrderBy('aggregation_level'))
        return order_by

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        agg_columns = [
            DatabaseColumn(
                'num_children_0_6mo_enrolled_for_services',
                SumWhen(
                    whens={"age_tranche = '0' OR age_tranche = '6'": 'valid_in_month'},
                    alias='num_children_0_6mo_enrolled_for_services'
                ),
                slug='num_children_0_6mo_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_6mo3yr_enrolled_for_services',
                SumWhen(
                    whens={"age_tranche = '12' OR age_tranche = '24' OR age_tranche = '36'": 'valid_in_month'},
                    alias='num_children_6mo3yr_enrolled_for_services'
                ),
                slug='num_children_6mo3yr_enrolled_for_services'
            ),
            DatabaseColumn(
                'num_children_3yr6yr_enrolled_for_services',
                SumWhen(
                    whens={"age_tranche = '48' OR age_tranche = '60' OR age_tranche = '72'": 'valid_in_month'},
                    alias='num_children_3yr6yr_enrolled_for_services'
                ),
                slug='num_children_3yr6yr_enrolled_for_services'
            ),
        ]
        return columns + agg_columns


class DemographicsAWCMonthly(ExportableMixin, IcdsSqlData):
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
        order_by.append(OrderBy('aggregation_level'))
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
                'beneficiary_persons',
                SumColumn(self.person_is_beneficiary_column),
                slug='beneficiary_persons'
            ),
            DatabaseColumn(
                'person_has_aadhaar',
                SumColumn(self.person_has_aadhaar_column),
                slug='person_has_aadhaar'
            ),
            AggregateColumn(
                'num_people_with_aadhar',
                percent,
                [
                    AliasColumn(self.person_has_aadhaar_column),
                    AliasColumn(self.person_is_beneficiary_column)
                ],
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

    @property
    def person_has_aadhaar_column(self):
        return person_has_aadhaar_column(self.beta)

    @property
    def person_is_beneficiary_column(self):
        return person_is_beneficiary_column(self.beta)


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
        awc_monthly = DemographicsAWCMonthly(
            self.config, self.loc_level, show_test=self.show_test, beta=self.beta).get_data()
        child_health = DemographicsChildHealth(
            self.config, self.loc_level, show_test=self.show_test, beta=self.beta).get_data()
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
                'header': (
                    'Total number of beneficiaries (Children under 6 years old, pregnant women and lactating '
                    'women, alive and seeking services) who have an Aadhaar ID'
                ),
                'slug': 'person_has_aadhaar'
            },
            {
                'header': (
                    'Total number of beneficiaries (Children under 6 years old, pregnant women and lactating '
                    'women, alive and seeking services)'),
                'slug': 'beneficiary_persons'
            },
            {
                'header': 'Percent Aadhaar-seeded beneficaries',
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
