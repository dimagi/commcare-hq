from __future__ import absolute_import
from datetime import datetime
import math
import time

from elasticsearch.exceptions import RequestError, ConnectionError, NotFoundError, ConflictError
import six

from pillowtop.utils import (
        ensure_matched_revisions, ensure_document_exists, prepare_bulk_payloads)
from pillowtop.exceptions import PillowtopIndexingError
from pillowtop.logger import pillow_logging
from .interface import PillowProcessor


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

    def process_change(self, pillow_instance, change):
        if change.deleted and change.id:
            self._delete_doc_if_exists(change.id)
            return

        doc = self._doc_to_save(change)
        if doc:
            # send it across
            send_to_elasticsearch(
                index=self.index_info.index,
                doc_type=self.index_info.type,
                doc_id=change.id,
                es_getter=self.es_getter,
                name=pillow_instance.get_name(),
                data=doc,
                update=self._doc_exists(change.id),
            )

    def _doc_to_save(self, change):
        doc = change.get_document()

        ensure_document_exists(change)
        ensure_matched_revisions(change)

        if doc is None or (self.doc_filter_fn and self.doc_filter_fn(doc)):
            return

        # prepare doc for es
        return self.doc_transform_fn(doc)

    def _doc_exists(self, doc_id):
        return self.elasticsearch.exists(self.index_info.index, self.index_info.type, doc_id)

    def _delete_doc_if_exists(self, doc_id):
        if self._doc_exists(doc_id):
            self.elasticsearch.delete(self.index_info.index, self.index_info.type, doc_id)


class BulkElasticProcessor(ElasticProcessor):
    def __init__(self, elasticsearch, index_info, doc_prep_fn=None, doc_filter_fn=None):
        super(BulkElasticProcessor, self).__init__(elasticsearch, index_info, doc_prep_fn, doc_filter_fn)
        self.changes = {}

    def process_change(self, pillow_instance, change):
        self.changes[change.id] = change

    def commit_changes(self):
        # pretty similar to build_bulk_payload, but that uses changes and doesn't ensure revisions
        payload = []
        for change in six.itervalues(self.changes):
            doc_id = change.id
            if change.deleted and change.id:
                payload.append({
                    "delete": {
                        "_index": self.index_info.index,
                        "_type": self.index_info.type,
                        "_id": doc_id
                    }
                })
                continue

            errors = dict()
            try:
                doc = self._doc_to_save(change)
                if doc:
                    payload.append({
                        "index": {
                            "_index": self.index_info.index,
                            "_type": self.index_info.type,
                            "_id": doc_id
                        }
                    })
                    payload.append(doc)
            except Exception as e:
                errors[doc_id] = (self.changes[doc_id], e)

        payloads = prepare_bulk_payloads(payload, 10 ** 7)

        for payload in payloads:
            # aggregate results and return docs with errors to be put in pillow error
            results = self._send_payload_with_retries(payload)
            errors.update(results)

        return errors

    def _send_payload_with_retries(self, payload):
        pillow_logging.info("Sending payload to ES")

        retries = 0
        bulk_start = datetime.utcnow()
        while retries < 3:
            if retries:
                retry_time = (datetime.utcnow() - bulk_start).seconds + retries * 15
                pillow_logging.warning("\tRetrying in %s seconds" % retry_time)
                time.sleep(retry_time)
                pillow_logging.warning("\tRetrying now ...")
                # reset timestamp when looping again
                bulk_start = datetime.utcnow()

            try:
                res = self.elasticsearch.bulk(payload)
            except Exception:
                retries += 1
                pillow_logging.exception("\tException sending payload to ES")
            else:
                return {
                    value['_id']: (self.changes[value['_id']], value['error'])
                    for doc_result in res['items']
                    for value in doc_result.values()
                    if value.get('error')
                }

        return False


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
                data.keys())

            if except_on_failure:
                raise PillowtopIndexingError(error_message)
            else:
                pillow_logging.error(error_message)
            break
        except ConflictError:
            break  # ignore the error if a doc already exists when trying to create it in the index
        except NotFoundError:
            break
