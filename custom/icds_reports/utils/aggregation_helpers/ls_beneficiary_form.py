from __future__ import absolute_import
from __future__ import unicode_literals

from custom.icds_reports.const import AGG_LS_VHND_TABLE
from custom.icds_reports.utils.aggregation_helpers import BaseICDSAggregationHelper, month_formatter
import hashlib


class LSBeneficiaryFormAggHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-ls_home_visit_forms_filled'
    aggregate_parent_table = AGG_LS_VHND_TABLE
    aggregate_child_table_prefix = 'icds_db_ls_beneficiary_form_'

    def __init__(self, month):
        self.month = month

    def drop_table_if_exists(self):
        return """
        DROP TABLE IF EXISTS "{table_name}"
        """.format(table_name=self.generate_child_tablename(self.month))

    def create_table_query(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        tablename = self.generate_child_tablename(month)

        return """
        CREATE TABLE IF NOT EXISTS "{child_tablename}" (
            CHECK (month = %(month_string)s)
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

        query_params = {
            "month": month_formatter(month),
        }

        return """
        INSERT INTO "{tablename}" (
        state_id, supervisor_id, month, beneficiary_vists
        ) (
             SELECT
                state_id,
                location_id as supervisor_id,
                %(month)s::DATE AS month,
                count(*) as beneficiary_vists
                FROM "{ls_home_visit_ucr}"
                WHERE submitted_on > %(start_date)s AND  submitted_on< %(end_date)s
                AND visit_type_entered is not null AND visit_type_entered <> ''
                GROUP BY location_id, month
        )
        """.format(
            ucr_tablename=self.ucr_tablename,
            tablename=tablename
        ), query_params
