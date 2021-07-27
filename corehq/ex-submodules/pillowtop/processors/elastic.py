import math
import time

from django.conf import settings

from corehq.util.es.elasticsearch import (
    ConflictError,
    ConnectionError,
    NotFoundError,
    RequestError,
)
from corehq.util.es.interface import ElasticsearchInterface
from corehq.util.metrics import metrics_histogram_timer

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

from .interface import BulkPillowProcessor, PillowProcessor


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

    def __init__(self, elasticsearch, index_info, doc_prep_fn=None, doc_filter_fn=None, change_filter_fn=None):
        self.change_filter_fn = change_filter_fn or noop_filter
        self.doc_filter_fn = doc_filter_fn or noop_filter
        self.elasticsearch = elasticsearch
        self.es_interface = ElasticsearchInterface(self.elasticsearch)
        self.index_info = index_info
        self.doc_transform_fn = doc_prep_fn or identity

    def es_getter(self):
        return self.elasticsearch

    def process_change(self, change):
        if self.change_filter_fn and self.change_filter_fn(change):
            return

        if change.deleted and change.id:
            self._delete_doc_if_exists(change.id)
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

            # prepare doc for es
            doc_ready_to_save = self.doc_transform_fn(doc)

        # send it across
        with self._datadog_timing('load'):
            send_to_elasticsearch(
                index_info=self.index_info,
                doc_type=self.index_info.type,
                doc_id=change.id,
                es_getter=self.es_getter,
                name='ElasticProcessor',
                data=doc_ready_to_save,
            )

    def _delete_doc_if_exists(self, doc_id):
        send_to_elasticsearch(
            index_info=self.index_info,
            doc_type=self.index_info.type,
            doc_id=doc_id,
            es_getter=self.es_getter,
            name='ElasticProcessor',
            delete=True
        )

    def _datadog_timing(self, step):
        return metrics_histogram_timer(
            'commcare.change_feed.processor.timing',
            timing_buckets=(.03, .1, .3, 1, 3, 10),
            tags={
                'action': step,
                'index': self.index_info.alias,
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
                self.index_info, list(changes_to_process.values()), self.doc_transform_fn, error_collector
            )
            error_changes = error_collector.errors

        try:
            with self._datadog_timing('bulk_load'):
                _, errors = self.es_interface.bulk_ops(
                    es_actions, raise_on_error=False, raise_on_exception=False)
        except Exception as e:
            pillow_logging.exception("[%s] ES bulk load error")
            error_changes.extend([
                (change, e) for change in changes_to_process.values()
            ])
        else:
            for change_id, error_msg in get_errors_with_ids(errors):
                error_changes.append((changes_to_process[change_id], BulkDocException(error_msg)))
        return retry_changes, error_changes


def send_to_elasticsearch(index_info, doc_type, doc_id, es_getter, name, data=None,
                          delete=False, es_merge_update=False):
    """
    More fault tolerant es.put method
    kwargs:
        es_merge_update: Set this to True to use Elasticsearch.update instead of Elasticsearch.index
            which merges existing ES doc and current update. If this is set to False, the doc will be replaced

    """
    alias = index_info.alias
    data = data if data is not None else {}
    current_tries = 0
    es_interface = _get_es_interface(es_getter)
    retries = _retries()
    propagate_failure = _propagate_failure()
    while current_tries < retries:
        try:
            if delete:
                es_interface.delete_doc(alias, doc_type, doc_id)
            else:
                if es_merge_update:
                    # The `retry_on_conflict` param is only valid on `update`
                    # requests. ES <5.x was lenient of its presence on `index`
                    # requests, ES >=5.x is not.
                    params = {'retry_on_conflict': 2}
                    es_interface.update_doc_fields(alias, doc_type, doc_id,
                                                   fields=data, params=params)
                else:
                    # use the same index API to create or update doc
                    es_interface.index_doc(alias, doc_type, doc_id, doc=data)
            break
        except ConnectionError:
            current_tries += 1
            if current_tries == retries:
                message = "[%s] Max retry error on %s/%s/%s"
                args = (name, alias, doc_type, doc_id)
                if propagate_failure:
                    raise PillowtopIndexingError(message % args)
                else:
                    pillow_logging.exception(message, *args)
            else:
                pillow_logging.exception("[%s] put_robust error attempt %s/%s", name, current_tries, retries)

            _sleep_between_retries(current_tries)
        except RequestError:
            message = "[%s] put_robust error: %s/%s/%s"
            args = (name, alias, doc_type, doc_id)
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


def _get_es_interface(es_getter):
    return ElasticsearchInterface(es_getter())
