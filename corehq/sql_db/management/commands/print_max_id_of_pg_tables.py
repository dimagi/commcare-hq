from django.core.management.base import BaseCommand
from django.db import connections

from corehq.sql_db.util import get_db_aliases_for_partitioned_query



tables_with_id_query= """
    select t.table_name
    from information_schema.tables t
    inner join information_schema.columns c on c.table_name = t.table_name 
                                    and c.table_schema = t.table_schema
    where c.column_name = 'id'
        and c.data_type = 'integer'
        and c.column_default is not NULL
        and t.table_schema not in ('information_schema', 'pg_catalog')
    order by t.table_schema
    """


def get_tables_with_id_column(cursor):
    # returns list of tables which have an id column
    cursor.execute(tables_with_id_query)
    result = cursor.fetchall()
    return [t for (t,) in result]


class Command(BaseCommand):
    help = "Print max value of id column for each relevent table in given db"

    def add_arguments(self, parser):
        parser.add_argument(
            'dbname',
            help='Django db alias'
        )
        parser.add_argument(
            '--minval',
            type=int,
            dest='minval',
            help='print only tables where the max value is more than this provided minvalue'
        )

    def handle(self, **options):
        dbname = options['dbname']
        minval = options['minval']
        cursor = connections[dbname].cursor()
        tables = get_tables_with_id_column(cursor)
        select_statements = [
            '(SELECT max("id") FROM {})'.format(t)
            for t in tables
        ]
        query = " UNION ALL ".join(select_statements)
        cursor.execute(query)
        result = [r for (r,) in cursor.fetchall()]
        result = dict(zip(tables, result))
        print('table_name, max(id)')
        for table, max_id in result.items():
            if max_id and max_id > minval:
                print(table, ", ", max_id)
