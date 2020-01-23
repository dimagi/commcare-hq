from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GOV_VHND_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationPartitionedHelper,
)


class GovVhndFormAggDistributedHelper(StateBasedAggregationPartitionedHelper):
    helper_key = 'gov-vhnd-form'
    ucr_data_source_id = 'static-vhnd_form'
    aggregate_parent_table = AGG_GOV_VHND_TABLE
    aggregate_child_table_prefix = 'icds_db_gov_vhnd_form_'

    def __init__(self, state_id, month):
        self.month = month
        self.state_id = state_id

    def aggregate_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(self.month)
        next_month_start = self.month + relativedelta(months=1)

        query_params = {
            "start_date": month_formatter(month),
            "end_date": month_formatter(next_month_start),
            "state_id": self.state_id
        }

        return """
        INSERT INTO "{tablename}" (
          awc_id, vhsnd_date_past_month, state_id, anm_mpw_present, asha_present, child_immu, anc_today,
          month
        )(
        SELECT
          DISTINCT awc_id as awc_id,
          FIRST_VALUE(vhsnd_date_past_month) over w as vhsnd_date_past_month,
          FIRST_VALUE(state_id) over w as state_id,
          FIRST_VALUE(anm_mpw=1) over w as anm_mpw_present,
          FIRST_VALUE(asha_present=1) over w as asha_present,
          FIRST_VALUE(child_immu=1) over w as child_immu,
          FIRST_VALUE(anc_today=1) over w as anc_today,
          %(start_date)s::DATE AS month
          FROM "{ucr_tablename}"
            WHERE vhsnd_date_past_month >= %(start_date)s AND
            vhsnd_date_past_month < %(end_date)s AND state_id = %(state_id)s
          WINDOW w AS (
                PARTITION BY awc_id
                ORDER BY vhsnd_date_past_month RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
          )ORDER BY awc_id, month
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename,
        ), query_params
