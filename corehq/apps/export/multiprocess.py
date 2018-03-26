"""
This package contains classes and function for processing ExportInstances using
multiple processes.

To rebuild an export run the following:

    rebuild_export_mutiprocess(export_instance_id, num_processes, page_size)

You can also use the MultiprocessExporter class to have more control over the process.
See the 'process_skipped_pages' management command for an example.

The export works as follows:
  * Dump raw docs from ES into files of size N docs
  * Once each file is complete add it to a multiprocessing Queue
  * Pool of X processes listen to queue and process the dump file
  * Results returned back to the main process
    * Unsuccessful results can be retried
  * Add successful pages to final ZIP archive
  * Add raw data dumps for unsuccessful pages to final ZIP archive
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import gzip
import json
import logging
import multiprocessing
import os
import tempfile
import time
import zipfile
from six.moves.queue import Empty
from collections import namedtuple
from datetime import timedelta

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import (
    ExportFile, get_export_writer, save_export_payload, get_export_size, get_export_documents)
from corehq.apps.export.export import write_export_instance
from corehq.elastic import ScanResult
from corehq.util.files import safe_filename
from couchexport.export import get_writer
from couchexport.writers import ZippedExportWriter

TEMP_FILE_PREFIX = 'cchq_export_dump_'

UNPROCESSED_PAGES_DIR = 'unprocessed'

logger = logging.getLogger(__name__)


ProgressValue = namedtuple('ProgressValue', 'page progress total')


class BaseResult(object):
    success = False

    def __init__(self, page_number, page_path, page_size):
        self.page = page_number
        self.path = page_path
        self.page_size = page_size


class SuccessResult(BaseResult):
    success = True


class RetryResult(BaseResult):
    def __init__(self, page_number, page_path, page_size, retry_count):
        super(RetryResult, self).__init__(page_number, page_path, page_size)
        self.retry_count = retry_count


class QueuedResult(RetryResult):
    def __init__(self, async_result, page_number, page_path, page_size, retry_count):
        super(QueuedResult, self).__init__(page_number, page_path, page_size, retry_count)
        self.async_result = async_result


class OutputPaginator(object):
    """Helper class to paginate raw export output"""
    def __init__(self, export_id, start_page_count=0):
        self.export_id = export_id
        self.page = start_page_count
        self.page_size = 0
        self.file = None

    def __enter__(self):
        self._new_file()

    def _new_file(self):
        if self.file:
            self.file.close()
        prefix = '{}{}_'.format(TEMP_FILE_PREFIX, self.export_id)
        fileobj = tempfile.NamedTemporaryFile(prefix=prefix, mode='wb', delete=False)
        self.path = fileobj.name
        self.file = gzip.GzipFile(fileobj=fileobj)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.close()
        if exc_type is not None:
            os.remove(self.path)
        self.file = None
        self.path = None

    def next_page(self):
        self.page += 1
        self.page_size = 0
        self._new_file()

    def write(self, doc):
        self.page_size += 1
        self.file.write('{}\n'.format(json.dumps(doc)))

    def get_result(self):
        return RetryResult(self.page, self.path, self.page_size, 0)


def rebuild_export_mutiprocess(export_id, num_processes, page_size=100000):
    assert num_processes > 0

    export_instance = get_properly_wrapped_export_instance(export_id)
    filters = export_instance.get_filters()
    total_docs = get_export_size(export_instance, filters)
    exporter = MultiprocessExporter(export_instance, total_docs, num_processes)
    paginator = OutputPaginator(export_id)

    logger.info('Starting data dump of {} docs'.format(total_docs))
    run_multiprocess_exporter(exporter, filters, paginator, page_size)


def run_multiprocess_exporter(exporter, filters, paginator, page_size):
    def _log_page_dumped(paginator):
        logger.info('  Dump page {} complete: {} docs'.format(paginator.page, paginator.page_size))

    with exporter, paginator:
        for doc in get_export_documents(exporter.export_instance, filters):
            paginator.write(doc)
            if paginator.page_size == page_size:
                _log_page_dumped(paginator)
                exporter.process_page(paginator.get_result())
                paginator.next_page()
        if paginator.page_size:
            _log_page_dumped(paginator)
            exporter.process_page(paginator.get_result())

    exporter.wait_till_completion()


def run_export_with_logging(export_instance, page_number, dump_path, doc_count, attempts):
    """Log any exceptions here since logging on the other side of the process queue
    won't show the traceback
    """
    logger.info('    Processing page {} started (attempt {})'.format(page_number, attempts))
    progress_queue = getattr(run_export_with_logging, 'queue', None)
    update_frequency = min(1000, int(doc_count // 10) or 1)
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
    return SuccessResult(page_number, export_file.path, doc_count)


def _get_export_documents_from_file(dump_path, doc_count):
    """Mimic the results of an ES scroll query but get results from jsonlines file"""
    def _doc_iter():
        with gzip.open(dump_path) as file:
            for line in file:
                yield json.loads(line.decode())
        os.remove(dump_path)

    return ScanResult(doc_count, _doc_iter())


def get_export_file(export_instance, docs, progress_tracker=None):
    export_instances = [export_instance]
    writer = get_export_writer(export_instances, allow_pagination=False)
    with writer.open(export_instances):
        write_export_instance(writer, export_instance, docs, progress_tracker)
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


class MultiprocessExporter(object):
    """Helper class to manage multi-process exporting"""

    def __init__(self, export_instance, total_docs, num_processes, existing_archive_path=None, keep_file=False):
        self.keep_file = keep_file
        self.export_instance = export_instance
        self.existing_archive_path = existing_archive_path
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
        self.premature_exit = False

    def __enter__(self):
        self.start()
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
        attempts = page_info.retry_count + 1
        self.progress_queue.put(ProgressValue(page_info.page, 0, page_info.page_size))
        args = self.export_instance, page_info.page, page_info.path, page_info.page_size, attempts
        result = self.pool.apply_async(self.export_function, args=args)
        self.results.append(QueuedResult(result, page_info.page, page_info.path, page_info.page_size, attempts))

    def wait_till_completion(self):
        results = self.get_results()
        final_path = self.build_final_export(results)
        if self.premature_exit:
            logger.warning("\n------- PREMATURE EXIT --------\nResult written to %s\n", final_path)
        else:
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
                    logger.error('Exiting before all results received.')
                    self.premature_exit = True
                    export_results.extend(self.results)
                    return export_results
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

    def _get_zipfile_for_final_archive(self):
        if self.existing_archive_path:
            return zipfile.ZipFile(
                self.existing_archive_path, mode='a',
                compression=zipfile.ZIP_DEFLATED, allowZip64=True
            )
        else:
            prefix = '{}{}_final_'.format(TEMP_FILE_PREFIX, self.export_instance.get_id)
            final_file_obj = tempfile.NamedTemporaryFile(prefix=prefix, mode='wb', delete=False)
            return zipfile.ZipFile(
                final_file_obj, mode='w',
                compression=zipfile.ZIP_DEFLATED, allowZip64=True
            )

    def build_final_export(self, export_results):
        base_name = safe_filename(self.export_instance.name or 'Export')
        final_zip = self._get_zipfile_for_final_archive()
        with final_zip:
            pages = len(export_results)
            for result in export_results:
                if not result.success:
                    logger.error('  Error in page %s so not added to final output', result.page)
                    if os.path.exists(result.path):
                        raw_dump_path = result.path
                        logger.info('    Adding raw dump of page %s to final output', result.page)
                        destination = '{}/page_{}.json.gz'.format(UNPROCESSED_PAGES_DIR, result.page)
                        final_zip.write(raw_dump_path, destination, zipfile.ZIP_STORED)
                        os.remove(raw_dump_path)
                    continue

                logger.info('  Adding page {} of {} to final file'.format(result.page, pages))
                if self.is_zip:
                    _add_compressed_page_to_zip(final_zip, result.page, result.path)
                else:
                    final_zip.write(result.path, '{}_{}'.format(base_name, result.page))

        return final_zip.filename

    def upload(self, final_path):
        logger.info('Uploading final export')
        with open(final_path, 'r') as payload:
            save_export_payload(self.export_instance, payload)
        if not self.keep_file:
            os.remove(final_path)


def _add_compressed_page_to_zip(zip_file, page_number, zip_path_to_add):
    with zipfile.ZipFile(zip_path_to_add, 'r') as page_file:
        for path in page_file.namelist():
            prefix, suffix = path.rsplit('/', 1)
            zip_file.writestr('{}/{}_{}'.format(
                prefix, page_number, suffix), page_file.open(path).read()
            )


def _output_progress(queue, total_docs):
    """Poll the queue for ProgressValue objects and log progress to logger"""
    logger.debug('Starting progress reporting process')
    page_progress = {}
    progress = total_dumped = 0
    start = time.time()
    while total_dumped == 0 or progress < total_dumped:
        try:
            poll_start = time.time()
            while time.time() - poll_start < 20:
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
                    percent=int(progress * 100 // total_docs),
                    dumped=total_dumped,
                    elapsed=elapsed,
                    remaining=time_remaining,
                    rate=int(docs_per_second)
                ))
