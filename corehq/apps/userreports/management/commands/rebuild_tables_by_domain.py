from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.userreports import tasks
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration


class Command(BaseCommand):
    help = "Rebuild all user configurable reporting tables in domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--initiated-by', required=True, action='store',
            dest='initiated', help='Who initiated the rebuild'
        )

    def handle(self, domain, **options):
        tables = StaticDataSourceConfiguration.by_domain(domain)
        tables.extend(DataSourceConfiguration.by_domain(domain))

        print("Rebuilding {} tables".format(len(tables)))

        for table in tables:
            tasks.rebuild_indicators(
                table._id, initiated_by=options['initiated'], source='rebuild_tables_by_domain'
            )
