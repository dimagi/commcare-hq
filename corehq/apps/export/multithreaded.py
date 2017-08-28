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

from corehq.apps.export.export import (
    ExportFile, _get_writer, _save_export_payload)
from corehq.apps.export.export import _write_export_instance
from corehq.elastic import ScanResult
from corehq.util.files import safe_filename
from couchexport.export import get_writer
from couchexport.writers import ZippedExportWriter

UNPROCESSED_PAGES_DIR = 'unprocessed'

logger = logging.getLogger(__name__)


ProgressValue = namedtuple('ProgressValue', 'page progress total')
SuccessResult = namedtuple('SuccessResult', 'success page export_path')
RetryResult = namedtuple('RetryResult', 'page path page_size retry_count')
QueuedResult = namedtuple('QueuedResult', 'async_result page path page_size retry_count')


def run_export_with_logging(export_instance, page_number, dump_path, doc_count, attempts):
    """Log any exceptions here since logging on the other side of the process queue
    won't show the traceback
    """
    logger.info('    Processing page {} started (attempt {})'.format(page_number, attempts))
    progress_queue = getattr(run_export, 'queue', None)
    update_frequency = min(1000, int(doc_count / 10) or 1)
    progress_tracker = LoggingProgressTracker(page_number, progress_queue, update_frequency)
    try:
        result = run_export(export_instance, page_number, dump_path, doc_count, progress_tracker)
        if progress_queue:
            # just to make sure we set progress to 100%
            progress_queue.put(ProgressValue(page_number, doc_count, doc_count))
        logger.info('    Processing page {} complete'.format(page_number))
        return result
    except Exception:
        logger.exception("Error processing page {} (attempt {})".format(page_number, attempts))
        raise


def run_export(export_instance, page_number, dump_path, doc_count, progress_tracker=None):
    docs = _get_export_documents_from_file(dump_path, doc_count)
    export_file = get_export_file(export_instance, docs, progress_tracker)
    return SuccessResult(True, page_number, export_file.path)


def _get_export_documents_from_file(dump_path, doc_count):
    """Mimic the results of an ES scroll query but get results from jsonlines file"""
    def _doc_iter():
        with gzip.open(dump_path) as f:
            for line in f.readlines():
                yield json.loads(line)
        os.remove(dump_path)

    return ScanResult(doc_count, _doc_iter())


def get_export_file(export_instance, docs, progress_tracker=None):
    export_instances = [export_instance]
    writer = _get_writer(export_instances, allow_pagination=False)
    with writer.open(export_instances):
        _write_export_instance(writer, export_instance, docs, progress_tracker)
        return ExportFile(writer.path, writer.format)


class LoggingProgressTracker(object):
    """Ducktyped class that mimics the interface of a celery task
    to keep track of export progress

    def update_state(self, state=None, meta=None):
        ...

    """
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
                    logger.info('[{}] {} of {} complete'.format(self.name, current, total))


class MultithreadedExporter(object):
    """Helper class to manage multi-threaded exporting"""

    def __init__(self, export_instance, total_docs, num_processes):
        self.export_instance = export_instance
        self.results = []
        self.progress_queue = multiprocessing.Queue()
        self.progress = multiprocessing.Process(target=_output_progress, args=(self.progress_queue, total_docs))

        self.export_function = run_export_with_logging

        def _set_queue(queue):
            """Set the progress queue as an attribute on the function
            You can't pass this as an arg"""
            self.export_function.queue = queue

        self.pool = multiprocessing.Pool(
            processes=num_processes,
            initializer=_set_queue,
            initargs=[self.progress_queue]
        )

        self.is_zip = isinstance(get_writer(export_instance.export_format), ZippedExportWriter)

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
        self.progress_queue.put(ProgressValue(page_info.page, 0, page_info.page_size))
        args = self.export_instance, page_info.page, page_info.path, page_info.page_size, attempts
        result = self.pool.apply_async(self.export_function, args=args)
        self.results.append(QueuedResult(result, page_info.page, page_info.path, page_info.page_size, attempts))

    def wait_till_completion(self):
        results = self.get_results()
        final_path = self.build_final_export(results)
        self.upload(final_path)

    def get_results(self, retries_per_page=3):
        export_results = []
        try:
            while self.results:
                queued_result = self.results[0]
                try:
                    export_results.append(queued_result.async_result.get(timeout=5))
                    self.results.pop(0)
                except KeyboardInterrupt:
                    raise
                except multiprocessing.TimeoutError:
                    pass
                except Exception:
                    logger.exception(
                        "Error getting results for page %s after %s tries",
                        queued_result.page,
                        queued_result.retry_count
                    )
                    self.results.pop(0)
                    if queued_result.retry_count < retries_per_page:
                        self.process_page(queued_result)
                    else:
                        export_results.append(queued_result)
        finally:
            self.stop()

        return export_results

    def stop(self):
        self._safe_terminate(self.pool)
        self._safe_terminate(self.progress)

        for p in multiprocessing.active_children():
            self._safe_terminate(p)

    def _safe_terminate(self, process):
        try:
            process.terminate()
        except:
            pass

    def build_final_export(self, export_results):
        final_path = tempfile.mktemp()
        base_name = safe_filename(self.export_instance.name or 'Export')
        with zipfile.ZipFile(final_path, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            pages = len(export_results)
            for result in export_results:
                if not isinstance(result, SuccessResult):
                    logger.error('  Error in page %s so not added to final output', result.page)
                    if os.path.exists(result.path):
                        raw_dump_path = result.path
                        logger.info('    Adding raw dump of page %s to final output', result.page)
                        destination = '{}/page_{}.json.gz'.format(UNPROCESSED_PAGES_DIR, result.page)
                        z.write(raw_dump_path, destination, zipfile.ZIP_STORED)
                    continue

                logger.info('  Adding page {} of {} to final file'.format(result.page, pages))
                if self.is_zip:
                    with zipfile.ZipFile(result.export_path, 'r') as page_file:
                        for path in page_file.namelist():
                            prefix, suffix = path.rsplit('/', 1)
                            z.writestr('{}/{}_{}'.format(prefix, result.page, suffix), page_file.open(path).read())
                else:
                    z.write(result.export_path, '{}_{}'.format(base_name, result.page))

        return final_path

    def upload(self, final_path, clean=True):
        logger.info('Uploading final export')
        with open(final_path, 'r') as payload:
            _save_export_payload(self.export_instance, payload)
        if clean:
            os.remove(final_path)


def _output_progress(queue, total_docs):
    """Poll the queue for ProgressValue objects and log progress to logger"""
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
            logger.info(
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
