import os
import zipfile

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import connections

from custom.icds_reports.const import CUSTOM_DATA_PULLS


class Command(BaseCommand):
    help = "Dump data from a pre-defined query for ICDS data pull requests"

    def add_arguments(self, parser):
        parser.add_argument('name')
        parser.add_argument('db_alias', choices=settings.DATABASES)
        parser.add_argument('--month', help="format YYYY-MM-DD")
        parser.add_argument('--location_id')
        parser.add_argument('-s', '--skip_confirmation', action='store_true')
        parser.add_argument('-l', '--log_progress', action='store_true')

    def handle(self, name, db_alias, *arg, **options):
        generated_files = []
        month = options.get('month')
        location_id = options.get('location_id')
        skip_confirmation = options.get('skip_confirmation')
        log_progress = options.get('log_progress')
        if db_alias not in settings.DATABASES:
            raise CommandError("Unexpected db alias")
        if name in CUSTOM_DATA_PULLS:
            generated_files = self.run_via_class(name, db_alias, month, location_id, skip_confirmation,
                                                 log_progress)
        else:
            generated_files = self.run_via_sql_file(name, db_alias, month, location_id, skip_confirmation,
                                                    log_progress)
        if len(generated_files) > 1:
            zip_file_name = "%s-DataPull.zip" % name
            with zipfile.ZipFile(zip_file_name, mode='a') as z:
                for generated_file in generated_files:
                    z.write(generated_file)
                    os.remove(generated_file)
            return zip_file_name
        else:    
            return generated_files[0] if generated_files else None

    def run_via_class(self, slug, db_alias, month, location_id, skip_confirmation, log_progress):
        data_pull_class = CUSTOM_DATA_PULLS[slug]
        data_pull = data_pull_class(db_alias, month=month, location_id=location_id)
        if log_progress:
            self._log(data_pull.get_queries())
        if not skip_confirmation and self._get_confirmation():
            return data_pull.run()
        return []   

    def run_via_sql_file(self, sql_query_file_path, db_alias, month, location_id, skip_confirmation, log_progress):
        filepath = 'custom/icds_reports/data_pull/sql_queries/%s.sql' % sql_query_file_path
        with open(filepath) as _sql:
            sql = _sql.read()
            sql = sql.format(month=month, location_id=location_id)
        if log_progress:
            self._log([sql])
        if not skip_confirmation and self._get_confirmation():
            sql = sql.replace('\n', ' ')
            result_file = "%s-%s-%s.csv" % (sql_query_file_path.split('/')[-1], month, location_id)
            with open(result_file, "w") as output:
                db_conn = connections[db_alias]
                c = db_conn.cursor()
                c.copy_expert("COPY ({query}) TO STDOUT DELIMITER ',' CSV HEADER;".format(query=sql), output)
            return [result_file]

    def _log(self, queries):
        print("Running queries")
        for sql in queries:
            print(sql)

    def _get_confirmation(self):
        proceed = input("Continue?(YES)")
        return proceed == "YES"
