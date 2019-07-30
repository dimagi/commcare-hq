from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from custom.icds_reports.const import AGG_THR_V2_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class THRFormV2AggDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'thr-form-v2'
    ucr_data_source_id = 'static-thr_forms_v2'
    tablename = AGG_THR_V2_TABLE

    def aggregate(self, cursor):
        drop_query, drop_params = self.drop_table_query()
        agg_query, agg_params = self.aggregation_query()

        cursor.execute(drop_query, drop_params)
        cursor.execute(agg_query, agg_params)

    def drop_table_query(self):
        return (
            'DELETE FROM "{}" WHERE month=%(month)s AND state_id = %(state)s'.format(self.tablename),
            {'month': month_formatter(self.month), 'state': self.state_id}
        )

    def aggregation_query(self):
        month = self.month.replace(day=1)
        next_month_start = self.month + relativedelta(months=1)

        query_params = {
            "state_id": self.state_id,
            "start_date": month_formatter(month),
            "end_date": month_formatter(next_month_start)
        }

        return """
        DROP TABLE IF EXISTS "temp_thr";
        CREATE TEMPORARY TABLE "temp_thr" AS
            SELECT
                state_id,
                supervisor_id,
                awc_id,
                COUNT(*) FILTER (WHERE photo_thr_packets_distributed is not null) as thr_distribution_image_count,
                %(start_date)s::DATE AS month
                FROM "{ucr_tablename}"
                WHERE submitted_on >= %(start_date)s AND submitted_on < %(end_date)s
                    AND state_id=%(state_id)s
                GROUP BY state_id, supervisor_id, awc_id;
        INSERT INTO "{tablename}" (
            state_id, supervisor_id, awc_id, thr_distribution_image_count, month
        )
        SELECT * from "temp_thr";
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=self.tablename
        ), query_params
