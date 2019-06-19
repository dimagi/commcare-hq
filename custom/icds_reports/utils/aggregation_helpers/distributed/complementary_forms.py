from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta

from custom.icds_reports.const import AGG_COMP_FEEDING_TABLE
from custom.icds_reports.utils.aggregation_helpers import month_formatter
from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper


class ComplementaryFormsAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'complementary-forms'
    ucr_data_source_id = 'static-complementary_feeding_forms'
    tablename = AGG_COMP_FEEDING_TABLE

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

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT DISTINCT child_health_case_id AS case_id,
        %(current_month_start)s::date AS month,
        supervisor_id AS supervisor_id,
        LAST_VALUE(timeend) OVER w AS latest_time_end,
        MAX(play_comp_feeding_vid) OVER w AS play_comp_feeding_vid,
        MAX(comp_feeding) OVER w AS comp_feeding_ever,
        MAX(demo_comp_feeding) OVER w AS demo_comp_feeding,
        MAX(counselled_pediatric_ifa) OVER w AS counselled_pediatric_ifa,
        LAST_VALUE(comp_feeding) OVER w AS comp_feeding_latest,
        LAST_VALUE(diet_diversity) OVER w AS diet_diversity,
        LAST_VALUE(diet_quantity) OVER w AS diet_quantity,
        LAST_VALUE(hand_wash) OVER w AS hand_wash
        FROM "{ucr_tablename}"
        WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND state_id = %(state_id)s
        WINDOW w AS (
            PARTITION BY supervisor_id, child_health_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        """.format(ucr_tablename=self.ucr_tablename), {
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "state_id": self.state_id
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        query_params = {
            "month": month_formatter(month),
            "previous_month": month_formatter(month - relativedelta(months=1)),
            "state_id": self.state_id
        }

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params.update(ucr_query_params)

        # GREATEST calculations are for when we want to know if a thing has
        # ever happened to a case.
        # CASE WHEN calculations are for when we want to know if a case
        # happened during the last form for this case. We must use CASE WHEN
        # and not COALESCE as when questions are skipped they will be NULL
        # and we want NULL in the aggregate table
        return """
        INSERT INTO "{tablename}" (
          state_id, supervisor_id, month, case_id, latest_time_end_processed, comp_feeding_ever,
          demo_comp_feeding, counselled_pediatric_ifa, play_comp_feeding_vid,
          comp_feeding_latest, diet_diversity, diet_quantity, hand_wash
        ) (
          SELECT
            %(state_id)s AS state_id,
            COALESCE(ucr.supervisor_id, prev_month.supervisor_id) AS supervisor_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
            GREATEST(ucr.comp_feeding_ever, prev_month.comp_feeding_ever) AS comp_feeding_ever,
            GREATEST(ucr.demo_comp_feeding, prev_month.demo_comp_feeding) AS demo_comp_feeding,
            GREATEST(ucr.counselled_pediatric_ifa, prev_month.counselled_pediatric_ifa) AS counselled_pediatric_ifa,
            GREATEST(ucr.play_comp_feeding_vid, prev_month.play_comp_feeding_vid) AS play_comp_feeding_vid,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.comp_feeding_latest ELSE prev_month.comp_feeding_latest
            END AS comp_feeding_latest,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.diet_diversity ELSE prev_month.diet_diversity
            END AS diet_diversity,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.diet_quantity ELSE prev_month.diet_quantity
            END AS diet_quantity,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.hand_wash ELSE prev_month.hand_wash
            END AS hand_wash
          FROM ({ucr_table_query}) ucr
          FULL OUTER JOIN "{tablename}" prev_month
          ON ucr.case_id = prev_month.case_id AND ucr.supervisor_id = prev_month.supervisor_id
            AND ucr.month = prev_month.month + INTERVAL '1 month'
          WHERE coalesce(ucr.month, %(month)s) = %(month)s
            AND coalesce(prev_month.month, %(previous_month)s) = %(previous_month)s
            AND coalesce(prev_month.state_id, %(state_id)s) = %(state_id)s
        )
        """.format(
            tablename=self.tablename,
            ucr_table_query=ucr_query
        ), query_params
