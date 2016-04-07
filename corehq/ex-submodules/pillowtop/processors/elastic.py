from .interface import PillowProcessor
from pillowtop.listener import send_to_elasticsearch
from pillowtop.logger import pillow_logging


class ElasticProcessor(PillowProcessor):

    def __init__(self, elasticsearch, index_meta, doc_prep_fn):
        self.elasticsearch = elasticsearch
        self.index_meta = index_meta
        self.doc_transform_fn = doc_prep_fn

    def es_getter(self):
        return self.elasticsearch

    def process_change(self, pillow_instance, change, do_set_checkpoint):
        # todo: if deletion - delete
        # prepare doc for es
        doc = change.get_document()
        if doc is None:
            pillow_logging.warning("Unable to get document from change: {}".format(change))
            return

        doc_ready_to_save = self.doc_transform_fn(doc)
        # send it across
        send_to_elasticsearch(
            index=self.index_meta.index,
            doc_type=self.index_meta.type,
            doc_id=change.id,
            es_getter=self.es_getter,
            name=pillow_instance.get_name(),
            data=doc_ready_to_save,
            update=self.elasticsearch.exists(self.index_meta.index, self.index_meta.type, change.id),
        )
