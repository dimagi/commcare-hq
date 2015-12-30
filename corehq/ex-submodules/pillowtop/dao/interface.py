from abc import ABCMeta, abstractmethod


class DocumentStore(object):
    """
    Very basic implementation of a document store.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_document(self, doc_id):
        pass

    @abstractmethod
    def save_document(self, doc_id, document):
        pass

    @abstractmethod
    def delete_document(self, doc_id):
        pass
