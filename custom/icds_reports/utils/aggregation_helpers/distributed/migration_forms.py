from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_MIGRATION_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class MigrationFormsAggregationDistributedHelper(StateBasedAggregationDistributedHelper):
    helper_key = 'migration-forms'
    ucr_data_source_id = 'static-migration_form'
    aggregate_parent_table = AGG_MIGRATION_TABLE
    months_required = 3

    def data_from_ucr_query(self):
        month = self.month.replace(day=1)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id,
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
        }
        return """
        SELECT DISTINCT
            %(state_id)s AS state_id,
            supervisor_id,
            %(month)s::DATE AS month,
            person_case_id AS person_case_id,
            LAST_VALUE(is_migrated) OVER w AS is_migrated,
            CASE
                WHEN LAST_VALUE(date_left) OVER w IS NULL
                    THEN LAST_VALUE(timeend) OVER w
                ELSE LAST_VALUE(date_left) OVER w
            END AS migration_date
          FROM "{ucr_tablename}"
          WHERE state_id = %(state_id)s AND
                timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
                person_case_id IS NOT NULL
          WINDOW w AS (
            PARTITION BY supervisor_id, person_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table,
        ), query_params

    def aggregation_query(self):
        month = self.month.replace(day=1)

        ucr_query, ucr_query_params = self.data_from_ucr_query()

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id,
            "previous_month": month_formatter(month - relativedelta(months=1)),
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
          state_id, supervisor_id, month, person_case_id, is_migrated, migration_date
        ) (
          SELECT
            %(state_id)s AS state_id,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) AS supervisor_id,
            %(month)s::DATE AS month,
            COALESCE(ucr.person_case_id, prev_month.person_case_id) AS person_case_id,
            COALESCE(ucr.is_migrated, prev_month.is_migrated) as is_migrated,
            COALESCE(ucr.migration_date, prev_month.migration_date) as migration_date
          FROM ({ucr_table_query}) ucr
          FULL OUTER JOIN (
             SELECT * FROM "{prev_tablename}" WHERE state_id = %(state_id)s
             ) prev_month
            ON ucr.person_case_id = prev_month.person_case_id AND ucr.supervisor_id = prev_month.supervisor_id
            WHERE coalesce(ucr.month, %(month)s) = %(month)s
                AND coalesce(prev_month.month, %(previous_month)s) = %(previous_month)s
                AND coalesce(prev_month.state_id, %(state_id)s) = %(state_id)s
        )
        """.format(
            tablename=self.aggregate_parent_table,
            ucr_table_query=ucr_query,
            prev_tablename=self.prev_tablename
        ), query_params
