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
          state_id, supervisor_id, awc_id, month, person_case_id, out_of_school, 
          re_out_of_school, admitted_in_school
        ) (
        SELECT DISTINCT ON (person_case_id)
            %(state_id)s AS state_id,
            supervisor_id,
            awc_id,
            %(month)s::DATE AS month,
            person_case_id,
            out_of_school IS NOT NULL AND out_of_school='yes' AS out_of_school,
            re_out_of_school IS NOT NULL AND re_out_of_school='yes' AS re_out_of_school,
            admitted_in_school IS NOT NULL AND admitted_in_school='yes' AS admitted_in_school
            from "{ucr_tablename}"
            WHERE state_id = %(state_id)s AND
                timeend < %(next_month_start)s
            ORDER BY person_case_id, timeend DESC
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table
        ), query_params
