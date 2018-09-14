from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from sqlagg.base import AliasColumn
from sqlagg.columns import SumColumn, SimpleColumn

from corehq.apps.reports.sqlreport import SqlData, DatabaseColumn, AggregateColumn
from custom.icds_reports.utils import percent, percent_or_not_entered
from custom.icds_reports.utils.mixins import ExportableMixin


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
            columns.append(DatabaseColumn(
                'AWW Phone Number',
                SimpleColumn('contact_phone_number'),
                slug='contact_phone_number')
            )
        return columns

    @property
    def columns(self):
        columns = self.get_columns_by_loc_level
        percent_function = percent_or_not_entered if self.beta else percent
        agg_columns = [
            AggregateColumn(
                'Percentage AWCs reported clean drinking water',
                percent_function,
                [
                    SumColumn('infra_clean_water'),
                    SumColumn('num_awc_infra_last_update', alias='awcs')
                ],
                slug='percent_with_drinking_water'
            ),
            AggregateColumn(
                'Percentage AWCs reported functional toilet',
                percent_function,
                [
                    SumColumn('infra_functional_toilet'),
                    AliasColumn('awcs')
                ],
                slug='percent_with_functional_toilet'
            ),
            AggregateColumn(
                'Percentage AWCs reported medicine kit',
                percent_function,
                [
                    SumColumn('infra_medicine_kits'),
                    AliasColumn('awcs')
                ],
                slug='percent_with_medicine_kit'
            ),
            AggregateColumn(
                'Percentage AWCs reported weighing scale: infants',
                percent_function,
                [
                    SumColumn('infra_infant_weighing_scale'),
                    AliasColumn('awcs')
                ],
                slug='percent_baby_scale'
            ),
            AggregateColumn(
                'Percentage AWCs reported weighing scale: mother and child',
                percent_function,
                [
                    SumColumn('infra_adult_weighing_scale'),
                    AliasColumn('awcs')
                ],
                slug='percent_adult_scale'
            )
        ]
        return columns + agg_columns
