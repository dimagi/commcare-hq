from abc import ABCMeta

from corehq.elastic import get_es_new
from corehq.util.couch_doc_processor import BaseDocProcessor, CouchDocumentProcessor
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.es_utils import set_index_reindex_settings, \
    set_index_normal_settings, get_index_info_from_pillow, initialize_mapping_if_necessary
from pillowtop.feed.interface import Change

import six


class PillowReindexer(six.with_metaclass(ABCMeta)):
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


def get_default_reindexer_for_elastic_pillow(pillow, change_provider):
    return ElasticPillowReindexer(
        pillow=pillow,
        change_provider=change_provider,
        elasticsearch=get_es_new(),
        index_info=get_index_info_from_pillow(pillow),
    )
