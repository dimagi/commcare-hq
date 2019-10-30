from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_LS_BENEFICIARY_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationPartitionedHelper,
)


class LSBeneficiaryFormAggDistributedHelper(StateBasedAggregationPartitionedHelper):
    helper_key = 'ls-beneficiary-form'
    ucr_data_source_id = 'static-ls_home_visit_forms_filled'
    aggregate_parent_table = AGG_LS_BENEFICIARY_TABLE
    aggregate_child_table_prefix = 'icds_db_ls_beneficiary_form_'

    def aggregate_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        next_month_start = self.month + relativedelta(months=1)

        query_params = {
            "state_id": self.state_id,
            "start_date": month_formatter(month),
            "end_date": month_formatter(next_month_start)
        }

        return """
        CREATE TEMPORARY TABLE "{temp_table}" AS (
            SELECT
            state_id,
            location_id as supervisor_id,
            %(start_date)s::DATE AS month,
            count(*) as form_count,
            count(*) FILTER (WHERE visit_type_entered is not null AND visit_type_entered <> '') as beneficiary_vists
            FROM "{ucr_tablename}"
            WHERE  state_id=%(state_id)s AND submitted_on >= %(start_date)s AND  
                   submitted_on < %(end_date)s
            GROUP BY state_id,location_id
        );
        INSERT INTO "{tablename}" (
        state_id, supervisor_id, month, form_count, beneficiary_vists
        ) (
             SELECT * FROM "{temp_table}"
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename,
            temp_table="temp_{}".format(tablename)
        ), query_params
