from __future__ import print_function

import gzip
import json
import logging
import multiprocessing
import os
import tempfile
import time
import zipfile
from Queue import Empty
from collections import namedtuple
from datetime import timedelta

from django.core.management import color_style
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


ProgressValue = namedtuple('ProgressValue', 'page progress total')

SuccessResult = namedtuple('SuccessResult', 'success page export_path')
RetryResult = namedtuple('RetryResult', 'page path page_size retry_count')
QueuedResult = namedtuple('QueuedResult', 'async_result page path page_size retry_count')


style = color_style()


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

        exporter = MultithreadedExporter(processes, export_instance, total_docs)
        dump_output = DumpOutput(export_id)
        print('Starting data dump of {} docs'.format(total_docs))

        with exporter:
            with dump_output:
                for index, doc in enumerate(_get_export_documents(export_instance, filters)):
                    dump_output.write(doc)
                    if dump_output.page_size == page_size:
                        exporter.process_page(dump_output)
                        dump_output.next_page()
                if dump_output.page_size:
                    exporter.process_page(dump_output)

        export_results = exporter.get_results()
        print('Processing complete')

        print('Compiling final file')
        final_path = tempfile.mktemp()
        base_name = safe_filename(export_instance.name or 'Export')
        with zipfile.ZipFile(final_path, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            pages = len(export_results)
            for result in export_results:
                if not isinstance(result, SuccessResult):
                    print(style.ERROR('  Error in page {} so not added to final output'.format(result.page)))
                    if os.path.exists(result.path):
                        raw_dump_path = result.path
                        print('    Adding raw dump of page {} to final output'.format(result.page))
                        z.write(raw_dump_path, 'unprocessed/page_{}.json.gz'.format(result.page), zipfile.ZIP_STORED)
                    continue

                print('  Adding page {} of {} to final file'.format(result.page, pages))
                if is_zip:
                    with zipfile.ZipFile(result.export_path, 'r') as page_file:
                        for path in page_file.namelist():
                            prefix, suffix = path.rsplit('/', 1)
                            z.writestr('{}/{}_{}'.format(prefix, result.page, suffix), page_file.open(path).read())
                else:
                    z.write(result.export_path, '{}_{}'.format(base_name, result.page))

        print('Uploading final export')
        with open(final_path, 'r') as payload:
            _save_export_payload(export_instance, payload)
        os.remove(final_path)
        self.stdout.write(self.style.SUCCESS('Rebuild Complete'))


def run_export_safe(export_instance, page_number, dump_path, doc_count, attempts):
    print('    Processing page {} started (attempt {})'.format(page_number, attempts))
    try:
        return run_export(export_instance, page_number, dump_path, doc_count)
    except Exception:
        logger.exception("Error processing page {} (attempt {})".format(page_number, attempts))
        raise


def run_export(export_instance, page_number, dump_path, doc_count):
    async_queue = getattr(run_export, 'queue', None)

    docs = _get_export_documents_from_file(dump_path, doc_count)
    update_frequency = min(1000, int(doc_count / 10) or 1)
    progress_tracker = LoggingProgressTracker(page_number, async_queue, update_frequency)
    export_file = get_export_file(export_instance, docs, progress_tracker)
    if async_queue:
        run_export.queue.put(ProgressValue(page_number, doc_count, doc_count))  # just to make sure we set progress to 100%
    print('    Processing page {} complete'.format(page_number))
    return SuccessResult(True, page_number, export_file.path)


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


class MultithreadedExporter(object):
    def __init__(self, num_processes, export_instance, total_docs):
        self.export_instance = export_instance
        self.results = []
        self.progress_queue = multiprocessing.Queue()
        self.progress = multiprocessing.Process(target=_output_progress, args=(self.progress_queue, total_docs))

        def _set_queue(queue):
            run_export.queue = queue
        self.pool = multiprocessing.Pool(
            processes=num_processes,
            initializer=_set_queue,
            initargs=[self.progress_queue]
        )

        self.export_results = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and exc_val:
            self.stop()

    def start(self):
        self.progress.start()

    def process_page(self, page_info):
        """
        :param page_info: object with attributes:
                           - page: page number (int)
                           - path: path to raw data dump
                           - page_size: number of docs in raw data dump
        """
        attempts = getattr(page_info, 'retry_count', 0) + 1
        if attempts == 1:
            print('  Dump page {} complete: {} docs'.format(page_info.page, page_info.page_size))

        self.progress_queue.put(ProgressValue(page_info.page, 0, page_info.page_size))
        args = self.export_instance, page_info.page, page_info.path, page_info.page_size, attempts
        result = self.pool.apply_async(run_export_safe, args=args)
        self.results.append(QueuedResult(result, page_info.page, page_info.path, page_info.page_size, attempts))

    def get_results(self, retries_per_page=3):
        try:
            while self.results:
                queued_result = self.results[0]
                try:
                    self.export_results.append(queued_result.async_result.get(timeout=5))
                    self.results.pop(0)
                except KeyboardInterrupt:
                    raise
                except multiprocessing.TimeoutError:
                    pass
                except Exception:
                    logger.exception("Error getting results: %s", queued_result)
                    print(style.ERROR('    Unable to process page {} after {} tries'.format(
                        queued_result.page, queued_result.retry_count))
                    )
                    self.results.pop(0)
                    if queued_result.retry_count < retries_per_page:
                        self.process_page(queued_result)
                    else:
                        self.export_results.append(queued_result)
        finally:
            self.stop()

        return self.export_results

    def stop(self):
        self.pool.terminate()
        self.progress.terminate()

        for p in multiprocessing.active_children():
            p.terminate()


def _output_progress(queue, total_docs):
    page_progress = {}
    progress = total_dumped = 0
    start = time.time()
    while total_dumped == 0 or progress < total_dumped:
        try:
            poll_start = time.time()
            while True:
                if (time.time() - poll_start) > 20:
                    break
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
                '{progress} of {total} ({percent}%) ({dumped} dumped) processed in {elapsed} '
                '(Estimated completion in {remaining}) '
                '(Avg processing rate: {rate} docs per sec)'.format(
                    progress=progress,
                    total=total_docs,
                    percent=int(progress * 100 / total_docs),
                    dumped=total_dumped,
                    elapsed=elapsed,
                    remaining=time_remaining,
                    rate=int(docs_per_second)
                ))
