from __future__ import absolute_import
from __future__ import unicode_literals

from six.moves import map

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AWC_LOCATION_TABLE_ID, AWW_USER_TABLE_ID
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper
from six.moves import range


class LocationAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'location'
    base_tablename = 'awc_location'
    local_tablename = 'awc_location_local'

    ucr_location_table = AWC_LOCATION_TABLE_ID
    ucr_aww_table = AWW_USER_TABLE_ID

    def __init__(self):
        pass

    def aggregate(self, cursor):
        drop_table_query = self.drop_table_query()
        agg_query = self.aggregate_query()
        aww_query = self.aww_query()
        rollup_queries = [self.rollup_query(i) for i in range(4, 0, -1)]

        cursor.execute(drop_table_query)
        cursor.execute(agg_query)
        cursor.execute(aww_query)
        for rollup_query in rollup_queries:
            cursor.execute(rollup_query)
        cursor.execute(self.create_local_table())

    @property
    def ucr_location_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ucr_location_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    @property
    def ucr_aww_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ucr_aww_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def drop_table_query(self):
        return """
            DELETE FROM "{tablename}";
        """.format(tablename=self.base_tablename)

    def aggregate_query(self):
        columns = (
            ('doc_id', 'doc_id'),
            ('awc_name', 'awc_name'),
            ('awc_site_code', 'awc_site_code'),
            ('supervisor_id', 'supervisor_id'),
            ('supervisor_name', 'supervisor_name'),
            ('supervisor_site_code', 'supervisor_site_code'),
            ('block_id', 'block_id'),
            ('block_name', 'block_name'),
            ('block_site_code', 'block_site_code'),
            ('district_id', 'district_id'),
            ('district_name', 'district_name'),
            ('district_site_code', 'district_site_code'),
            ('state_id', 'state_id'),
            ('state_name', 'state_name'),
            ('state_site_code', 'state_site_code'),
            ('aggregation_level', '5'),
            ('block_map_location_name', 'block_map_location_name'),
            ('district_map_location_name', 'district_map_location_name'),
            ('state_map_location_name', 'state_map_location_name'),
            ('aww_name', 'NULL'),
            ('contact_phone_number', 'NULL'),
            ('state_is_test', 'state_is_test'),
            ('district_is_test', 'district_is_test'),
            ('block_is_test', 'block_is_test'),
            ('supervisor_is_test', 'supervisor_is_test'),
            ('awc_is_test', 'awc_is_test')
        )

        return """
            INSERT INTO "{tablename}" (
              {columns}
            ) (
              SELECT
                {calculations}
              FROM "{ucr_location_tablename}"
            )
        """.format(
            tablename=self.base_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            ucr_location_tablename=self.ucr_location_tablename
        )

    def aww_query(self):
        return """
            UPDATE "{tablename}" awc_loc SET
              aww_name = ut.aww_name,
              contact_phone_number = ut.contact_phone_number
            FROM (
              SELECT
                commcare_location_id,
                aww_name,
                contact_phone_number
              FROM "{ucr_aww_tablename}"
            ) ut
            WHERE ut.commcare_location_id = awc_loc.doc_id
        """.format(
            tablename=self.base_tablename,
            ucr_aww_tablename=self.ucr_aww_tablename
        )

    def rollup_query(self, aggregation_level):
        columns = (
            ('doc_id', lambda col: col if aggregation_level > 4 else "'All'"),
            ('awc_name', lambda col: col if aggregation_level > 4 else "NULL"),
            ('awc_site_code', lambda col: col if aggregation_level > 4 else "'All'"),
            ('supervisor_id', lambda col: col if aggregation_level > 3 else "'All'"),
            ('supervisor_name', lambda col: col if aggregation_level > 3 else "NULL"),
            ('supervisor_site_code', lambda col: col if aggregation_level > 3 else "'All'"),
            ('block_id', lambda col: col if aggregation_level > 2 else "'All'"),
            ('block_name', lambda col: col if aggregation_level > 2 else "NULL"),
            ('block_site_code', lambda col: col if aggregation_level > 2 else "'All'"),
            ('district_id', lambda col: col if aggregation_level > 1 else "'All'"),
            ('district_name', lambda col: col if aggregation_level > 1 else "NULL"),
            ('district_site_code', lambda col: col if aggregation_level > 1 else "'All'"),
            ('state_id', 'state_id'),
            ('state_name', 'state_name'),
            ('state_site_code', 'state_site_code'),
            ('aggregation_level', '{}'.format(aggregation_level)),
            ('block_map_location_name', lambda col: col if aggregation_level > 2 else "'All'"),
            ('district_map_location_name', lambda col: col if aggregation_level > 1 else "'All'"),
            ('state_map_location_name', 'state_map_location_name'),
            ('aww_name', 'NULL'),
            ('contact_phone_number', 'NULL'),
            ('state_is_test', 'MAX(state_is_test)'),
            (
                'district_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 1 else "0"
            ),
            (
                'block_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 2 else "0"
            ),
            (
                'supervisor_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 3 else "0"
            ),
            (
                'awc_is_test',
                lambda col: 'MAX({column})'.format(column=col) if aggregation_level > 4 else "0"
            )
        )

        def _transform_column(column_tuple):
            column = column_tuple[0]

            agg_col = column_tuple[1]
            if callable(agg_col):
                return (column, agg_col(column))
            return column_tuple

        columns = list(map(_transform_column, columns))

        end_text_column = ["id", "name", "site_code", "map_location_name"]

        group_by = ["state_{}".format(name) for name in end_text_column]
        if aggregation_level > 1:
            group_by.extend(["district_{}".format(name) for name in end_text_column])
        if aggregation_level > 2:
            group_by.extend(["block_{}".format(name) for name in end_text_column])
        if aggregation_level > 3:
            group_by.extend(
                ["supervisor_{}".format(name) for name in end_text_column if name is not "map_location_name"]
            )

        return """
            INSERT INTO "{tablename}" (
              {columns}
            ) (
              SELECT
                {calculations}
              FROM "{tablename}"
              GROUP BY {group_by}
            )
        """.format(
            tablename=self.base_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by)
        )

    def create_local_table(self):
        return """
        DELETE FROM "{local_tablename}";
        INSERT INTO "{local_tablename}" SELECT * FROM "{tablename}";
        """.format(
            tablename=self.base_tablename,
            local_tablename=self.local_tablename
        )
