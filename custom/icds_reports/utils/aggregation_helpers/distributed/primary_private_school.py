from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_PRIMARY_PRIVATE_SCHOOL_FORMS
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class AggPrimaryPrivateSchoolAggregate(StateBasedAggregationDistributedHelper):
    helper_key = 'primary-school'
    ucr_data_source_id = 'static-dashboard_primary_private_school'
    aggregate_parent_table = AGG_PRIMARY_PRIVATE_SCHOOL_FORMS

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
        SELECT DISTINCT ON (person_case_id)
            %(state_id)s AS state_id,
            supervisor_id,
            %(month)s::DATE AS month,
            person_case_id,
            admitted_private_school='yes' AS admitted_private_school,
            date_admission_private_school,
            returned_private_school='yes' AS returned_private_school,
            date_return_private_school,
            admitted_primary_school='yes' AS admitted_primary_school,
            date_admission_primary_school
            from "{ucr_tablename}"
            WHERE state_id = %(state_id)s AND
                timeend < %(next_month_start)s
            ORDER BY person_case_id, timeend DESC
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
