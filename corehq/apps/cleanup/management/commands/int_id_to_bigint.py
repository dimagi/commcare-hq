from __future__ import absolute_import
from __future__ import print_function

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from corehq.form_processor.utils.sql import fetchone_as_namedtuple
from corehq.util.django_migrations import add_if_not_exists_raw
from corehq.util.log import with_progress_bar


def confirm(table_name):
    return raw_input(
        u"""
        Are you sure you want to modify the {} table? [y/N]
        """.format(table_name)
    ) == 'y'


def update_new_id(db_name, table_name, start, end):
    with connections[db_name].cursor() as cursor:
        cursor.execute(
            "BEGIN; UPDATE {} SET new_id = id WHERE id BETWEEN %s AND %s; COMMIT;".format(table_name),
            [start, end]
        )


def get_min_max_id(db_name, table_name):
    with connections[db_name].cursor() as cursor:
        cursor.execute("SELECT min(id) AS min_id, max(id) AS max_id FROM {}".format(table_name))
        result = fetchone_as_namedtuple(cursor)
    return result.min_id, result.max_id


def add_new_id_column(db_name, table_name):

    with connections[db_name].cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (SELECT 1
            FROM information_schema.columns
            WHERE table_name=%s AND column_name=%s);
        """, [table_name, 'new_id'])
        exists = cursor.fetchone()[0]

        if not exists:
            print("Adding 'new_id' column to table %s" % table_name)
            cursor.execute("""ALTER TABLE {} ADD COLUMN new_id BIGINT""".format(table_name))
        else:
            print("'new_id' column already exists for table %s" % table_name)


def commit(db_name, table_name):
    print('Making final changes to table')
    with connections[db_name].cursor() as cursor:
        cursor.execute("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = %s AND constraint_type = 'PRIMARY KEY'
            """, [table_name])
        pk_index_name = cursor.fetchone()[0]

        new_index_name = '%s_new' % pk_index_name
        cursor.execute(add_if_not_exists_raw(
            "CREATE UNIQUE INDEX {} on {}(new_id)".format(new_index_name, table_name),
            new_index_name
        ))

    with connections[db_name].cursor() as cursor:
        cursor.execute('begin')
        id_seq_name = '%s_id_seq' % table_name
        cursor.execute(
            "ALTER TABLE {} ALTER COLUMN new_id SET DEFAULT nextval(%s::regclass)".format(
                table_name
            ), [id_seq_name]
        )
        cursor.execute("UPDATE {} SET new_id = id WHERE new_id IS NULL".format(table_name))
        cursor.execute("ALTER TABLE {} DROP CONSTRAINT {}".format(table_name, pk_index_name))
        cursor.execute("ALTER SEQUENCE {} OWNED BY {}.new_id".format(id_seq_name, table_name))
        cursor.execute("ALTER INDEX {} RENAME TO {}".format(new_index_name, pk_index_name))
        cursor.execute("ALTER TABLE {} ADD CONSTRAINT {} PRIMARY KEY USING INDEX {}".format(
            table_name, pk_index_name, pk_index_name
        ))
        cursor.execute("ALTER TABLE {} DROP COLUMN id".format(table_name))
        cursor.execute("ALTER TABLE {} RENAME COLUMN new_id to id".format(table_name))
        cursor.execute('commit')


class Command(BaseCommand):
    help = 'Convert int ID column to bigint'

    def add_arguments(self, parser):
        parser.add_argument('db_name')
        parser.add_argument('model_name')

    def handle(self, db_name, model_name, **options):
        model = apps.get_model(*model_name.split('.'))
        table_name = model._meta.db_table

        if not confirm(table_name):
            raise CommandError('Aborting.')

        add_new_id_column(db_name, table_name)

        min_id, max_id = get_min_max_id(db_name, table_name)
        if min_id and max_id:
            batch_size = 10000
            batches = [(x, x + batch_size) for x in range(min_id, max_id, 10000 + 1)]
            last_end = None
            for start, end in with_progress_bar(batches):
                update_new_id(db_name, table_name, start, end)
                last_end = end

            min_id, max_id = get_min_max_id(db_name, table_name)
            update_new_id(db_name, table_name, last_end + 1, max_id)

        commit(db_name, table_name)
