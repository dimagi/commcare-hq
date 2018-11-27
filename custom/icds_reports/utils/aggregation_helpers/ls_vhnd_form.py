from __future__ import absolute_import
from __future__ import unicode_literals

from dateutil.relativedelta import relativedelta
from custom.icds_reports.const import AGG_LS_VHND_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter
import hashlib


class LSVhndFormAggHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-ls_vhnd_form'
    aggregate_parent_table = AGG_LS_VHND_TABLE
    aggregate_child_table_prefix = 'icds_db_ls_vhnd_form_'

    def __init__(self, month):
        self.month = month

    def drop_table_if_exists(self, agg_level):
        return """
        DROP TABLE IF EXISTS "{table_name}"
        """.format(table_name=self.self.generate_child_tablename(self.month))

    def create_table_query(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        tablename = self.generate_child_tablename(month)

        return """
        CREATE TABLE IF NOT EXISTS "{child_tablename}" (
            CHECK (month = %(month_string)s,
            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
        ) INHERITS ("{parent_tablename}")
        """.format(
            parent_tablename=self.aggregate_parent_table,
            child_tablename=tablename,
        ), {
            "month_string": month_string
        }

    def generate_child_tablename(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        hash_for_table = hashlib.md5((month_string).encode('utf-8')).hexdigest()[8:]
        return self.aggregate_child_table_prefix + hash_for_table

    def aggregate_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        query_params = {
            "month": month_formatter(month),
        }

        return """
        INSERT INTO "{tablename}" (
        state_id, supervisor_id, month, vhnd_observed
        ) (
             SELECT 
                state_id,
                location_id as supervisor_id,
                %(month)s::DATE AS month,
                count(*) as vhnd_observed
                FROM "{ucr_tablename}"
                WHERE vhnd_date > %(start_date)s AND vhnd_date < %(end_date)s
                GROUP BY location_id
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params
