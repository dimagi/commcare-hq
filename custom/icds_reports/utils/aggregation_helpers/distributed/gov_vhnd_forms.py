from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GOV_VHND_TABLE
from custom.icds_reports.utils.aggregation_helpers import date_to_string
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
        tablename = self.generate_child_tablename(self.month)
        next_month_start = self.month + relativedelta(months=1)

        query_params = {
            "start_date": date_to_string(self.month),
            "end_date": date_to_string(next_month_start),
            "state_id": self.state_id
        }

        return """
        INSERT INTO "{tablename}" (
          vhsnd_date_past_month, state_id, anm_mpw_present, asha_present, child_immu, anc_today,
          awc_id, month
        )(
        SELECT
        DISTINCT ON(awc_id, month) vhsnd_date_past_month, state_id,
         CASE WHEN(anm_mpw = 1) THEN TRUE  ELSE FALSE END as anm_mpw_present,
         CASE WHEN(asha_present = 1) THEN TRUE  ELSE FALSE END as asha_present,
         CASE WHEN(child_immu = 1) THEN TRUE  ELSE FALSE END as child_immu,
         CASE WHEN(anc_today = 1) THEN TRUE  ELSE FALSE END as anc_today,
         awc_id, month
          FROM "{ucr_tablename}"
          WHERE vhsnd_date_past_month >= %(start_date)s AND
           vhsnd_date_past_month < %(end_date)s AND state_id = %(state_id)s
           ORDER BY awc_id, month, submitted_on
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename,
        ), query_params
