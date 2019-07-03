from __future__ import absolute_import
from __future__ import unicode_literals
import math
import time

from elasticsearch.exceptions import RequestError, ConnectionError, NotFoundError, ConflictError

from pillowtop.utils import ensure_matched_revisions, ensure_document_exists
from pillowtop.exceptions import PillowtopIndexingError
from pillowtop.logger import pillow_logging
from .interface import PillowProcessor

from corehq.util.datadog.gauges import datadog_bucket_timer


def identity(x):
    return x


RETRY_INTERVAL = 2  # seconds, exponentially increasing
MAX_RETRIES = 4  # exponential factor threshold for alerts


class ElasticProcessor(PillowProcessor):

    def __init__(self, elasticsearch, index_info, doc_prep_fn=None, doc_filter_fn=None):
        self.doc_filter_fn = doc_filter_fn
        self.elasticsearch = elasticsearch
        self.index_info = index_info
        self.doc_transform_fn = doc_prep_fn or identity

    def es_getter(self):
        return self.elasticsearch

    def process_change(self, change):
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
                index=self.index_info.index,
                doc_type=self.index_info.type,
                doc_id=change.id,
                es_getter=self.es_getter,
                name='ElasticProcessor',
                data=doc_ready_to_save,
                update=self._doc_exists(change.id),
            )

    def _doc_exists(self, doc_id):
        return self.elasticsearch.exists(self.index_info.index, self.index_info.type, doc_id)

    def _delete_doc_if_exists(self, doc_id):
        if self._doc_exists(doc_id):
            self.elasticsearch.delete(self.index_info.index, self.index_info.type, doc_id)

    def _datadog_timing(self, step):
        return datadog_bucket_timer('commcare.change_feed.processor.timing', tags=[
            'action:{}'.format(step),
            'index:{}'.format(self.index_info.alias),
        ], timing_buckets=(.03, .1, .3, 1, 3, 10))


def send_to_elasticsearch(index, doc_type, doc_id, es_getter, name, data=None, retries=MAX_RETRIES,
                          except_on_failure=False, update=False, delete=False, es_merge_update=False):
    """
    More fault tolerant es.put method
    kwargs:
        es_merge_update: Set this to True to use Elasticsearch.update instead of Elasticsearch.index
            which merges existing ES doc and current update. If this is set to False, the doc will be replaced

    """
    data = data if data is not None else {}
    current_tries = 0
    while current_tries < retries:
        try:
            if delete:
                es_getter().delete(index, doc_type, doc_id)
            elif update:
                params = {'retry_on_conflict': 2}
                if es_merge_update:
                    es_getter().update(index, doc_type, doc_id, body={"doc": data}, params=params)
                else:
                    es_getter().index(index, doc_type, body=data, id=doc_id, params=params)
            else:
                es_getter().create(index, doc_type, body=data, id=doc_id)
            break
        except ConnectionError as ex:
            current_tries += 1
            pillow_logging.error("[%s] put_robust error %s attempt %d/%d" % (
                name, ex, current_tries, retries))

            if current_tries == retries:
                message = "[%s] Max retry error on %s/%s/%s" % (name, index, doc_type, doc_id)
                if except_on_failure:
                    raise PillowtopIndexingError(message)
                else:
                    pillow_logging.error(message)

            time.sleep(math.pow(RETRY_INTERVAL, current_tries))
        except RequestError as ex:
            error_message = "Pillowtop put_robust error [%s]:\n%s\n\tpath: %s/%s/%s\n\t%s" % (
                name,
                ex.error or "No error message",
                index, doc_type, doc_id,
                list(data))

            if except_on_failure:
                raise PillowtopIndexingError(error_message)
            else:
                pillow_logging.error(error_message)
            break
        except ConflictError:
            break  # ignore the error if a doc already exists when trying to create it in the index
        except NotFoundError:
            break
