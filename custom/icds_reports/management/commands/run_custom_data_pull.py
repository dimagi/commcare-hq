from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from custom.icds_reports.data_pull.exporter import DataExporter


class Command(BaseCommand):
    help = """
    Dump data from a pre-defined custom query for ICDS data pull requests
    or a sql file to generate a result zip file in the current directory.
    The command returns the zip file name.
    """

    def add_arguments(self, parser):
        parser.add_argument('name', help="slug of a custom data pull or a sql file name/path")
        parser.add_argument('db_alias', choices=settings.DATABASES)
        parser.add_argument('--month', help="format YYYY-MM-DD")
        parser.add_argument('--location_id')
        parser.add_argument('-s', '--skip_confirmation', action='store_true')
        parser.add_argument('-l', '--log_progress', action='store_true')

    def handle(self, name, db_alias, *arg, **options):
        if db_alias not in settings.DATABASES:
            raise CommandError("Unexpected db alias")

        month = options.get('month')
        location_id = options.get('location_id')
        skip_confirmation = options.get('skip_confirmation')
        log_progress = options.get('log_progress')
        exporter = DataExporter(name, db_alias, month, location_id)
        if log_progress:
            self._log(exporter.queries)
        if skip_confirmation or self._get_confirmation():
            return exporter.export()

    def _log(self, queries):
        print("Running queries now")
        for sql in queries:
            print(sql)

    def _get_confirmation(self):
        proceed = input("Continue?(YES)")
        return proceed == "YES"
