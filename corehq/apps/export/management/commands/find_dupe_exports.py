from __future__ import print_function
from collections import defaultdict

from django.core.management.base import BaseCommand

from corehq.apps.export.models import FormExportInstance


class Command(BaseCommand):
    help = "Find duplicate exports"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )

    def handle(self, domain, **options):
        key = [domain, 'FormExportInstance']
        exports = FormExportInstance.get_db().view(
            'export_instances_by_domain/view',
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
            reduce=False,
        )
        export_by_xmlns = defaultdict(list)
        for export in exports:
            export_by_xmlns[export['doc']['xmlns']].append(export)

        for xmlns, exports in export_by_xmlns.iteritems():
            print("exports for xmlns {} :".format(xmlns))
            for export in exports:
                tables = export['doc']['tables']
                if tables:
                    columns = tables[0]['columns']
                else:
                    columns = []
                print("{}: {} - {} {}".format(export['id'], export['doc']['name'], len(tables), len(columns)))
