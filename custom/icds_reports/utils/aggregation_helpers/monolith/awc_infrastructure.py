from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_INFRASTRUCTURE_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class AwcInfrastructureAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'awc-infrastructure'
    ucr_data_source_id = 'static-infrastructure_form_v2'
    aggregate_parent_table = AGG_INFRASTRUCTURE_TABLE
    aggregate_child_table_prefix = 'icds_db_infra_form_'
    column_names = (
        'supervisor_id',
        'timeend',
        'awc_building', 'source_drinking_water', 'toilet_functional',
        'electricity_awc', 'adequate_space_pse',
        'adult_scale_available', 'baby_scale_available', 'flat_scale_available',
        'adult_scale_usable', 'baby_scale_usable', 'cooking_utensils_usable',
        'infantometer_usable', 'medicine_kits_usable', 'stadiometer_usable',
    )

    def aggregate(self, cursor):
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)

    def _window_helper(self, column_name):
        return (
            "LAST_VALUE({column}) OVER {column} AS {column}".format(column=column_name),
            """
            {column} AS (
                PARTITION BY awc_id
                ORDER BY
                    CASE WHEN {column} IS NULL THEN 0 ELSE 1 END ASC,
                    timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
            """.format(column=column_name)
        )

    def data_from_ucr_query(self):
        next_month_start = month_formatter(self.month + relativedelta(months=1))
        six_months_ago = month_formatter(self.month - relativedelta(months=6))

        windows = [
            self._window_helper(column_name)
            for column_name in self.column_names
        ]
        select_lines = ', '.join([window[0] for window in windows])
        window_lines = ', '.join([window[1] for window in windows])

        return """
            SELECT
                DISTINCT awc_id AS awc_id,
                {select_lines}
            FROM "{ucr_tablename}"
            WHERE timeend >= %(six_months_ago)s AND timeend < %(next_month_start)s
                AND state_id = %(state_id)s AND awc_id IS NOT NULL
            WINDOW
                {window_lines}
        """.format(
            ucr_tablename=self.ucr_tablename,
            select_lines=select_lines,
            window_lines=window_lines,
        ), {
            "six_months_ago": six_months_ago,
            "next_month_start": next_month_start,
            "state_id": self.state_id,
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
            state_id, supervisor_id, month, awc_id, latest_time_end_processed,
            awc_building, source_drinking_water, toilet_functional,
            electricity_awc, adequate_space_pse,
            adult_scale_available, baby_scale_available, flat_scale_available,
            adult_scale_usable, baby_scale_usable, cooking_utensils_usable,
            infantometer_usable, medicine_kits_usable, stadiometer_usable
        ) (
          SELECT
            %(state_id)s AS state_id,
            ucr.supervisor_id AS supervisor_id,
            %(month)s AS month,
            ucr.awc_id AS awc_id,
            ucr.timeend as latest_time_end_processed,
            ucr.awc_building as awc_building,
            ucr.source_drinking_water as source_drinking_water,
            ucr.toilet_functional as toilet_functional,
            ucr.electricity_awc as electricity_awc,
            ucr.adequate_space_pse as adequate_space_pse,
            ucr.adult_scale_available as adult_scale_available,
            ucr.baby_scale_available as baby_scale_available,
            ucr.flat_scale_available as flat_scale_available,
            ucr.adult_scale_usable as adult_scale_usable,
            ucr.baby_scale_usable as baby_scale_usable,
            ucr.cooking_utensils_usable as cooking_utensils_usable,
            ucr.infantometer_usable as infantometer_usable,
            ucr.medicine_kits_usable as medicine_kits_usable,
            ucr.stadiometer_usable as stadiometer_usable
          FROM ({ucr_table_query}) ucr
        )
        """.format(
            ucr_table_query=ucr_query,
            tablename=tablename
        ), query_params
