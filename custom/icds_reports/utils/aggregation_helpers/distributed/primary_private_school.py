from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import PRIMARY_PRIVATE_SCHOOL
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class PrimaryPrivateSchoolAggregate(StateBasedAggregationDistributedHelper):
    helper_key = 'primary-school'
    ucr_data_source_id = 'static-dashboard_primary_private_school'
    aggregate_parent_table = PRIMARY_PRIVATE_SCHOOL

    def aggregation_query(self):
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
        INSERT INTO "{tablename}" (
          state_id, supervisor_id, month, person_case_id, admitted_private_school, 
          date_admission_private_school, returned_private_school, date_return_private_school,
          admitted_primary_school, date_admission_primary_school
        ) (
          SELECT DISTINCT
            %(state_id)s AS state_id,
            LAST_VALUE(supervisor_id) over w as supervisor_id,
            %(month)s::DATE AS month,
            LAST_VALUE(person_case_id) over w AS person_case_id,
            LAST_VALUE(admitted_private_school) over w ='yes' AS admitted_private_school,
            LAST_VALUE(date_admission_private_school) over w  AS date_admission_private_school,
            LAST_VALUE(returned_private_school) over w='yes'  AS returned_private_school,
            LAST_VALUE(date_return_private_school) over w  AS date_return_private_school,
            CLAST_VALUE(admitted_primary_school) over w='yes'  AS admitted_primary_school,
            LAST_VALUE(date_admission_primary_school) over w AS date_admission_primary_school
          FROM "{ucr_tablename}"
          WHERE state_id = %(state_id)s AND
                timeend < %(next_month_start)s
          WINDOW w AS (
            PARTITION BY supervisor_id, person_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          )
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
