from django.core.management.base import BaseCommand

from corehq.apps.userreports import tasks
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)


class Command(BaseCommand):
    help = "Rebuild all user configurable reporting tables in domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--initiated-by', required=True, action='store',
            dest='initiated', help='Who initiated the rebuild'
        )
        parser.add_argument("--async", action="store_true", dest="async", help="Run on celery")

    def handle(self, domain, **options):
        tables = StaticDataSourceConfiguration.by_domain(domain)
        tables.extend(DataSourceConfiguration.by_domain(domain))
        tables_by_id = {table.table_id: table for table in tables}

        print("Rebuilding {} tables".format(len(tables_by_id)))

        for table in tables_by_id.values():
            if options['async']:
                tasks.rebuild_indicators.delay(
                    table._id, initiated_by=options['initiated'], source='rebuild_tables_by_domain'
                )
            else:
                tasks.rebuild_indicators(
                    table._id, initiated_by=options['initiated'], source='rebuild_tables_by_domain'
                )
