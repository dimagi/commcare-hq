from abc import ABCMeta, abstractmethod

from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.util.couch import get_document_class_by_doc_type


class BaseIDProvider(metaclass=ABCMeta):
    @abstractmethod
    def get_doc_ids(self, domain):
        """
        :param domain:
        :return: iterable of tuple(doc_type, list(doc_ids))
        """
        raise NotImplementedError


class DocTypeIDProvider(BaseIDProvider):
    def __init__(self, doc_type):
        self.doc_type = doc_type

    def get_doc_ids(self, domain):
        doc_class = get_document_class_by_doc_type(self.doc_type)
        doc_ids = get_doc_ids_in_domain_by_type(domain, self.doc_type)
        yield doc_class, doc_ids


class ViewKeyGenerator(object):
    def __call__(self, doc_type, domain):
        return self.get_key_args(doc_type, domain)

    def get_key_args(self, doc_type, domain):
        raise NotImplementedError


class DomainKeyGenerator(ViewKeyGenerator):
    def get_key_args(self, doc_type, domain):
        return {
            'key': domain
        }


class ViewIDProvider(BaseIDProvider):
    """ID provider that gets ID's from view rows
    :param doc_type: Doc Type of returned docs
    :param view_name: Name of the view to query
    :param key_generator: (optional) function to call to generate the view key.
                          Arguments passed are ``doc_type`` and ``domain_name``.
                          If not provided the key will be just the domain_name.
    """
    def __init__(self, doc_type, view_name, key_generator):
        self.doc_type = doc_type
        self.view_name = view_name
        self.key_generator = key_generator

    def get_doc_ids(self, domain):
        doc_class = get_document_class_by_doc_type(self.doc_type)
        key_kwargs = self.key_generator(self.doc_type, domain)
        doc_ids = [
            row['id']
            for row in doc_class.get_db().view(
                self.view_name, include_docs=False, reduce=False,
                **key_kwargs)
        ]
        return [(doc_class, doc_ids)]


class WebUserIDProvider(BaseIDProvider):
    doc_type = 'WebUser'

    def get_doc_ids(self, domain):
        from corehq.apps.users.dbaccessors import get_all_user_ids_by_domain
        from corehq.apps.users.models import WebUser
        user_ids = get_all_user_ids_by_domain(
            domain, include_web_users=True, include_mobile_users=False
        )
        yield WebUser, list(user_ids)
