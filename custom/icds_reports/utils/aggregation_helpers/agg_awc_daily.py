from __future__ import absolute_import
from __future__ import unicode_literals

import six

from custom.icds_reports.utils.aggregation import BaseICDSAggregationHelper, transform_day_to_month, month_formatter


class AggAwcDailyAggregationHelper(BaseICDSAggregationHelper):
    base_tablename = 'agg_awc_daily'

    def __init__(self, day):
        self.day = day

    def _tablename_func(self):
        return "{}_{}".format(self.base_tablename, self.day.strftime("%Y-%m-%d"))

    @property
    def tablename(self):
        return self._tablename_func()

    def drop_table_query(self):
        return 'DROP TABLE IF EXISTS "{}"'.format(self.tablename)

    def create_table_query(self):
        return """
            CREATE TABLE IF NOT EXISTS "{tablename}" (
            CHECK (date = %(table_date)s)) INHERITS ("{parent_tablename}")
        """.format(
            tablename=self.tablename,
            parent_tablename=self.base_tablename,
        ), {
            "table_date": self.day.strftime('%Y-%m-%d')
        }

    def aggregation_query(self):
        current_month = month_formatter(self.day)
        columns = (
            ('state_id', 'state_id'),
            ('district_id', 'district_id'),
            ('block_id', 'block_id'),
            ('supervisor_id', 'supervisor_id'),
            ('awc_id', 'awc_id'),
            ('aggregation_level', 'aggregation_level'),
            ('date', self.day.strftime("'%Y-%m-%d'")),
            ('cases_household', 'cases_household'),
            ('cases_person', 'cases_person'),
            ('cases_person_all', 'cases_person_all'),
            ('cases_person_has_aadhaar', 'cases_person_has_aadhaar'),
            ('cases_person_beneficiary', 'cases_person_beneficiary'),
            ('cases_child_health', 'cases_child_health'),
            ('cases_child_health_all', 'cases_child_health_all'),
            ('cases_ccs_pregnant', 'cases_ccs_pregnant'),
            ('cases_ccs_pregnant_all', 'cases_ccs_pregnant_all'),
            ('cases_ccs_lactating', 'cases_ccs_lactating'),
            ('cases_ccs_lactating_all', 'cases_ccs_lactating_all'),
            ('cases_person_adolescent_girls_11_14', 'cases_person_adolescent_girls_11_14'),
            ('cases_person_adolescent_girls_15_18', 'cases_person_adolescent_girls_15_18'),
            ('cases_person_adolescent_girls_11_14_all', 'cases_person_adolescent_girls_11_14_all'),
            ('cases_person_adolescent_girls_15_18_all', 'cases_person_adolescent_girls_15_18_all'),
            ('daily_attendance_open', '0'),
            ('num_awcs', 'num_awcs'),
            ('num_launched_states', 'num_launched_states'),
            ('num_launched_districts', 'num_launched_districts'),
            ('num_launched_blocks', 'num_launched_blocks'),
            ('num_launched_supervisors', 'num_launched_supervisors'),
            ('num_launched_awcs', 'num_launched_awcs'),
            ('cases_person_has_aadhaar_v2', 'cases_person_has_aadhaar_v2'),
            ('cases_person_beneficiary_v2', 'cases_person_beneficiary_v2'),
            ('state_is_test', "state_is_test"),
            ('district_is_test', "district_is_test"),
            ('block_is_test', "block_is_test"),
            ('supervisor_is_test', "supervisor_is_test"),
            ('awc_is_test', "awc_is_test")
        )
        return """
        INSERT INTO "{tablename}" (
            {columns}
        ) (SELECT
            {calculations}
            FROM "agg_awc"
            WHERE aggregation_level = 5 AND month = %(start_date)s
        )
        """.format(
            tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns])
        ), {
            "start_date": current_month
        }

    def aggregation_daily_attendance_query(self):
        return """
        UPDATE "{tablename}" agg_awc SET 
          daily_attendance_open = ut.daily_attendance_open
        FROM (SELECT
          awc_id, 
          pse_date, 
          sum(awc_open_count) AS daily_attendance_open 
          FROM daily_attendance WHERE pse_date = %(start_date)s
          GROUP BY awc_id, pse_date) ut
        WHERE ut.pse_date = agg_awc.date AND ut.awc_id = agg_awc.awc_id;
        """.format(
            tablename=self.tablename
        ), {
            "start_date": self.day
        }

    def rollup_query(self, aggregation_level):

        def num_launched_column(agg_level, col_level):
            loc_levels = ['districts', 'blocks', 'supervisors', 'awcs']
            if col_level > agg_level:
                num_launched_col = 'num_launched_{loc_level}'.format(loc_level=loc_levels[col_level - 2])
                return 'sum({column})'.format(column=num_launched_col)
            else:
                num_launched_col = 'num_launched_{loc_level}'.format(loc_level=loc_levels[agg_level - 1])
                return 'CASE WHEN (sum({column}) > 0) THEN 1 ELSE 0 END'.format(column=num_launched_col)

        columns = (
            ('state_id', 'state_id'),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('awc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('aggregation_level', str(aggregation_level)),
            ('date', 'date'),
            ('cases_household', 'sum(cases_household)'),
            ('cases_person', 'sum(cases_person)'),
            ('cases_person_all', 'sum(cases_person_all)'),
            ('cases_person_has_aadhaar', 'sum(cases_person_has_aadhaar)'),
            ('cases_person_beneficiary', 'sum(cases_person_beneficiary)'),
            ('cases_child_health', 'sum(cases_child_health)'),
            ('cases_child_health_all', 'sum(cases_child_health_all)'),
            ('cases_ccs_pregnant', 'sum(cases_ccs_pregnant)'),
            ('cases_ccs_pregnant_all', 'sum(cases_ccs_pregnant_all)'),
            ('cases_ccs_lactating', 'sum(cases_ccs_lactating)'),
            ('cases_ccs_lactating_all', 'sum(cases_ccs_lactating_all)'),
            ('cases_person_adolescent_girls_11_14', 'sum(cases_person_adolescent_girls_11_14)'),
            ('cases_person_adolescent_girls_15_18', 'sum(cases_person_adolescent_girls_15_18)'),
            ('cases_person_adolescent_girls_11_14_all', 'sum(cases_person_adolescent_girls_11_14_all)'),
            ('cases_person_adolescent_girls_15_18_all', 'sum(cases_person_adolescent_girls_15_18_all)'),
            ('daily_attendance_open', 'sum(daily_attendance_open)'),
            ('num_awcs', 'sum(num_awcs)'),
            ('num_launched_states', num_launched_column(aggregation_level, 1)),
            ('num_launched_districts', num_launched_column(aggregation_level, 2)),
            ('num_launched_blocks', num_launched_column(aggregation_level, 3)),
            ('num_launched_supervisors', num_launched_column(aggregation_level, 4)),
            ('num_launched_awcs', num_launched_column(aggregation_level, 5)),
            ('cases_person_has_aadhaar_v2', 'sum(cases_person_has_aadhaar_v2)'),
            ('cases_person_beneficiary_v2', 'sum(cases_person_beneficiary_v2)'),
            ('state_is_test', lambda col: col if aggregation_level > 1 else "0"),
            ('district_is_test', lambda col: col if aggregation_level > 2 else "0"),
            ('block_is_test', lambda col: col if aggregation_level > 3 else "0"),
            ('supervisor_is_test', lambda col: col if aggregation_level > 4 else "0"),
            ('awc_is_test', lambda col: col if aggregation_level > 5 else "0")
        )

        def _transform_column(column_tuple):
            column = column_tuple[0]

            if len(column_tuple) == 2:
                agg_col = column_tuple[1]
                if isinstance(agg_col, six.string_types):
                    return column_tuple
                elif callable(agg_col):
                    return (column, agg_col(column))

            return (column, 'SUM({})'.format(column))

        columns = list(map(_transform_column, columns))

        group_by = ["state_id", "state_is_test"]
        if aggregation_level > 1:
            group_by.extend(["district_id", "district_is_test"])
        if aggregation_level > 2:
            group_by.extend(["block_id", "block_is_test"])
        if aggregation_level > 3:
            group_by.extend(["supervisor_id", "supervisor_is_test"])

        group_by.append("date")

        return """
                INSERT INTO "{to_tablename}" (
                    {columns}
                ) (
                    SELECT {calculations}
                    FROM "{from_tablename}"
                    WHERE aggregation_level = %(aggregation_level)s
                    GROUP BY {group_by}
                    ORDER BY {group_by}
                )
                """.format(
            to_tablename=self.tablename,
            from_tablename=self.tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by),
        ), {
            'aggregation_level': aggregation_level + 1
        }

    def indexes(self):
        col_indx1 = 'state_id, district_id, block_id, supervisor_id, awc_id'
        indexes = [
            'CREATE INDEX "{tablename}_indx1" ON "{tablename}" ({col_indx1})'.format(
                tablename=self.tablename,
                col_indx1=col_indx1
            ),
            'CREATE INDEX "{tablename}_indx2" ON "{tablename}" (date)'.format(tablename=self.tablename),
            'CREATE INDEX "{tablename}_indx3" ON "{tablename}" (awc_id)'.format(tablename=self.tablename),
            'CREATE INDEX "{tablename}_indx4" ON "{tablename}" (supervisor_id)'.format(tablename=self.tablename),
            'CREATE INDEX "{tablename}_indx5" ON "{tablename}" (block_id)'.format(tablename=self.tablename),
            'CREATE INDEX "{tablename}_indx6" ON "{tablename}" (district_id)'.format(tablename=self.tablename),
            'CREATE INDEX "{tablename}_indx7" ON "{tablename}" (aggregation_level)'.format(tablename=self.tablename),
        ]
        return indexes
