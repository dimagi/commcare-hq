from abc import ABCMeta

import six

from corehq.elastic import get_es_new
from corehq.util.couch_doc_processor import BaseDocProcessor, BulkDocProcessor
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.es_utils import set_index_reindex_settings, \
    set_index_normal_settings, get_index_info_from_pillow, initialize_mapping_if_necessary
from pillowtop.feed.interface import Change
from pillowtop.logger import pillow_logging
from pillowtop.utils import prepare_bulk_payloads, build_bulk_payload


class PillowReindexer(six.with_metaclass(ABCMeta)):
    can_be_reset = False

    def __init__(self, pillow):
        self.pillow = pillow

    def clean(self):
        """
            Cleans the index.

            This can be called prior to reindex to ensure starting from a clean slate.
            Should be overridden on a case-by-case basis by subclasses.
            """
        pass


class PillowChangeProviderReindexer(PillowReindexer):

    def __init__(self, pillow, change_provider):
        super(PillowChangeProviderReindexer, self).__init__(pillow)
        self.change_provider = change_provider

    def reindex(self, start_from=None):
        for change in self.change_provider.iter_all_changes(start_from=start_from):
            self.pillow.process_change(change)


def _clean_index(es, index_info):
    if es.indices.exists(index_info.index):
        es.indices.delete(index=index_info.index)


def _prepare_index_for_reindex(es, index_info):
    if not es.indices.exists(index_info.index):
        es.indices.create(index=index_info.index, body=index_info.meta)
    initialize_mapping_if_necessary(es, index_info)
    set_index_reindex_settings(es, index_info.index)


def _prepare_index_for_usage(es, index_info):
    set_index_normal_settings(es, index_info.index)
    es.indices.refresh(index_info.index)


class ElasticPillowReindexer(PillowChangeProviderReindexer):

    def __init__(self, pillow, change_provider, elasticsearch, index_info):
        super(ElasticPillowReindexer, self).__init__(pillow, change_provider)
        self.es = elasticsearch
        self.index_info = index_info

    def clean(self):
        _clean_index(self.es, self.index_info)

    def reindex(self, start_from=None):
        if not start_from:
            # when not resuming force delete and create the index
            _prepare_index_for_reindex(self.es, self.index_info)

        super(ElasticPillowReindexer, self).reindex(start_from)

        _prepare_index_for_usage(self.es, self.index_info)


class BulkPillowReindexProcessor(BaseDocProcessor):
    def __init__(self, es_client, index_info, pillow):
        super(BulkPillowReindexProcessor, self).__init__(index_info.index)
        self.es = es_client
        self.pillow = pillow
        self.index_info = index_info

    @property
    def unique_key(self):
        return "{}_{}_{}".format(self.slug, self.pillow.pillow_id, 'reindex')

    def process_bulk_docs(self, docs, couchdb):
        changes = [self._doc_to_change(doc, couchdb) for doc in docs]

        # todo: decouple from pillow
        bulk_changes = build_bulk_payload(self.index_info, changes, self.pillow.change_transform)

        max_payload_size = pow(10, 8)  # ~ 100Mb
        payloads = prepare_bulk_payloads(bulk_changes, max_payload_size)
        if len(payloads) > 1:
            pillow_logging.info("%s,payload split into %s parts" % (self.unique_key, len(payloads)))

        pillow_logging.info("%s,sending payload,%s" % (self.unique_key, len(changes)))

        for payload in payloads:
            self.es.bulk(payload)

        return True

    @staticmethod
    def _doc_to_change(doc, couchdb):
        return Change(
            id=doc['_id'], sequence_id=None, document=doc, deleted=False,
            document_store=CouchDocumentStore(couchdb)
        )


class ResumableBulkElasticPillowReindexer(PillowReindexer):
    can_be_reset = True

    def __init__(self, pillow, doc_types, elasticsearch, index_info, chunk_size=1000):
        super(ResumableBulkElasticPillowReindexer, self).__init__(pillow)
        self.es = elasticsearch
        self.index_info = index_info
        self.chunk_size = chunk_size

        self.doc_type_map = dict(
            t if isinstance(t, tuple) else (t.__name__, t) for t in doc_types)
        if len(doc_types) != len(self.doc_type_map):
            raise ValueError("Invalid (duplicate?) doc types")

    def clean(self):
        _clean_index(self.es, self.index_info)

    def reindex(self, reset=False):
        doc_processor = BulkPillowReindexProcessor(self.es, self.index_info, self.pillow)
        processor = BulkDocProcessor(
            self.doc_type_map,
            doc_processor,
            reset=reset,
            chunk_size=self.chunk_size
        )

        if reset or not processor.has_started():
            # when not resuming force delete and create the index
            _prepare_index_for_reindex(self.es, self.index_info)

        processor.run()

        _prepare_index_for_usage(self.es, self.index_info)


def get_default_reindexer_for_elastic_pillow(pillow, change_provider):
    return ElasticPillowReindexer(
        pillow=pillow,
        change_provider=change_provider,
        elasticsearch=get_es_new(),
        index_info=get_index_info_from_pillow(pillow),
    )
