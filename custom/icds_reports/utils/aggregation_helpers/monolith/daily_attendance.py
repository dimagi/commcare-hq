from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import DAILY_FEEDING_TABLE_ID
from custom.icds_reports.utils.aggregation_helpers import date_to_string, \
    transform_day_to_month
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class DailyAttendanceAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'daily-attendance'
    base_tablename = 'daily_attendance'
    ucr_daily_attendance_table = DAILY_FEEDING_TABLE_ID

    def __init__(self, month):
        self.month = transform_day_to_month(month)

    def aggregate(self, cursor):
        curr_month_query, curr_month_params = self.create_table_query()
        agg_query, agg_params = self.aggregate_query()
        indexes_query = self.indexes()

        cursor.execute(self.drop_table_query())
        cursor.execute(curr_month_query, curr_month_params)
        cursor.execute(agg_query, agg_params)
        cursor.execute(indexes_query)

    @property
    def tablename(self):
        return "{}_{}".format(self.base_tablename, date_to_string(self.month))

    def create_table_query(self):
        return """
            CREATE TABLE IF NOT EXISTS "{tablename}" (
            CHECK (month = %(table_date)s)) INHERITS ("{parent_tablename}")
        """.format(
            tablename=self.tablename,
            parent_tablename=self.base_tablename,
        ), {
            "table_date": date_to_string(self.month)
        }

    def drop_table_query(self):
        return 'DROP TABLE IF EXISTS "{}"'.format(self.tablename)

    @property
    def ucr_daily_attendance_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ucr_daily_attendance_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def aggregate_query(self):
        return """
            INSERT INTO "{tablename}" (
              SELECT DISTINCT ON (awc_id, submitted_on)
                doc_id as doc_id,
                awc_id as awc_id,
                month as month,
                submitted_on as pse_date,
                awc_open_count as awc_open_count,
                1 as count,
                eligible_children as eligible_children,
                attended_children as attended_children,
                attended_children_percent as attended_children_percent,
                form_location as form_location,
                form_location_lat as form_location_lat,
                form_location_long as form_location_long,
                image_name as image_name,
                pse_conducted as pse_conducted,
                supervisor_id as supervisor_id
              FROM "{ucr_daily_attendance_tablename}"
              WHERE month = %(start_month)s and (awc_open_count=1 OR awc_not_open = 1)
              ORDER BY awc_id, submitted_on, inserted_at DESC
            )
        """.format(
            tablename=self.tablename,
            ucr_daily_attendance_tablename=self.ucr_daily_attendance_tablename
        ), {
            "start_month": date_to_string(self.month),
        }

    def indexes(self):
        return """
            CREATE INDEX "{tablename}_indx1" ON "{tablename}" (awc_id)
        """.format(
            tablename=self.tablename
        )
