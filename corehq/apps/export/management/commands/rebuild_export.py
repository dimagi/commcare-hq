from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import multiprocessing

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.export.multiprocess import rebuild_export_mutiprocess

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild a saved export using multiple processes"

    def add_arguments(self, parser):
        parser.add_argument('export_id')
        parser.add_argument(
            '--chunksize',
            type=int,
            dest='page_size',
            default=100000,
        )
        parser.add_argument(
            '--processes',
            type=int,
            dest='processes',
            default=multiprocessing.cpu_count() - 1,
            help='Number of parallel processes to run.'
        )

    def handle(self, **options):
        if __debug__:
            raise CommandError("You should run this with 'python -O'")

        export_id = options.pop('export_id')
        page_size = options.pop('page_size')
        processes = options.pop('processes')

        rebuild_export_mutiprocess(export_id, processes, page_size)

        self.stdout.write(self.style.SUCCESS('Rebuild Complete'))
