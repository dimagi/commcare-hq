from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GROWTH_MONITORING_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class GrowthMonitoringFormsAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'growth-monitoring-forms'
    ucr_data_source_id = 'static-dashboard_growth_monitoring_forms'
    aggregate_parent_table = AGG_GROWTH_MONITORING_TABLE
    aggregate_child_table_prefix = 'icds_db_gm_form_'

    def aggregate(self, cursor):
        prev_month_query, prev_month_params = self.create_table_query(self.month - relativedelta(months=1))
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(prev_month_query, prev_month_params)
        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        # We need many windows here because we want the last time changed for each of these columns
        # Window definitions inspired by https://stackoverflow.com/a/47223416
        # The CASE/WHEN's are needed, because time end should be NULL when a form has not changed the value,
        # but the windows include all forms (this works because we use LAST_VALUE and NULLs are sorted to the top
        return """
            SELECT
                DISTINCT child_health_case_id AS case_id,
                LAST_VALUE(supervisor_id) OVER weight_child AS supervisor_id,
                LAST_VALUE(weight_child) OVER weight_child AS weight_child,
                CASE
                    WHEN LAST_VALUE(weight_child) OVER weight_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER weight_child
                END AS weight_child_last_recorded,
                LAST_VALUE(height_child) OVER height_child AS height_child,
                CASE
                    WHEN LAST_VALUE(height_child) OVER height_child IS NULL THEN NULL
                    ELSE LAST_VALUE(timeend) OVER height_child
                END AS height_child_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa
                END AS zscore_grading_wfa,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfa) OVER zscore_grading_wfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfa
                END AS zscore_grading_wfa_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa
                END AS zscore_grading_hfa,
                CASE
                    WHEN LAST_VALUE(zscore_grading_hfa) OVER zscore_grading_hfa = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_hfa
                END AS zscore_grading_hfa_last_recorded,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh
                END AS zscore_grading_wfh,
                CASE
                    WHEN LAST_VALUE(zscore_grading_wfh) OVER zscore_grading_wfh = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER zscore_grading_wfh
                END AS zscore_grading_wfh_last_recorded,
                CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(muac_grading) OVER muac_grading
                END AS muac_grading,
                CASE
                    WHEN LAST_VALUE(muac_grading) OVER muac_grading = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER muac_grading
                END AS muac_grading_last_recorded
            FROM "{ucr_tablename}"
            WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s
                AND state_id = %(state_id)s AND child_health_case_id IS NOT NULL
            WINDOW
                weight_child AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN weight_child IS NULL THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                height_child AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN height_child IS NULL THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_wfa AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_wfa = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_hfa AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_hfa = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                zscore_grading_wfh AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN zscore_grading_wfh = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ),
                muac_grading AS (
                    PARTITION BY child_health_case_id
                    ORDER BY
                        CASE WHEN muac_grading = 0 THEN 0 ELSE 1 END ASC,
                        timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
        """.format(ucr_tablename=self.ucr_tablename), {
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "state_id": self.state_id
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        previous_month_tablename = self.generate_child_tablename(month - relativedelta(months=1))

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        # The '1970-01-01' is a fallback, this should never happen,
        # but an unexpected NULL should not block other data
        return """
        INSERT INTO "{tablename}" (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            weight_child, weight_child_last_recorded,
            height_child, height_child_last_recorded,
            zscore_grading_wfa, zscore_grading_wfa_last_recorded,
            zscore_grading_hfa, zscore_grading_hfa_last_recorded,
            zscore_grading_wfh, zscore_grading_wfh_last_recorded,
            muac_grading, muac_grading_last_recorded
        ) (
          SELECT
            %(state_id)s AS state_id,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) AS supervisor_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(
                ucr.weight_child_last_recorded,
                ucr.height_child_last_recorded,
                ucr.zscore_grading_wfa_last_recorded,
                ucr.zscore_grading_hfa_last_recorded,
                ucr.zscore_grading_wfh_last_recorded,
                ucr.muac_grading_last_recorded,
                prev_month.latest_time_end_processed,
                '1970-01-01'
            ) AS latest_time_end_processed,
            COALESCE(ucr.weight_child, prev_month.weight_child) AS weight_child,
            GREATEST(ucr.weight_child_last_recorded, prev_month.weight_child_last_recorded) AS weight_child_last_recorded,
            COALESCE(ucr.height_child, prev_month.height_child) AS height_child,
            GREATEST(ucr.height_child_last_recorded, prev_month.height_child_last_recorded) AS height_child_last_recorded,
            COALESCE(ucr.zscore_grading_wfa, prev_month.zscore_grading_wfa) AS zscore_grading_wfa,
            GREATEST(ucr.zscore_grading_wfa_last_recorded, prev_month.zscore_grading_wfa_last_recorded) AS zscore_grading_wfa_last_recorded,
            COALESCE(ucr.zscore_grading_hfa, prev_month.zscore_grading_hfa) AS zscore_grading_hfa,
            GREATEST(ucr.zscore_grading_hfa_last_recorded, prev_month.zscore_grading_hfa_last_recorded) AS zscore_grading_hfa_last_recorded,
            COALESCE(ucr.zscore_grading_wfh, prev_month.zscore_grading_wfh) AS zscore_grading_wfh,
            GREATEST(ucr.zscore_grading_wfh_last_recorded, prev_month.zscore_grading_wfh_last_recorded) AS zscore_grading_wfh_last_recorded,
            COALESCE(ucr.muac_grading, prev_month.muac_grading) AS muac_grading,
            GREATEST(ucr.muac_grading_last_recorded, prev_month.muac_grading_last_recorded) AS muac_grading_last_recorded
          FROM ({ucr_table_query}) ucr
          FULL OUTER JOIN "{previous_month_tablename}" prev_month
          ON ucr.case_id = prev_month.case_id
        )
        """.format(
            ucr_table_query=ucr_query,
            previous_month_tablename=previous_month_tablename,
            tablename=tablename
        ), query_params
