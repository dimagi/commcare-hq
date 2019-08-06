from __future__ import absolute_import
from __future__ import unicode_literals

import io
import json

import csv342 as csv
from six.moves import map, range

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import (
    StaticDataSourceConfiguration,
    get_datasource_config,
)
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AWC_LOCATION_TABLE_ID, AWW_USER_TABLE_ID
from custom.icds_reports.utils.aggregation_helpers.monolith.base import BaseICDSAggregationHelper


class LocationAggregationHelper(BaseICDSAggregationHelper):
    helper_key = 'location'
    base_tablename = 'awc_location'
    local_tablename = 'awc_location_local'

    ucr_aww_table = AWW_USER_TABLE_ID

    def __init__(self):
        pass

    @property
    def _table_column_names(self):
        return (
            'doc_id', 'awc_name', 'awc_site_code', 'awc_is_test',
            'supervisor_id', 'supervisor_name', 'supervisor_site_code', 'supervisor_is_test',
            'block_id', 'block_name', 'block_site_code', 'block_is_test', 'block_map_location_name',
            'district_id', 'district_name', 'district_site_code', 'district_is_test', 'district_map_location_name',
            'state_id', 'state_name', 'state_site_code', 'state_is_test', 'state_map_location_name',
            'aggregation_level',
        )

    def generate_csv(self):
        domain_locations = SQLLocation.objects.filter(domain=self.domain).values(
            'pk', 'parent_id', 'metadata', 'name', 'location_id', 'location_type__code')
        locations_by_pk = {
            loc['pk']: loc
            for loc in domain_locations
        }
        locations = [loc for loc in domain_locations if loc['location_type__code'] == 'awc']

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self._table_column_names, delimiter='\t', newline='\n')
        writer.writeheader()

        for location in locations:
            metadata = json.loads(location['metadata'])
            loc = {
                'aggregation_level': 5,
                'doc_id': location['location_id'],
                'awc_name': location['name'],
                'awc_site_code': location['location_type__code'],
                'awc_is_test': 1 if metadata.get('is_test_location') == 'test' else 0,
            }

            current_location = location
            while current_location['parent_id']:
                current_location = locations_by_pk[current_location['parent_id']]
                loc_type = current_location['location_type__code']
                loc.update({
                    '{}_id'.format(loc_type): current_location['location_id'],
                    '{}_name'.format(loc_type): current_location['name'],
                    '{}_site_code'.format(loc_type): current_location['location_type__code'],
                    '{}_is_test'.format(loc_type): 1 if metadata.get('is_test_location') == 'test' else 0,
                })
                if loc_type in ('block', 'district', 'state'):
                    loc.update({
                        '{}_map_location_name'.format(loc_type): metadata.get('map_location_name'),
                    })

            writer.writerow(loc)

        output.seek(0)
        return output

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
    def ucr_aww_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ucr_aww_table)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def drop_table_query(self):
        return """
            DELETE FROM "{tablename}";
        """.format(tablename=self.base_tablename)

    def aggregate_to_temporary_table(self, cursor, csv_file):
        columns = csv_file.readline().split('\t')
        # double cursor to get psycopg2 cursor from django cursor
        cursor.cursor.copy_from(csv_file, 'temp_awc_location', columns=columns)

    def create_temporary_table_query(self):
        return "CREATE TABLE \"temp_awc_location\" (LIKE \"{tablename}\" INCLUDING INDEXES)".format(
            tablename=self.base_tablename,
        )

    def move_data_to_real_table(self):
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
            ('aggregation_level', 'aggregation_level'),
            ('block_map_location_name', 'block_map_location_name'),
            ('district_map_location_name', 'district_map_location_name'),
            ('state_map_location_name', 'state_map_location_name'),
            ('aww_name', 'aww_name'),
            ('contact_phone_number', 'contact_phone_number'),
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
              FROM "temp_awc_location"
            )
        """.format(
            tablename=self.base_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
        )

    def aww_query(self):
        return """
            UPDATE temp_awc_location" awc_loc SET
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
            INSERT INTO "temp_awc_location" (
              {columns}
            ) (
              SELECT
                {calculations}
              FROM "temp_awc_location"
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
