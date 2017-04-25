from abc import ABCMeta, abstractmethod

import six

from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.util.couch import get_document_class_by_doc_type


class BaseIDProvider(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_doc_ids(self, domain):
        """
        :param domain:
        :return: iterable of tuple(doc_type, list(doc_ids))
        """
        raise NotImplementedError


class DocTypeIDProvider(BaseIDProvider):
    def __init__(self, doc_types):
        self.doc_types = doc_types

    def get_doc_ids(self, domain):
        for doc_type in self.doc_types:
            doc_class = get_document_class_by_doc_type(doc_type)
            doc_ids = get_doc_ids_in_domain_by_type(domain, doc_type)
            yield doc_class, doc_ids


class ViewIDProvider(BaseIDProvider):
    """ID provider that gets ID's from view rows
    :param doc_type: Doc Type of returned docs
    :param view_name: Name of the view to query
    :param key_generator: (optional) function to call to generate the view key.
                          Arguments passed are ``doc_type`` and ``domain_name``.
                          If not provided the key will be just the domain_name.
    """
    def __init__(self, doc_type, view_name, key_generator=None):
        self.doc_type = doc_type
        self.view_name = view_name
        self.key_generator = key_generator

    def get_doc_ids(self, domain):
        doc_class = get_document_class_by_doc_type(self.doc_type)
        key = self.key_generator(self.doc_type, domain) if self.key_generator else domain
        doc_ids = [
            row['id']
            for row in doc_class.get_db().view(self.view_name, key=key, include_docs=False)
        ]
        return [(doc_class, doc_ids)]


class UserIDProvider(BaseIDProvider):
    def __init__(self, include_mobile_users=True, include_web_users=True):
        self.include_mobile_users = include_mobile_users
        self.include_web_users = include_web_users

    def get_doc_ids(self, domain):
        from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain
        from corehq.apps.users.models import CommCareUser
        from corehq.apps.users.models import WebUser
        if self.include_mobile_users:
            user_ids = get_all_user_ids_by_domain(
                domain, include_web_users=False, include_mobile_users=True
            )
            yield CommCareUser, list(user_ids)

        if self.include_web_users:
            user_ids = get_all_user_ids_by_domain(
                domain, include_web_users=True, include_mobile_users=False
            )
            yield WebUser, list(user_ids)


class SyncLogIDProvider(BaseIDProvider):
    def get_doc_ids(self, domain):
        from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain
        from casexml.apps.phone.models import SyncLog
        for user_id in get_all_user_ids_by_domain(domain):
            rows = SyncLog.view(
                "phone/sync_logs_by_user",
                startkey=[user_id],
                endkey=[user_id, {}],
                reduce=False,
                include_docs=False,
            )
            yield SyncLog, [row['id'] for row in rows]
