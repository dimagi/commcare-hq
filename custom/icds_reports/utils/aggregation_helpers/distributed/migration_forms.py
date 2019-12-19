from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_MIGRATION_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationDistributedHelper,
)


class MigrationFormsAggregationDistributedHelper(StateBasedAggregationDistributedHelper):
    helper_key = 'migration-forms'
    ucr_date_source_id = 'static-migration_form'
    aggregate_parent_table = AGG_MIGRATION_TABLE

    def aggergation_query(self):
        month = self.month.replace(day=1)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(month=1))

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id,
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
        }

        return """
        INSERT INTO "{tablename}" (
        	case_id, state_id, supervisor_id, month, latest_time_end_processed,
			migration_status
		) (
		  SELECT DISTINCT ON (person_case_id)
		    %(state_id)s AS state_id,
		    supervisor_id,
		    %(month)s AS month,
		    person_case_id as case_id,
		  FROM "{ucr_tablename}"
		  WHERE state_id = %(state_id)s AND
				timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND
				person_case_id IS NOT NULL
		  WINDOW w AS (
		    PARTITION BY supervisor_id, person_case_id
		    ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
		  )
		)
		""".format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.aggregate_parent_table,
        ), query_params
