from __future__ import print_function

import gzip
import json
import multiprocessing
import os
import tempfile
import time
import zipfile
from Queue import Empty
from collections import namedtuple
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import (
    _get_export_documents, ExportFile, _save_export_payload, _Writer, get_export_size
)
from corehq.apps.export.export import _write_export_instance
from corehq.elastic import ScanResult
from corehq.util.files import safe_filename
from couchexport.export import get_writer
from couchexport.writers import ZippedExportWriter


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


ProgressValue = namedtuple('ProgressValue', 'page progress total')


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
        is_zip = isinstance(get_writer(export_instance.export_format), ZippedExportWriter)
        filters = export_instance.get_filters()
        total_docs = get_export_size(export_instance, filters)

        results = []
        progress_queue = multiprocessing.Queue()

        progress = multiprocessing.Process(target=_output_progress, args=(progress_queue, total_docs))
        progress.start()

        def _process_page(pool, output):
            args = export_instance, output.page, output.path, output.page_size
            progress_queue.put(ProgressValue(output.page, 0, output.page_size))
            results.append(pool.apply_async(run_export, args=args))
            print('  Dump page {} complete: {} docs'.format(output.page, output.page_size))

        def _set_queue(queue):
            run_export.queue = queue

        pool = multiprocessing.Pool(processes=processes, initializer=_set_queue, initargs=[progress_queue])
        dump_output = DumpOutput(export_id)
        print('Starting data dump of {} docs'.format(total_docs))
        with dump_output:
            for index, doc in enumerate(_get_export_documents(export_instance, filters)):
                dump_output.write(doc)
                if dump_output.page_size == page_size:
                    _process_page(pool, dump_output)
                    dump_output.next_page()
            if dump_output.page_size:
                _process_page(pool, dump_output)

        export_files = [p.get() for p in results]
        try:
            progress.terminate()
        except:
            pass

        print('Processing complete')

        print('Compiling final file')
        final_path = tempfile.mktemp()
        base_name = safe_filename(export_instance.name or 'Export')
        with zipfile.ZipFile(final_path, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for page, export_path in export_files:
                print('  Adding page {} to final file'.format(page))
                if is_zip:
                    with zipfile.ZipFile(export_path, 'r') as page_file:
                        for path in page_file.namelist():
                            prefix, suffix = path.rsplit('/', 1)
                            z.writestr('{}/{}_{}'.format(prefix, page, suffix), page_file.open(path).read())
                else:
                    z.write(export_path, '{}_{}'.format(base_name, page))

        print('Uploading final export')
        with open(final_path, 'r') as payload:
            _save_export_payload(export_instance, payload)
        os.remove(final_path)


def run_export(export_instance, page_number, dump_path, doc_count):
    print('    Processing page {} started'.format(page_number))
    docs = _get_export_documents_from_file(dump_path, doc_count)
    update_frequency = min(1000, int(doc_count / 10) or 1)
    progress_tracker = LoggingProgressTracker(page_number, run_export.queue, update_frequency)
    export_file = get_export_file(export_instance, docs, progress_tracker)
    run_export.queue.put(ProgressValue(page_number, doc_count, doc_count))  # just to make sure we set progress to 100%
    print('    Processing page {} complete'.format(page_number))
    return page_number, export_file.path


def _get_export_documents_from_file(dump_path, doc_count):
    def _doc_iter():
        with gzip.open(dump_path) as f:
            for line in f.readlines():
                yield json.loads(line)
        os.remove(dump_path)

    return ScanResult(doc_count, _doc_iter())


def get_export_file(export_instance, docs, progress_tracker=None):
    export_instances = [export_instance]
    legacy_writer = get_writer(export_instance.export_format)
    writer = _Writer(legacy_writer)
    with writer.open(export_instances):
        _write_export_instance(writer, export_instance, docs, progress_tracker)
        return ExportFile(writer.path, writer.format)


class LoggingProgressTracker(object):
    def __init__(self, name, progress_queue=None, update_frequency=100):
        self.name = name
        self.progress_queue = progress_queue
        self.update_frequency = update_frequency

    def update_state(self, state=None, meta=None):
        meta = meta or {}
        current = meta.get('current')
        total = meta.get('total', 0)
        if current is not None:
            if current % self.update_frequency == 0:
                if self.progress_queue:
                    self.progress_queue.put(ProgressValue(self.name, current, total))
                else:
                    print('[{}] {} of {} complete'.format(self.name, current, total))


def _output_progress(queue, total_docs):
    page_progress = {}
    progress = total_dumped = 0
    start = time.time()
    while total_dumped == 0 or progress < total_dumped:
        pages = page_progress.keys() or [1]
        try:
            for p in pages:
                value = queue.get(timeout=10)
                page_progress[value.page] = value
        except Empty:
            pass
        total_dumped = sum(val.total for val in page_progress.values())
        progress = sum(val.progress for val in page_progress.values())
        elapsed = time.time() - start
        docs_per_second = progress / elapsed
        docs_remaining = total_docs - progress
        try:
            time_remaining = docs_remaining / docs_per_second
            time_remaining = str(timedelta(seconds=time_remaining)).split('.')[0]
        except ArithmeticError:
            time_remaining = 'unknown'
        if total_dumped > 0:
            elapsed = str(timedelta(seconds=elapsed)).split('.')[0]
            print(
                '{progress} of {total} ({dumped} dumped) processed in {elapsed} '
                '(Estimated completion in {remaining}) '
                '(Avg processing rate: {rate} docs per sec)'.format(
                    progress=progress,
                    total=total_docs,
                    dumped=total_dumped,
                    elapsed=elapsed,
                    remaining=time_remaining,
                    rate=int(docs_per_second)
                ))
