from corehq.util.elastic import ensure_index_deleted, ensure_production_index_deleted
from pillowtop.es_utils import create_index_and_set_settings_normal, set_index_reindex_settings, \
    set_index_normal_settings, get_index_info_from_pillow
from pillowtop.pillow.interface import PillowRuntimeContext


class PillowReindexer(object):

    def __init__(self, pillow, change_provider):
        self.pillow = pillow
        self.change_provider = change_provider

    def reindex(self, start_from=None):
        reindexer_context = PillowRuntimeContext(do_set_checkpoint=False)
        for change in self.change_provider.iter_changes(start_from=start_from):
            self.pillow.processor(change, reindexer_context)


class ElasticPillowReindexer(PillowReindexer):

    def __init__(self, pillow, change_provider, elasticsearch, index_info):
        super(ElasticPillowReindexer, self).__init__(pillow, change_provider)
        self.es = elasticsearch
        self.index_info = index_info

    def reindex(self, start_from=None):
        if not start_from:
            # when not resuming force delete and create the index
            self._delete_and_prepare_index_for_reindex()

        reindexer_context = PillowRuntimeContext(do_set_checkpoint=False)
        for change in self.change_provider.iter_changes(start_from=start_from):
            self.pillow.processor(change, reindexer_context)

        self._prepare_index_for_usage()

    def _delete_and_prepare_index_for_reindex(self):
        ensure_production_index_deleted(self.index_info.index)
        self.es.indices.create(index=self.index_info.index, body=self.index_info.meta)
        set_index_reindex_settings(self.es, self.index_info.index)

    def _prepare_index_for_usage(self):
        set_index_normal_settings(self.es, self.index_info.index)
        self.es.indices.refresh(self.index_info.index)


def get_default_reindexer_for_elastic_pillow(pillow, change_provider):
    return ElasticPillowReindexer(
        pillow=pillow,
        change_provider=change_provider,
        elasticsearch=pillow.get_es_new(),
        index_info=get_index_info_from_pillow(pillow),
    )
