from django.core.exceptions import ObjectDoesNotExist
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import DocumentStore


class DjangoDocumentStore(DocumentStore):
    """
    An implementation of the DocumentStore that uses the Django ORM.
    """
    def __init__(self, model_class, doc_generator_fn=None, model_manager=None, id_field='pk'):
        self._model_manager = model_manager or model_class.objects
        self._model_class = model_class
        self._doc_generator_fn = doc_generator_fn
        if not doc_generator_fn:
            try:
                self._doc_generator_fn = model_class.to_json
            except AttributeError:
                raise ValueError('DjangoDocumentStore must be supplied with a doc_generator_fn argument')
        self._id_field = id_field
        self._in_query_filter = f'{id_field}__in'

    def get_document(self, doc_id):
        try:
            model = self._model_manager.get(**{self._id_field: doc_id})
            return self._doc_generator_fn(model)
        except ObjectDoesNotExist:
            raise DocumentNotFoundError()

    def iter_document_ids(self):
        return self._model_manager.all().values_list(self._id_field, flat=True)

    def iter_documents(self, ids):
        from dimagi.utils.chunked import chunked
        for chunk in chunked(ids, 500):
            chunk = list([_f for _f in chunk if _f])
            filters = {
                self._in_query_filter: chunk
            }
            for model in self._model_manager.filter(**filters):
                yield self._doc_generator_fn(model)
