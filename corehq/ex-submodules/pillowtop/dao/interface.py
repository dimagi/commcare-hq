from abc import ABCMeta, abstractmethod


class DocumentStore(metaclass=ABCMeta):
    """
    Very basic implementation of a document store.
    """

    @abstractmethod
    def get_document(self, doc_id):
        pass

    @abstractmethod
    def iter_document_ids(self, last_id=None):
        raise NotImplementedError('this function not yet implemented')

    @abstractmethod
    def iter_documents(self, ids):
        raise NotImplementedError('this function not yet implemented')


class ReadOnlyDocumentStore(DocumentStore):
    pass
