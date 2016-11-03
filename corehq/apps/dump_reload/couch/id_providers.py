from abc import ABCMeta, abstractmethod

import six

from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.util.couch import get_document_class_by_doc_type


class BaseIDProvider(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_doc_ids(self, domain):
        raise NotImplementedError


class DocTypeIDProvider(BaseIDProvider):
    def __init__(self, doc_types):
        self.doc_types = doc_types

    def get_doc_ids(self, domain):
        for doc_type in self.doc_types:
            doc_class = get_document_class_by_doc_type(doc_type)
            doc_ids = get_doc_ids_in_domain_by_type(domain, doc_type)
            yield doc_class, doc_ids
