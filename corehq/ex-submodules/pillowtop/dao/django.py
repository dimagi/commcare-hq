from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.exceptions import ObjectDoesNotExist
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import DocumentStore


class DjangoDocumentStore(DocumentStore):
    """
    An implementation of the DocumentStore that uses the Django ORM.
    """

    def __init__(self, model_class, doc_generator_fn, model_generator_fn=None, model_manager=None):
        self._model_manager = model_manager or model_class.objects
        self._model_class = model_class
        self._doc_generator_fn = doc_generator_fn
        if model_generator_fn is None:
            # the default generator just assumes the dict is flat set of model fields
            model_generator_fn = lambda document_dict: self._model_class(**document_dict)
        self._model_generator_fn = model_generator_fn

    def get_document(self, doc_id):
        try:
            model = self._model_manager.get(pk=doc_id)
            return self._doc_generator_fn(model)
        except ObjectDoesNotExist:
            raise DocumentNotFoundError()

    def save_document(self, doc_id, document):
        document['pk'] = doc_id
        instance = self._model_generator_fn(document)
        instance.save()

    def delete_document(self, doc_id):
        self._model_manager.filter(pk=doc_id).delete()

    def iter_document_ids(self, last_id=None):
        # todo: support last_id
        return self._model_manager.all().values_list('id', flat=True)

    def iter_documents(self, ids):
        from dimagi.utils.chunked import chunked
        for chunk in chunked(ids, 500):
            chunk = list([_f for _f in chunk if _f])
            for model in self._model_manager.filter(pk__in=chunk):
                yield self._doc_generator_fn(model)
