from abc import ABCMeta, abstractmethod


class DocumentStore(metaclass=ABCMeta):
    """
    Very basic implementation of a document store.
    """

    @abstractmethod
    def get_document(self, doc_id):
        pass

    @abstractmethod
    def save_document(self, doc_id, document):
        pass

    @abstractmethod
    def delete_document(self, doc_id):
        pass

    def iter_document_ids(self, last_id=None):
        # todo: can convert to @abstractmethod once subclasses handle it
        raise NotImplementedError('this function not yet implemented')

    def iter_documents(self, ids):
        # todo: can convert to @abstractmethod once subclasses handle it
        raise NotImplementedError('this function not yet implemented')


class ReadOnlyDocumentStore(DocumentStore):

    def save_document(self, doc_id, document):
        raise NotImplementedError('This document store is read only!')

    def delete_document(self, doc_id):
        raise NotImplementedError('This document store is read only!')
