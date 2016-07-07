from abc import ABCMeta, abstractmethod

import six

from corehq.apps.change_feed.document_types import is_deletion
from corehq.elastic import get_es_new
from corehq.util.doc_processor.interface import BaseDocProcessor, BulkDocProcessor
from pillowtop.es_utils import set_index_reindex_settings, \
    set_index_normal_settings, get_index_info_from_pillow, initialize_mapping_if_necessary
from pillowtop.feed.interface import Change
from pillowtop.logger import pillow_logging
from pillowtop.utils import prepare_bulk_payloads, build_bulk_payload


class Reindexer(six.with_metaclass(ABCMeta)):
    def consume_options(self, options):
        """Called from the management command with the command line
        options.

        :param options: command line options dict
        :return: dict of unprocessed options
        """
        return options

    def clean(self):
        """
            Cleans the index.

            This can be called prior to reindex to ensure starting from a clean slate.
            Should be overridden on a case-by-case basis by subclasses.
            """
        pass

    @abstractmethod
    def reindex(self):
        """Perform the reindex"""
        raise NotImplementedError


class PillowReindexer(Reindexer):
    def __init__(self, pillow):
        self.pillow = pillow


class PillowChangeProviderReindexer(PillowReindexer):
    start_from = None

    def __init__(self, pillow, change_provider):
        super(PillowChangeProviderReindexer, self).__init__(pillow)
        self.change_provider = change_provider

    def consume_options(self, options):
        self.start_from = options.pop("start_from", None)
        return options

    def reindex(self):
        for change in self.change_provider.iter_all_changes(start_from=self.start_from):
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

    def reindex(self):
        if not self.start_from:
            # when not resuming force delete and create the index
            _prepare_index_for_reindex(self.es, self.index_info)

        super(ElasticPillowReindexer, self).reindex()

        _prepare_index_for_usage(self.es, self.index_info)


class BulkPillowReindexProcessor(BaseDocProcessor):
    def __init__(self, es_client, index_info, doc_filter=None, doc_transform=None):
        self.doc_transform = doc_transform
        self.doc_filter = doc_filter
        self.es = es_client
        self.index_info = index_info

    def should_process(self, doc):
        if self.doc_filter:
            return not self.doc_filter(doc)
        return True

    def process_bulk_docs(self, docs):
        if len(docs) == 0:
            return True

        changes = [self._doc_to_change(doc) for doc in docs]

        bulk_changes = build_bulk_payload(self.index_info, changes, self.doc_transform)

        max_payload_size = pow(10, 8)  # ~ 100Mb
        payloads = prepare_bulk_payloads(bulk_changes, max_payload_size)
        if len(payloads) > 1:
            pillow_logging.info("payload split into %s parts" % len(payloads))

        pillow_logging.info("sending payload,%s" % len(changes))

        for payload in payloads:
            self.es.bulk(payload)

        return True

    @staticmethod
    def _doc_to_change(doc):
        return Change(
            id=doc['_id'], sequence_id=None, document=doc, deleted=is_deletion(doc['doc_type'])
        )


class ResumableBulkElasticPillowReindexer(Reindexer):
    reset = False

    def __init__(self, doc_provider, elasticsearch, index_info,
                 doc_filter=None, doc_transform=None, chunk_size=1000):
        self.doc_provider = doc_provider
        self.es = elasticsearch
        self.index_info = index_info
        self.chunk_size = chunk_size
        self.doc_processor = BulkPillowReindexProcessor(
            self.es, self.index_info, doc_filter, doc_transform
        )

    def consume_options(self, options):
        self.reset = options.pop("reset", False)
        return options

    def clean(self):
        _clean_index(self.es, self.index_info)

    def reindex(self):
        processor = BulkDocProcessor(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )

        if self.reset or not processor.has_started():
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
