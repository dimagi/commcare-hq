from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_GOV_VHND_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    StateBasedAggregationPartitionedHelper,
)


class GovVhndFormAggDistributedHelper(StateBasedAggregationPartitionedHelper):
    helper_key = 'gov-vhnd-form'
    ucr_data_source_id = 'static-gov_vhnd_form'
    aggregate_parent_table = AGG_GOV_VHND_TABLE
    aggregate_child_table_prefix = 'icds_db_gov_vhnd_form_'

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "start_date": month_formatter(month),
            "end_date": month_formatter(next_month_start)
        }

        return """
        INSERT INTO "{tablename}" (
          vhsnd_date_past_month, anm_mpw_present, asha_present, child_immu, anc_today,
          awc_id, month
        )(
        SELECT
          vhsnd_date_past_month, anm_mpw_present, asha_present, child_immu, anc_today,
          awc_id, month
          FROM "{ucr_tablename}"
          WHERE vhnd_date >= %(start_date)s AND vhnd_date < %(end_date)s
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename,
        ), query_params
