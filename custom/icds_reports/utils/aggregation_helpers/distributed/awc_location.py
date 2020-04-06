import csv
import io
import json

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import (
    StaticDataSourceConfiguration,
    get_datasource_config,
)
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import AWW_USER_TABLE_ID
from custom.icds_reports.utils.aggregation_helpers.distributed.base import (
    BaseICDSAggregationDistributedHelper,
)


class LocationAggregationDistributedHelper(BaseICDSAggregationDistributedHelper):
    helper_key = 'location'
    base_tablename = 'awc_location'
    local_tablename = 'awc_location_local'
    temporary_tablename = 'tmp_awc_location_local'

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
        domain_locations = _get_all_locations_for_domain(self.domain)
        locations_by_pk = {
            loc['pk']: loc
            for loc in domain_locations
        }
        locations = [loc for loc in domain_locations if loc['location_type__code'] == 'awc']

        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=self._table_column_names,
            delimiter='\t', escapechar='\\', lineterminator='\n'
        )
        writer.writeheader()

        for location in locations:
            metadata = json.loads(location['metadata'])
            # We strip newlines from the names because in the dashboard the names
            # are displayed without newlines and it keeps the CSV import/export
            # logic simpler between python and postgres
            loc = {
                'aggregation_level': 5,
                'doc_id': location['location_id'],
                'awc_name': location['name'].replace("\n", ""),
                'awc_site_code': location['site_code'],
                'awc_is_test': 1 if metadata.get('is_test_location') == 'test' else 0,
            }

            current_location = location
            while current_location['parent_id']:
                current_location = locations_by_pk[current_location['parent_id']]
                loc_type = current_location['location_type__code']
                metadata = json.loads(current_location['metadata'])
                loc.update({
                    '{}_id'.format(loc_type): current_location['location_id'],
                    '{}_name'.format(loc_type): current_location['name'].replace("\n", ""),
                    '{}_site_code'.format(loc_type): current_location['site_code'],
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
        location_csv = self.generate_csv()

        cursor.execute(self.drop_temporary_table_query())
        cursor.execute(self.create_temporary_table_query())
        self.aggregate_to_temporary_table(cursor, location_csv)
        cursor.execute(self.aww_query())
        rollup_queries = [self.rollup_query(i) for i in range(4, 0, -1)]
        for rollup_query in rollup_queries:
            cursor.execute(rollup_query)

        cursor.execute(self.delete_old_locations())
        cursor.execute(self.move_data_to_local_table())
        cursor.execute(self.create_distributed_table())

    @property
    def ucr_aww_tablename(self):
        return get_table_name(self.domain, self.ucr_aww_table)

    def delete_old_locations(self):
        return "DELETE FROM \"{local_tablename}\"".format(local_tablename=self.local_tablename)

    def aggregate_to_temporary_table(self, cursor, csv_file):
        columns = csv_file.readline().replace('\t', ',')

        # using csv format to not consider `\` as special value
        query = "COPY {}({}) FROM STDIN DELIMITER '\t' CSV ".format(self.temporary_tablename,
                                                                    columns)

        # double cursor to get psycopg2 cursor from django cursor
        cursor.cursor.copy_expert(query, csv_file)

    def drop_temporary_table_query(self):
        return "DROP TABLE IF EXISTS \"{}\"".format(self.temporary_tablename)

    def create_temporary_table_query(self):
        return "CREATE TABLE \"{temporary_tablename}\" (LIKE \"{local_tablename}\" INCLUDING INDEXES)".format(
            local_tablename=self.local_tablename,
            temporary_tablename=self.temporary_tablename,
        )

    def move_data_to_local_table(self):
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
            ('awc_ward_1', 'awc_ward_1'),
            ('awc_ward_2', 'awc_ward_2'),
            ('awc_ward_3', 'awc_ward_3'),
            ('state_is_test', 'state_is_test'),
            ('district_is_test', 'district_is_test'),
            ('block_is_test', 'block_is_test'),
            ('supervisor_is_test', 'supervisor_is_test'),
            ('awc_is_test', 'awc_is_test')
        )

        return """
            INSERT INTO "{local_tablename}" (
              {columns}
            ) (
              SELECT
                {calculations}
              FROM "{temporary_tablename}"
            )
        """.format(
            local_tablename=self.local_tablename,
            temporary_tablename=self.temporary_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
        )

    def aww_query(self):
        return """
            UPDATE {temporary_tablename} awc_loc SET
              aww_name = ut.aww_name,
              contact_phone_number = ut.contact_phone_number,
              awc_ward_1 = ut.awc_ward_1,
              awc_ward_2 = ut.awc_ward_2,
              awc_ward_3 = ut.awc_ward_3
            FROM (
              SELECT
                commcare_location_id,
                aww_name,
                contact_phone_number,
                awc_ward_1,
                awc_ward_2,
                awc_ward_3
              FROM "{ucr_aww_tablename}"
            ) ut
            WHERE ut.commcare_location_id = awc_loc.doc_id
        """.format(
            temporary_tablename=self.temporary_tablename,
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
            ('awc_ward_1', 'NULL'),
            ('awc_ward_2', 'NULL'),
            ('awc_ward_3', 'NULL'),
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
            INSERT INTO "{temporary_tablename}" (
              {columns}
            ) (
              SELECT
                {calculations}
              FROM "{temporary_tablename}"
              GROUP BY {group_by}
            )
        """.format(
            temporary_tablename=self.temporary_tablename,
            columns=", ".join([col[0] for col in columns]),
            calculations=", ".join([col[1] for col in columns]),
            group_by=", ".join(group_by)
        )

    def create_distributed_table(self):
        return """
        DELETE FROM "{tablename}";
        INSERT INTO "{tablename}" SELECT * FROM "{local_tablename}";
        """.format(
            tablename=self.base_tablename,
            local_tablename=self.local_tablename
        )


def _get_all_locations_for_domain(domain):
    return (
        SQLLocation.objects
        .filter(domain=domain, is_archived=False)
        .values('pk', 'parent_id', 'metadata', 'name', 'location_id', 'location_type__code', 'site_code')
    )
