from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from django.utils.functional import cached_property

from dateutil.relativedelta import relativedelta

from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class InactiveAwwsAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'inactive-awws'
    ucr_data_source_id = 'static-usage_forms'

    def __init__(self, last_sync):
        self.last_sync = last_sync

    def aggregate(self, cursor):
        missing_location_query = self.missing_location_query()
        aggregation_query, agg_params = self.aggregate_query()

        cursor.execute(missing_location_query)
        cursor.execute(aggregation_query, agg_params)

    @cached_property
    def aggregate_parent_table(self):
        from custom.icds_reports.models import AggregateInactiveAWW
        return AggregateInactiveAWW._meta.db_table

    def data_from_ucr_query(self):
        return """
            SELECT DISTINCT awc_id as awc_id,
                FIRST_VALUE(form_date) OVER forms as first_submission,
                LAST_VALUE(form_date) OVER forms as last_submission
            FROM "{ucr_tablename}"
            WHERE inserted_at >= %(last_sync)s AND form_date > %(six_months_ago) AND form_date <= %(now)s
            WINDOW forms AS (
              PARTITION BY awc_id
              ORDER BY form_date ASC RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
        """.format(
            ucr_tablename=self.ucr_tablename,
        ), {
            "last_sync": self.last_sync,
            "now": datetime.datetime.utcnow(),
            "six_months_ago": datetime.datetime.utcnow() - relativedelta(months=6),
        }

    def missing_location_query(self):
        return """
        INSERT INTO "{table_name}" (
            awc_id, awc_name, awc_site_code, supervisor_id, supervisor_name,
            block_id, block_name, district_id, district_name, state_id, state_name
        ) (
            SELECT
                loc.doc_id as awc_id,
                loc.awc_name as awc_name,
                'awc' || loc.awc_site_code as awc_site_code,
                loc.supervisor_id as supervisor_id,
                loc.supervisor_name as supervisor_name,
                loc.block_id as block_id,
                loc.block_name as block_name,
                loc.district_id as district_id,
                loc.district_name as district_name,
                loc.state_id as state_id,
                loc.state_name as state_name
            FROM "{awc_location_table_name}" loc
            WHERE loc.doc_id not in (
              SELECT aww.awc_id FROM "{table_name}" aww
            ) and loc.doc_id != 'All'
        )
        """.format(
            table_name=self.aggregate_parent_table,
            awc_location_table_name='awc_location'
        )

    def aggregate_query(self):
        ucr_query, params = self.data_from_ucr_query()
        return """
            UPDATE "{table_name}" AS agg_table SET
                first_submission = LEAST(agg_table.first_submission, ut.first_submission),
                last_submission = GREATEST(agg_table.last_submission, ut.last_submission)
            FROM (
              SELECT
                loc.doc_id as awc_id,
                ucr.first_submission as first_submission,
                ucr.last_submission as last_submission
              FROM ({ucr_table_query}) ucr
              JOIN "{awc_location_table_name}" loc
              ON ucr.awc_id = loc.doc_id
            ) ut
            WHERE agg_table.awc_id = ut.awc_id
        """.format(
            table_name=self.aggregate_parent_table,
            ucr_table_query=ucr_query,
            awc_location_table_name='awc_location',
        ), params
