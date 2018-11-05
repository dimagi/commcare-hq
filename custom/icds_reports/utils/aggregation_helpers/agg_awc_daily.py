from __future__ import absolute_import
from __future__ import unicode_literals

import six

from six.moves import map

from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, transform_day_to_month


class AggAwcDailyAggregationHelper(BaseICDSAggregationHelper):
    aggregate_parent_table = 'agg_awc_daily'

    def __init__(self, date):
        self.date = date
        self.month = transform_day_to_month(date)

    @property
    def tablename(self):
        return "{}_{}".format(self.aggregate_parent_table, self.date.strftime("%Y-%m-%d"))

    def drop_table_query(self):
        return 'DROP TABLE IF EXISTS "{}"'.format(self.tablename)

    def create_table_query(self):
        return """
        CREATE TABLE IF NOT EXISTS "{tablename}" (
            CHECK (date = DATE %(date)s),
            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
        ) INHERITS ("{parent_tablename}")
        """.format(
            parent_tablename=self.aggregate_parent_table,
            tablename=self.tablename,
        ), {
            "date": self.date.strftime("%Y-%m-%d"),
        }

    def aggregation_query(self):

        columns = (
            ('state_id',),
            ('district_id',),
            ('block_id',),
            ('supervisor_id',),
            ('awc_id',),
            ('aggregation_level',),
            ('date', '%(date)s'),
            ('cases_household',),
            ('cases_person',),
            ('cases_person_all',),
            ('cases_person_has_aadhaar',),
            ('cases_person_beneficiary',),
            ('cases_child_health',),
            ('cases_child_health_all',),
            ('cases_ccs_pregnant',),
            ('cases_ccs_pregnant_all',),
            ('cases_ccs_lactating',),
            ('cases_ccs_lactating_all',),
            ('cases_person_adolescent_girls_11_14',),
            ('cases_person_adolescent_girls_15_18',),
            ('cases_person_adolescent_girls_11_14_all',),
            ('cases_person_adolescent_girls_15_18_all',),
            ('daily_attendance_open', '0'),
            ('num_awcs',),
            ('num_launched_states',),
            ('num_launched_districts',),
            ('num_launched_blocks',),
            ('num_launched_supervisors',),
            ('num_launched_awcs',),
            ('cases_person_has_aadhaar_v2',),
            ('cases_person_beneficiary_v2',),
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM agg_awc
            WHERE aggregation_level = 5 and month = %(start_date)s
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] if len(col) > 1 else col[0] for col in columns]),
        ), {
            "start_date": self.month,
            "date": self.date
        }

    def update_query(self):
        return """
        UPDATE "{tablename}" agg_awc SET
            daily_attendance_open = ut.daily_attendance_open
        FROM (
            SELECT
                awc_id,
                pse_date,
                sum(awc_open_count) AS daily_attendance_open
            FROM daily_attendance WHERE pse_date = %(date)s
            GROUP BY awc_id, pse_date
        ) ut
        WHERE ut.pse_date = agg_awc.date AND ut.awc_id = agg_awc.awc_id
        """.format(tablename=self.tablename), {
            'date': self.date
        }

    def rollup_query(self, aggregation_level):
        launched_cols = [
            'num_launched_states',
            'num_launched_districts',
            'num_launched_blocks',
            'num_launched_supervisors',
            'num_launched_awcs',
        ]

        def _launched_col(col):
            col_index = launched_cols.index(col)
            col_for_level = launched_cols[aggregation_level]
            if col_index >= aggregation_level:
                return 'sum({})'.format(col)
            else:
                return 'CASE WHEN (sum({}) > 0) THEN 1 ELSE 0 END'.format(col_for_level)

        columns = (
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('aggregation_level', str(aggregation_level)),
            ('date', 'date'),
            ('cases_household',),
            ('cases_person',),
            ('cases_person_all',),
            ('cases_person_has_aadhaar',),
            ('cases_person_beneficiary',),
            ('cases_child_health',),
            ('cases_child_health_all',),
            ('cases_ccs_pregnant',),
            ('cases_ccs_pregnant_all',),
            ('cases_ccs_lactating',),
            ('cases_ccs_lactating_all',),
            ('cases_person_adolescent_girls_11_14',),
            ('cases_person_adolescent_girls_15_18',),
            ('cases_person_adolescent_girls_11_14_all',),
            ('cases_person_adolescent_girls_15_18_all',),
            ('daily_attendance_open',),
            ('num_awcs',),
            ('num_launched_states', lambda col: _launched_col(col)),
            ('num_launched_districts', lambda col: _launched_col(col)),
            ('num_launched_blocks', lambda col: _launched_col(col)),
            ('num_launched_supervisors', lambda col: _launched_col(col)),
            ('num_launched_awcs', lambda col: _launched_col(col)),
            ('cases_person_has_aadhaar_v2',),
            ('cases_person_beneficiary_v2',),
        )

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, six.string_types):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))

            return column, 'SUM({})'.format(column)

        columns = list(map(_transform_column, columns))

        group_by = ["state_id"]
        if aggregation_level > 1:
            group_by.append("district_id")
        if aggregation_level > 2:
            group_by.append("block_id")
        if aggregation_level > 3:
            group_by.append("supervisor_id")
        group_by.append("date")

        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (
            SELECT {calculations}
            FROM "{tablename}"
            WHERE aggregation_level = {aggregation_level}
            GROUP BY {group_by}
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
            aggregation_level=aggregation_level
        )

    def indexes(self):
        agg_locations = ['state_id', 'district_id', 'block_id', 'supervisor_id', 'awc_id']
        indexes = [
            'CREATE INDEX ON "{}" (date)'.format(self.tablename),
            'CREATE INDEX ON "{}" (aggregation_level)'.format(self.tablename),
            'CREATE INDEX ON "{}" ({})'.format(self.tablename, ', '.join(agg_locations)),
        ]

        for location in agg_locations:
            indexes.append('CREATE INDEX ON "{}" ({})'.format(self.tablename, location))
        return indexes
