import logging
import multiprocessing

from django.core.management.base import BaseCommand, CommandError

from couchdbkit import ResourceNotFound

from corehq.apps.export.multiprocess import rebuild_export_mutiprocess

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild a saved export using multiple processes"

    def add_arguments(self, parser):
        parser.add_argument('domain')
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

        domain = options.pop('domain')
        export_id = options.pop('export_id')
        page_size = options.pop('page_size')
        processes = options.pop('processes')

        try:
            rebuild_export_mutiprocess(domain, export_id, processes, page_size)
        except ResourceNotFound:
            raise CommandError(f"Export {export_id} not found in domain {domain}")

        self.stdout.write(self.style.SUCCESS('Rebuild Complete'))
