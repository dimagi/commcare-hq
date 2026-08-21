import os

from django.core.management.base import BaseCommand

from django.db import connections, transaction

from corehq.sql_db.connections import get_icds_ucr_citus_db_alias


@transaction.atomic
def _run_custom_sql_script(command):
    db_alias = get_icds_ucr_citus_db_alias()
    if not db_alias:
        return

    with connections[db_alias].cursor() as cursor:
        cursor.execute(command)


class Command(BaseCommand):

    def handle(self, *args, **options):

        thr_path = os.path.join(os.path.dirname(__file__), 'sql_scripts',
                                'build_thr_child_table.sql')

        print("RUNNING THR TABLE")
        with open(thr_path, "r", encoding='utf-8') as sql_file:
            sql_to_execute = sql_file.read()
            _run_custom_sql_script(sql_to_execute)
