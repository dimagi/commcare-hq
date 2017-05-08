from __future__ import print_function
import time

from django.core.management.base import BaseCommand

from corehq.apps.export.models import FormExportInstance
from corehq.apps.export.esaccessors import get_form_export_base_query


class Command(BaseCommand):
    help = "Testing scan and scroll"

    def add_arguments(self, parser):
        parser.add_argument(
            '--export-id',
            dest='export_id',
            default=None,
            help='Export ID to test',
        )
        parser.add_argument(
            '--size',
            dest='size',
            type=int,
            default=1000,
            help='Size of scroll query',
        )
        parser.add_argument(
            '--limit',
            dest='limit',
            type=int,
            default=1000,
            help='Max number of iterations to perform',
        )

    def handle(self, **options):
        size = options.get('size')
        limit = options.get('limit')
        export_instance = FormExportInstance.get(options.get('export_id'))
        query = get_form_export_base_query(
            export_instance.domain,
            export_instance.app_id,
            export_instance.xmlns,
            export_instance.include_errors
        )

        docs = iter(query.size(size).scroll())
        i = 0
        n_shards = 5
        print('iteration,size,time_ms')
        while True:
            start = int(time.time() * 1000)
            try:
                next(docs)
            except StopIteration:
                print('Stopping')
                break

            if i % (size * n_shards) == 0:
                print('{},{},{}'.format(i, size, (time.time() * 1000) - start))
            i += 1
            if i >= limit:
                break
