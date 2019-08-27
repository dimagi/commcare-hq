
import os
from zipfile import ZipFile
from datetime import datetime
from django.db import connections
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.form_processor.models import CommCareCaseSQL


class Command(BaseCommand):
    help = "Dump all case data, per case type per shard in csv files"

    def add_arguments(self, parser):
        parser.add_argument('--domain')
        parser.add_argument('--case_type')
        parser.add_argument('--db_conn', choices=settings.DATABASES)

    def ensure_params(self, for_domain, for_case_type, for_db_conn):
        if for_case_type:
            available_case_types = (CommCareCaseSQL.objects.using(for_db_conn).
                                    values_list('type', flat=True).distinct())
            if for_case_type not in available_case_types:
                raise CommandError("Unexpected case type {for_case_type} passed. "
                                   "Should be from the following: {case_types}"
                                   .format(for_case_type=for_case_type, case_types=available_case_types))

        if for_domain:
            available_domains = (CommCareCaseSQL.objects.using(for_db_conn).
                                 values_list('domain', flat=True).distinct())
            if for_domain not in available_domains:
                raise CommandError("Domain name {for_domain} not found for any case in db {for_db_conn}".format(
                    for_domain=for_domain, for_db_conn=for_db_conn
                ))

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
                    available_domains = (CommCareCaseSQL.objects.using(db).
                                         values_list('domain', flat=True).distinct())
                    if for_domain not in available_domains:
                        print("Domain name {for_domain} not found for any case in db {for_db_conn}".format(
                            for_domain=for_domain,
                            for_db_conn=db
                        ))
                        continue
                    where_clause += "domain='{domain}' and ".format(domain=for_domain)

                # ensure case type passed present for this db, if not just ignore it with a warning message
                available_case_types = (CommCareCaseSQL.objects.using(db).
                                        values_list('type', flat=True).distinct())
                if for_case_type and for_case_type not in available_case_types:
                    print("Ignoring Unexpected case type {for_case_type} passed."
                          "Should be from the following: {case_types}"
                          .format(for_case_type=for_case_type, case_types=available_case_types))
                    continue
                if for_case_type:
                    case_types = [for_case_type]
                else:
                    case_types = available_case_types
                for case_type in case_types:
                    file_name = "{case_type}_{db_name}_{timestamp}.csv".format(
                        case_type=case_type, db_name=db,
                        timestamp=datetime.utcnow().strftime(DATETIME_FORMAT))
                    with open(file_name, "w", encoding='utf-8') as output:
                        c = db_conn.cursor()
                        _where_clause = where_clause + "type='{case_type}' ".format(case_type=case_type)
                        copy_query = "copy (SELECT * FROM form_processor_commcarecasesql " \
                                     "{where_clause})".format(where_clause=_where_clause)
                        print("Query Being Run:")
                        print(copy_query)
                        c.copy_expert(
                            "{query} TO STDOUT DELIMITER ',' CSV HEADER;".format(query=copy_query), output)
                    with ZipFile(file_name + '.zip', 'w') as zip_file:
                        zip_file.write(file_name, file_name)
                        os.remove(file_name)
            else:
                print("Ignoring {db}. It does not have the table form_processor_commcarecasesql".format(db=db))
