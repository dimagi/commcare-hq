from __future__ import print_function

import gzip
import json
import logging
import multiprocessing
import tempfile

from django.core.management import color_style
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import (
    _get_export_documents, get_export_size
)
from corehq.apps.export.multithreaded import MultithreadedExporter

logger = logging.getLogger(__name__)


class DumpOutput(object):
    def __init__(self, export_id):
        self.export_id = export_id
        self.page = 0
        self.page_size = 0
        self.file = None

    def __enter__(self):
        self._new_file()

    def _new_file(self):
        if self.file:
            self.file.close()
        self.path = tempfile.mktemp()
        self.file = gzip.open(self.path, 'wb')

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()
        self.file = None
        self.path = None

    def next_page(self):
        self.page += 1
        self.page_size = 0
        self._new_file()

    def write(self, doc):
        self.page_size += 1
        self.file.write('{}\n'.format(json.dumps(doc)))


class Command(BaseCommand):
    help = "Rebuild a saved export using multiple processes"

    def add_arguments(self, parser):
        parser.add_argument('export_id')
        parser.add_argument(
            '--chunksize',
            type=int,
            dest='page_size',
            default=10000,
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
            raise CommandError("You should run this with 'pythong -O'")

        export_id = options.pop('export_id')
        page_size = options.pop('page_size')
        processes = options.pop('processes')

        export_instance = get_properly_wrapped_export_instance(export_id)
        filters = export_instance.get_filters()
        total_docs = get_export_size(export_instance, filters)

        exporter = MultithreadedExporter(export_instance, total_docs, processes)
        dump_output = DumpOutput(export_id)
        print('Starting data dump of {} docs'.format(total_docs))

        def _log_page_dumped(dump_output):
            logger.info('  Dump page {} complete: {} docs'.format(dump_output.page, dump_output.page_size))

        with exporter:
            with dump_output:
                for index, doc in enumerate(_get_export_documents(export_instance, filters)):
                    dump_output.write(doc)
                    if dump_output.page_size == page_size:
                        _log_page_dumped(dump_output)
                        exporter.process_page(dump_output)
                        dump_output.next_page()
                if dump_output.page_size:
                    _log_page_dumped(dump_output)
                    exporter.process_page(dump_output)

            exporter.wait_till_completion()
        self.stdout.write(self.style.SUCCESS('Rebuild Complete'))
