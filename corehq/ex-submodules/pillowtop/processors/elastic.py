from .interface import PillowProcessor
from pillowtop.listener import send_to_elasticsearch
from pillowtop.logger import pillow_logging


IDENTITY_FN = lambda x: x


class ElasticProcessor(PillowProcessor):

    def __init__(self, elasticsearch, index_info, doc_prep_fn=None):
        self.elasticsearch = elasticsearch
        self.index_info = index_info
        self.doc_transform_fn = doc_prep_fn or IDENTITY_FN

    def es_getter(self):
        return self.elasticsearch

    def process_change(self, pillow_instance, change, do_set_checkpoint):
        if change.deleted and change.id:
            self._delete_doc_if_exists(change.id)
            return

        # prepare doc for es
        doc = change.get_document()
        if doc is None:
            pillow_logging.warning("Unable to get document from change: {}".format(change))
            return

        doc_ready_to_save = self.doc_transform_fn(doc)
        # send it across
        send_to_elasticsearch(
            index=self.index_info.index,
            doc_type=self.index_info.type,
            doc_id=change.id,
            es_getter=self.es_getter,
            name=pillow_instance.get_name(),
            data=doc_ready_to_save,
            update=self._doc_exists(change.id),
        )

    def _doc_exists(self, doc_id):
        return self.elasticsearch.exists(self.index_info.index, self.index_info.type, doc_id)

    def _delete_doc_if_exists(self, doc_id):
        if self._doc_exists(doc_id):
            self.elasticsearch.delete(self.index_info.index, self.index_info.type, doc_id)
