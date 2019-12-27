from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GROWTH_MONITORING_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class GrowthMonitoringFormsAggregationDistributedHelper(StateBasedAggregationDistributedHelper):
    helper_key = 'growth-monitoring-forms'
    ucr_data_source_id = 'static-dashboard_growth_monitoring_forms'
    aggregate_parent_table = AGG_GROWTH_MONITORING_TABLE

    def data_from_ucr_query(self, indicator):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        # We need many windows here because we want the last time changed for each of these columns
        # Window definitions inspired by https://stackoverflow.com/a/47223416
        # The CASE/WHEN's are needed, because time end should be NULL when a form has not changed the value,
        # but the windows include all forms (this works because we use LAST_VALUE and NULLs are sorted to the top
        return """
            SELECT
                DISTINCT child_health_case_id AS case_id,
                supervisor_id AS supervisor_id,
                %(current_month_start)s AS month,
                CASE
                    WHEN LAST_VALUE({indicator}) OVER W = 0 THEN NULL
                    ELSE LAST_VALUE({indicator}) OVER W
                END AS {indicator},
                CASE
                    WHEN LAST_VALUE({indicator}) OVER W = 0 THEN NULL
                    ELSE LAST_VALUE(timeend) OVER W
                END AS {indicator}_last_recorded
            FROM "{ucr_tablename}"
            WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s
                AND state_id = %(state_id)s AND child_health_case_id IS NOT NULL
                AND {indicator} IS NOT NULL AND {indicator} != 0
            WINDOW
                W AS (
                    PARTITION BY supervisor_id, child_health_case_id
                    ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
        """.format(ucr_tablename=self.ucr_tablename, indicator=indicator), {
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "state_id": self.state_id,
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)

        query_params = {
            "month": month_formatter(month),
            "previous_month": month_formatter(month - relativedelta(months=1)),
            "state_id": self.state_id
        }

        # Copies the data from the previous month
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
            state_id, supervisor_id, %(month)s, case_id, latest_time_end_processed,
            weight_child, weight_child_last_recorded,
            height_child, height_child_last_recorded,
            zscore_grading_wfa, zscore_grading_wfa_last_recorded,
            zscore_grading_hfa, zscore_grading_hfa_last_recorded,
            zscore_grading_wfh, zscore_grading_wfh_last_recorded,
            muac_grading, muac_grading_last_recorded
          FROM "{tablename}"
          WHERE month = %(previous_month)s AND state_id = %(state_id)s
      )
        """.format(
            tablename=self.aggregate_parent_table
        ), query_params

    def update_queries(self):
        month = self.month.replace(day=1)
        shared_params = {
            "month": month_formatter(month),
            "previous_month": month_formatter(month - relativedelta(months=1)),
            "state_id": self.state_id
        }

        ucr_query, query_params = self.data_from_ucr_query('weight_child')
        query_params.update(shared_params)

        # The '1970-01-01' is a fallback, this should never happen,
        # but an unexpected NULL should not block other data
        yield """
        INSERT INTO "{tablename}" as gm_forms (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            weight_child, weight_child_last_recorded
        ) (
          SELECT
            %(state_id)s,
            supervisor_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            GREATEST(
                ucr.weight_child_last_recorded,
                '1970-01-01'
            ) AS latest_time_end_processed,
            ucr.weight_child,
            ucr.weight_child_last_recorded
          FROM ({ucr_table_query}) ucr
        )
        ON CONFLICT (supervisor_id, case_id, month) DO UPDATE SET
            latest_time_end_processed = GREATEST(
                EXCLUDED.latest_time_end_processed, gm_forms.latest_time_end_processed),
            weight_child = COALESCE(EXCLUDED.weight_child, gm_forms.weight_child),
            weight_child_last_recorded = GREATEST(
                EXCLUDED.weight_child_last_recorded, gm_forms.weight_child_last_recorded)
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.aggregate_parent_table
        ), query_params

        ucr_query, query_params = self.data_from_ucr_query('height_child')
        query_params.update(shared_params)

        yield """
        INSERT INTO "{tablename}" as gm_forms (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            height_child, height_child_last_recorded
        ) (
          SELECT
            %(state_id)s,
            supervisor_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            GREATEST(
                ucr.height_child_last_recorded,
                '1970-01-01'
            ) AS latest_time_end_processed,
            ucr.height_child,
            ucr.height_child_last_recorded
          FROM ({ucr_table_query}) ucr
        )
        ON CONFLICT (supervisor_id, case_id, month) DO UPDATE SET
            latest_time_end_processed = GREATEST(
                EXCLUDED.latest_time_end_processed, gm_forms.latest_time_end_processed),
            height_child = COALESCE(EXCLUDED.height_child, gm_forms.height_child),
            height_child_last_recorded = GREATEST(
                EXCLUDED.height_child_last_recorded, gm_forms.height_child_last_recorded)
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.aggregate_parent_table
        ), query_params

        ucr_query, query_params = self.data_from_ucr_query('zscore_grading_wfa')
        query_params.update(shared_params)

        yield """
        INSERT INTO "{tablename}" as gm_forms (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            zscore_grading_wfa, zscore_grading_wfa_last_recorded
        ) (
          SELECT
            %(state_id)s,
            supervisor_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            GREATEST(
                ucr.zscore_grading_wfa_last_recorded,
                '1970-01-01'
            ) AS latest_time_end_processed,
            ucr.zscore_grading_wfa,
            ucr.zscore_grading_wfa_last_recorded
          FROM ({ucr_table_query}) ucr
        )
        ON CONFLICT (supervisor_id, case_id, month) DO UPDATE SET
            latest_time_end_processed = GREATEST(
                EXCLUDED.latest_time_end_processed, gm_forms.latest_time_end_processed),
            zscore_grading_wfa= COALESCE(
                EXCLUDED.zscore_grading_wfa, gm_forms.zscore_grading_wfa),
            zscore_grading_wfa_last_recorded = GREATEST(
                EXCLUDED.zscore_grading_wfa_last_recorded, gm_forms.zscore_grading_wfa_last_recorded)
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.aggregate_parent_table
        ), query_params

        ucr_query, query_params = self.data_from_ucr_query('zscore_grading_hfa')
        query_params.update(shared_params)

        yield """
        INSERT INTO "{tablename}" as gm_forms (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            zscore_grading_hfa, zscore_grading_hfa_last_recorded
        ) (
          SELECT
            %(state_id)s,
            supervisor_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            GREATEST(
                ucr.zscore_grading_hfa_last_recorded,
                '1970-01-01'
            ) AS latest_time_end_processed,
            ucr.zscore_grading_hfa,
            ucr.zscore_grading_hfa_last_recorded
          FROM ({ucr_table_query}) ucr
        )
        ON CONFLICT (supervisor_id, case_id, month) DO UPDATE SET
            latest_time_end_processed = GREATEST(
                EXCLUDED.latest_time_end_processed, gm_forms.latest_time_end_processed),
            zscore_grading_hfa = COALESCE(
                EXCLUDED.zscore_grading_hfa, gm_forms.zscore_grading_hfa),
            zscore_grading_hfa_last_recorded = GREATEST(
                EXCLUDED.zscore_grading_hfa_last_recorded, gm_forms.zscore_grading_hfa_last_recorded)
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.aggregate_parent_table
        ), query_params

        ucr_query, query_params = self.data_from_ucr_query('zscore_grading_wfh')
        query_params.update(shared_params)

        yield """
        INSERT INTO "{tablename}" as gm_forms (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            zscore_grading_wfh, zscore_grading_wfh_last_recorded
        ) (
          SELECT
            %(state_id)s,
            supervisor_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            GREATEST(
                ucr.zscore_grading_wfh_last_recorded,
                '1970-01-01'
            ) AS latest_time_end_processed,
            ucr.zscore_grading_wfh,
            ucr.zscore_grading_wfh_last_recorded
          FROM ({ucr_table_query}) ucr
        )
        ON CONFLICT (supervisor_id, case_id, month) DO UPDATE SET
            latest_time_end_processed = GREATEST(
                EXCLUDED.latest_time_end_processed, gm_forms.latest_time_end_processed),
            zscore_grading_wfh = COALESCE(
                EXCLUDED.zscore_grading_wfh, gm_forms.zscore_grading_wfh),
            zscore_grading_wfh_last_recorded = GREATEST(
                EXCLUDED.zscore_grading_wfh_last_recorded, gm_forms.zscore_grading_wfh_last_recorded)
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.aggregate_parent_table
        ), query_params

        ucr_query, query_params = self.data_from_ucr_query('muac_grading')
        query_params.update(shared_params)

        yield """
        INSERT INTO "{tablename}" as gm_forms (
            state_id, supervisor_id, month, case_id, latest_time_end_processed,
            muac_grading, muac_grading_last_recorded
        ) (
          SELECT
            %(state_id)s,
            supervisor_id,
            %(month)s AS month,
            ucr.case_id AS case_id,
            GREATEST(
                ucr.muac_grading_last_recorded,
                '1970-01-01'
            ) AS latest_time_end_processed,
            ucr.muac_grading,
            ucr.muac_grading_last_recorded
          FROM ({ucr_table_query}) ucr
        )
        ON CONFLICT (supervisor_id, case_id, month) DO UPDATE SET
            latest_time_end_processed = GREATEST(
                EXCLUDED.latest_time_end_processed, gm_forms.latest_time_end_processed),
            muac_grading = COALESCE(EXCLUDED.muac_grading, gm_forms.muac_grading),
            muac_grading_last_recorded = GREATEST(
                EXCLUDED.muac_grading_last_recorded, gm_forms.muac_grading_last_recorded)
        """.format(
            ucr_table_query=ucr_query,
            tablename=self.aggregate_parent_table
        ), query_params
