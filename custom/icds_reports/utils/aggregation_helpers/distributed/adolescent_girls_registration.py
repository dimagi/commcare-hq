from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_ADOLESCENT_GIRLS_REGISTRATION_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)

class AggAdolescentGirlsRegistrationAggregate(StateBasedAggregationDistributedHelper):
    helper_key = 'adolescent-girls'
    ucr_data_source_id = 'static-adolescent_girls_reg_form'
    aggregate_parent_table = AGG_ADOLESCENT_GIRLS_REGISTRATION_TABLE
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
               awc_id,
               %(month)s::DATE AS month,
               person_case_id,
               LAST_VALUE(out_of_school) OVER w IS NOT NULL AND LAST_VALUE(out_of_school) OVER w ='yes' AS out_of_school,
               LAST_VALUE(re_out_of_school) OVER w  IS NOT NULL AND LAST_VALUE(re_out_of_school) OVER w ='yes' AS re_out_of_school,
               LAST_VALUE(admitted_in_school) OVER w IS NOT NULL AND LAST_VALUE(admitted_in_school) OVER w='yes' AS admitted_in_school
               from "{ucr_tablename}"
               WHERE state_id = %(state_id)s AND timeend >= %(current_month_start)s AND
                   timeend < %(next_month_start)s
                WINDOW w AS (
            PARTITION BY supervisor_id, awc_id, person_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
           """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
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
          state_id, supervisor_id, awc_id, month, person_case_id, out_of_school,
          re_out_of_school, admitted_in_school
        ) (
        SELECT
            %(state_id)s AS state_id,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) AS supervisor_id,
            COALESCE(ucr.awc_id, prev_month.awc_id) AS awc_id,
            %(month)s::DATE AS month,
            COALESCE(ucr.person_case_id, prev_month.person_case_id) AS person_case_id,
            CASE WHEN ucr.person_case_id IS NOT NULL
                 THEN ucr.out_of_school IS NOT NULL AND ucr.out_of_school='yes'
                 ELSE prev_month.out_of_school IS NOT NULL AND prev_month.out_of_school END AS out_of_school,
            CASE WHEN ucr.person_case_id IS NOT NULL
                 THEN ucr.re_out_of_school IS NOT NULL AND ucr.re_out_of_school='yes'
                 ELSE prev_month.re_out_of_school IS NOT NULL AND prev_month.re_out_of_school END AS re_out_of_school,
            CASE WHEN ucr.person_case_id IS NOT NULL
                 THEN ucr.admitted_in_school IS NOT NULL AND ucr.admitted_in_school='yes'
                 ELSE prev_month.admitted_in_school IS NOT NULL AND prev_month.admitted_in_school END AS admitted_in_school
            from ({ucr_table_query}) ucr
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
