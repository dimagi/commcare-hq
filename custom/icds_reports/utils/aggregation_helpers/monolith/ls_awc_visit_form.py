from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_LS_AWC_VISIT_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class LSAwcMgtFormAggHelper(BaseICDSAggregationHelper):
    helper_key = 'ls-awc-mgt-form'
    ucr_data_source_id = 'static-awc_mgt_forms'
    aggregate_parent_table = AGG_LS_AWC_VISIT_TABLE
    aggregate_child_table_prefix = 'icds_db_ls_awc_mgt_form_'

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_param = self.aggregate_query()
        cursor.execute(drop_query)
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_param)

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
        INSERT INTO "{tablename}" (
        state_id, supervisor_id, month, awc_visits
        ) (
            SELECT
            state_id,
            location_id as supervisor_id,
            %(start_date)s::DATE AS month,
            count(*) as awc_visits
                FROM "{ucr_tablename}"
                WHERE submitted_on >= %(start_date)s AND  submitted_on < %(end_date)s
                AND location_entered is not null and location_entered <> ''
                AND state_id=%(state_id)s
                GROUP BY state_id,location_id
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params
