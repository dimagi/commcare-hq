import logging
import math
import time

from django.conf import settings

from pillowtop.exceptions import BulkDocException, PillowtopIndexingError
from pillowtop.logger import pillow_logging
from pillowtop.utils import (
    ErrorCollector,
    build_bulk_payload,
    bulk_fetch_changes_docs,
    ensure_document_exists,
    ensure_matched_revisions,
    get_errors_with_ids,
)

from corehq.util.es.elasticsearch import (
    ConflictError,
    ConnectionError,
    NotFoundError,
    RequestError,
)
from corehq.util.metrics import metrics_histogram_timer

from .interface import BulkPillowProcessor, PillowProcessor

logger = logging.getLogger(__name__)


def identity(x):
    return x


def noop_filter(x):
    return False


RETRY_INTERVAL = 2  # seconds, exponentially increasing
MAX_RETRIES = 4  # exponential factor threshold for alerts


class ElasticProcessor(PillowProcessor):
    """Generic processor to transform documents and insert into ES.

    Processes one document at a time.

    Reads from:
      - Usually Couch
      - Sometimes SQL

    Writes to:
      - ES
    """

    def __init__(self, adapter, doc_filter_fn=None, change_filter_fn=None):
        self.adapter = adapter
        self.change_filter_fn = change_filter_fn or noop_filter
        self.doc_filter_fn = doc_filter_fn or noop_filter

    def process_change(self, change):
        from corehq.apps.change_feed.document_types import (
            get_doc_meta_object_from_document,
        )

        if self.change_filter_fn and self.change_filter_fn(change):
            return

        if change.deleted and change.id:
            doc = change.get_document()
            if doc and doc.get('doc_type'):
                logger.info(
                    f'[process_change] Attempting to delete doc {change.id}')
                current_meta = get_doc_meta_object_from_document(doc)
                if current_meta.is_deletion:
                    self._delete_doc_if_exists(change.id)
                    logger.info(
                        f"[process_change] Deleted doc {change.id}")
                else:
                    logger.info(
                        f"[process_change] Not deleting doc {change.id} "
                        "because current_meta.is_deletion is false")
            else:
                self._delete_doc_if_exists(change.id)
                logger.info(
                    f"[process_change] Deleted doc {change.id}")
            return

        with self._datadog_timing('extract'):
            doc = change.get_document()

            ensure_document_exists(change)
            ensure_matched_revisions(change, doc)

        with self._datadog_timing('transform'):
            if doc is None or (self.doc_filter_fn and self.doc_filter_fn(doc)):
                return

            if doc.get('doc_type') is not None and doc['doc_type'].endswith("-Deleted"):
                self._delete_doc_if_exists(change.id)
                return

        # send it across
        with self._datadog_timing('load'):
            send_to_elasticsearch(
                doc_id=change.id,
                adapter=self.adapter,
                name='ElasticProcessor',
                data=doc,
            )

    def _delete_doc_if_exists(self, doc_id):
        send_to_elasticsearch(
            doc_id=doc_id,
            adapter=self.adapter,
            name='ElasticProcessor',
            delete=True
        )

    def _datadog_timing(self, step):
        return metrics_histogram_timer(
            'commcare.change_feed.processor.timing',
            timing_buckets=(.03, .1, .3, 1, 3, 10),
            tags={
                'action': step,
                'index': self.adapter.index_name,
            })


class BulkElasticProcessor(ElasticProcessor, BulkPillowProcessor):
    """Generic processor to transform documents and insert into ES.

    Processes one "chunk" of changes at a time (chunk size specified by pillow).

    Reads from:
      - Usually Couch
      - Sometimes SQL

    Writes to:
      - ES
    """

    def process_changes_chunk(self, changes_chunk):
        logger.info('Processing chunk of changes in BulkElasticProcessor')
        if self.change_filter_fn:
            changes_chunk = [
                change for change in changes_chunk
                if not self.change_filter_fn(change)
            ]
        with self._datadog_timing('bulk_extract'):
            bad_changes, docs = bulk_fetch_changes_docs(changes_chunk)

        with self._datadog_timing('bulk_transform'):
            changes_to_process = {
                change.id: change
                for change in changes_chunk
                if change.document and not self.doc_filter_fn(change.document)
            }
            retry_changes = list(bad_changes)

            error_collector = ErrorCollector()
            es_actions = build_bulk_payload(
                list(changes_to_process.values()),
                error_collector,
            )
            error_changes = error_collector.errors

        try:
            with self._datadog_timing('bulk_load'):
                _, errors = self.adapter.bulk(
                    es_actions,
                    raise_errors=False,
                )
        except Exception as e:
            pillow_logging.exception("Elastic bulk error: %s", e)
            error_changes.extend([
                (change, e) for change in changes_to_process.values()
            ])
        else:
            for change_id, error_msg in get_errors_with_ids(errors):
                error_changes.append((changes_to_process[change_id], BulkDocException(error_msg)))
        return retry_changes, error_changes


def send_to_elasticsearch(adapter, doc_id, name,
                        data=None, delete=False, es_merge_update=False):
    """
    More fault tolerant es.put method
    kwargs:
        es_merge_update: Set this to True to use Elasticsearch.update instead of Elasticsearch.index
            which merges existing ES doc and current update. If this is set to False, the doc will be replaced

    """
    data = data if data is not None else {}
    current_tries = 0
    retries = _retries()
    propagate_failure = _propagate_failure()
    while current_tries < retries:
        try:
            if delete:
                adapter.delete(doc_id)
            else:
                if es_merge_update:
                    # The `retry_on_conflict` param is only valid on `update`
                    # requests. ES <5.x was lenient of its presence on `index`
                    # requests, ES >=5.x is not.
                    adapter.update(doc_id, fields=data, retry_on_conflict=2)
                else:
                    # use the same index API to create or update doc
                    adapter.index(data)
            break
        except ConnectionError:
            current_tries += 1
            if current_tries == retries:
                message = "[%s] Max retry error on %s/%s/%s"
                args = (name, adapter.index_name, adapter.type, doc_id)
                if propagate_failure:
                    raise PillowtopIndexingError(message % args)
                else:
                    pillow_logging.exception(message, *args)
            else:
                pillow_logging.exception("[%s] put_robust error attempt %s/%s", name, current_tries, retries)

            _sleep_between_retries(current_tries)
        except RequestError:
            message = "[%s] put_robust error: %s/%s/%s"
            args = (name, adapter.index_name, adapter.type, doc_id)
            if propagate_failure:
                raise PillowtopIndexingError(message % args)
            else:
                pillow_logging.exception(message, *args)
            break
        except ConflictError:
            break  # ignore the error if a doc already exists when trying to create it in the index
        except NotFoundError:
            break


def _propagate_failure():
    return settings.UNIT_TESTING


def _retries():
    return 1 if settings.UNIT_TESTING else MAX_RETRIES


def _sleep_between_retries(current_tries):
    time.sleep(math.pow(RETRY_INTERVAL, current_tries))
