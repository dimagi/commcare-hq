from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.userreports import tasks
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration


class Command(BaseCommand):
    help = "Rebuild all user configurable reporting tables in domain"
    args = 'domain'
    label = ""

    def handle(self, *args, **options):
        if len(args) < 1:
            raise CommandError('Usage is rebuild_tables_by_domain %s' % self.args)

        domain = args[0]
        tables = StaticDataSourceConfiguration.by_domain(domain)
        tables.extend(DataSourceConfiguration.by_domain(domain))

        print("Rebuilding {} tables".format(len(tables)))

        for table in tables:
            tasks.rebuild_indicators(table._id)
