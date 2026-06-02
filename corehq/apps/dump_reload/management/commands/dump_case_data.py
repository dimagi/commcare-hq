import os
from datetime import datetime
from zipfile import ZipFile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.form_processor.models import CommCareCase


class Command(BaseCommand):
    help = "Dump all case data, per case type per shard in csv files"

    def add_arguments(self, parser):
        parser.add_argument('--domain')
        parser.add_argument('--case_type')
        parser.add_argument('--db_conn', choices=settings.DATABASES)

    def ensure_params(self, for_domain, for_case_type, for_db_conn):
        if for_case_type:
            available_case_types = (CommCareCase.objects.using(for_db_conn).
                                    values_list('type', flat=True).distinct())
            if for_case_type not in available_case_types:
                raise CommandError(f"Unexpected case type {for_case_type} passed. "
                                   f"Should be from the following: {available_case_types}")

        if for_domain:
            available_domains = (CommCareCase.objects.using(for_db_conn).
                                 values_list('domain', flat=True).distinct())
            if for_domain not in available_domains:
                raise CommandError(f"Domain name {for_domain} not found for any case in db {for_db_conn}")

    def handle(self, *args, **options):
        for_domain = options.get('domain')
        for_case_type = options.get('case_type')
        for_db_conn = options.get('db_conn')

        if for_db_conn:
            self.ensure_params(for_domain, for_case_type, for_db_conn)
            dbs = [for_db_conn]
        else:
            dbs = settings.DATABASES

        for db in dbs:
            where_clause = "WHERE "
            db_conn = connections[db]
            if 'form_processor_commcarecasesql' in db_conn.introspection.table_names():
                if for_domain:
                    # ensure domain passed present for this db, if not just ignore it with a warning message
                    available_domains = (CommCareCase.objects.using(db).
                                         values_list('domain', flat=True).distinct())
                    if for_domain not in available_domains:
                        print(f"Domain name {for_domain} not found for any case in db {db}")
                        continue
                    where_clause += f"domain='{for_domain}' and "

                # ensure case type passed present for this db, if not just ignore it with a warning message
                available_case_types = (CommCareCase.objects.using(db).
                                        values_list('type', flat=True).distinct())
                if for_case_type and for_case_type not in available_case_types:
                    print(f"Ignoring Unexpected case type {for_case_type} passed."
                          f"Should be from the following: {available_case_types}")
                    continue
                if for_case_type:
                    case_types = [for_case_type]
                else:
                    case_types = available_case_types
                for case_type in case_types:
                    file_name = f"{case_type}_{db}_{datetime.utcnow().strftime(DATETIME_FORMAT)}.csv"
                    with open(file_name, "w", encoding='utf-8') as output:
                        c = db_conn.cursor()
                        _where_clause = where_clause + f"type='{case_type}' "
                        copy_query = ("copy (SELECT * FROM form_processor_commcarecasesql "
                                      f"{_where_clause})")
                        print("Query Being Run:")
                        print(copy_query)
                        c.copy_expert(
                            f"{copy_query} TO STDOUT DELIMITER ',' CSV HEADER;", output)
                    with ZipFile(file_name + '.zip', 'w') as zip_file:
                        zip_file.write(file_name, file_name)
                        os.remove(file_name)
            else:
                print(f"Ignoring {db}. It does not have the table form_processor_commcarecasesql")
