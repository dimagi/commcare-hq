from __future__ import absolute_import
from sqlagg.columns import CountColumn
from sqlagg.filters import RawFilter

from corehq.apps.reports.sqlreport import DatabaseColumn
from custom.enikshay.reports.generic import EnikshaySqlData
from custom.enikshay.reports.utils import convert_to_raw_filters_list


class ChartsSqlData(EnikshaySqlData):

    @property
    def filters(self):
        filters = super(ChartsSqlData, self).filters
        filters.append(RawFilter('closed = 0'))
        return filters

    @property
    def columns(self):
        return [
            DatabaseColumn(
                '',
                CountColumn(
                    'doc_id',
                    filters=self.filters + convert_to_raw_filters_list(
                        "current_episode_type = 'confirmed_tb'", "previous_tb_treatment = 'no'"
                    ),
                    alias='cat1_patients'
                )
            ),
            DatabaseColumn(
                '',
                CountColumn(
                    'doc_id',
                    filters=self.filters + convert_to_raw_filters_list(
                        "current_episode_type = 'confirmed_tb'", "previous_tb_treatment = 'yes'"
                    ),
                    alias='cat2_patients'
                )
            ),
            DatabaseColumn(
                '',
                CountColumn(
                    'doc_id',
                    filters=self.filters + convert_to_raw_filters_list(
                        "current_episode_type = 'confirmed_tb'"
                    ),
                    alias='total_patients'
                )
            ),

        ]
