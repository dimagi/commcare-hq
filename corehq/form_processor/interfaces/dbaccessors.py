from abc import ABCMeta, abstractmethod
from collections import namedtuple

import six
from StringIO import StringIO

from corehq.util.quickcache import quickcache
from dimagi.utils.chunked import chunked
from dimagi.utils.decorators.memoized import memoized

from ..utils import should_use_sql_backend


CaseIndexInfo = namedtuple(
    'CaseIndexInfo', ['case_id', 'identifier', 'referenced_id', 'referenced_type', 'relationship']
)


class AttachmentContent(namedtuple('AttachmentContent', ['content_type', 'content_stream'])):

    @property
    def content_body(self):
        # WARNING an error is likely if this property is accessed more than once
        # self.content_stream is a file-like object, and most file-like objects
        # will error on subsequent read attempt once closed (by with statement).
        with self.content_stream as stream:
            return stream.read()


class AbstractFormAccessor(six.with_metaclass(ABCMeta)):
    """
    Contract for common methods expected on FormAccessor(SQL/Couch). All methods
    should be static or classmethods.
    """
    @abstractmethod
    def form_exists(form_id, domain=None):
        raise NotImplementedError

    @abstractmethod
    def get_form(form_id):
        raise NotImplementedError

    @abstractmethod
    def get_forms(form_ids, ordered=False):
        raise NotImplementedError

    @abstractmethod
    def get_form_ids_for_user(domain, form_ids):
        raise NotImplementedError

    @abstractmethod
    def get_deleted_form_ids_for_user(domain, user_id):
        raise NotImplementedError

    @abstractmethod
    def get_form_ids_in_domain_by_type(domain, type_):
        raise NotImplementedError

    @abstractmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        raise NotImplementedError

    @abstractmethod
    def get_with_attachments(form_id):
        raise NotImplementedError

    @abstractmethod
    def get_attachment_content(form_id, attachment_name):
        """
        :param attachment_id:
        :return: AttachmentContent object
        """
        raise NotImplementedError

    @abstractmethod
    def save_new_form(form):
        raise NotImplementedError

    @abstractmethod
    def update_form_problem_and_state(form):
        raise NotImplementedError

    @abstractmethod
    def forms_have_multimedia(domain, app_id, xmlns):
        raise NotImplementedError

    @abstractmethod
    def soft_delete_forms(domain, form_ids, deletion_date=None, deletion_id=None):
        raise NotImplementedError


class FormAccessors(object):
    """
    Facade for Form DB access that proxies method calls to SQL or Couch version
    """

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
        from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
        if should_use_sql_backend(self.domain):
            return FormAccessorSQL
        else:
            return FormAccessorCouch

    def get_form(self, form_id):
        return self.db_accessor.get_form(form_id)

    def get_forms(self, form_ids, ordered=False):
        """
        :param form_ids: list of form_ids to fetch
        :type ordered:   True if the list of returned forms should have the same order
                         as the list of form_ids passed in
        """
        return self.db_accessor.get_forms(form_ids, ordered=ordered)

    def iter_forms(self, form_ids):
        for chunk in chunked(form_ids, 100):
            chunk = list(filter(None, chunk))
            for form in self.get_forms(chunk):
                yield form

    def form_exists(self, form_id):
        return self.db_accessor.form_exists(form_id, domain=self.domain)

    def get_all_form_ids_in_domain(self):
        return self.db_accessor.get_form_ids_in_domain_by_type(self.domain, 'XFormInstance')

    def get_forms_by_type(self, type_, limit, recent_first=False):
        return self.db_accessor.get_forms_by_type(self.domain, type_, limit, recent_first)

    def get_with_attachments(self, form_id):
        return self.db_accessor.get_with_attachments(form_id)

    def save_new_form(self, form):
        self.db_accessor.save_new_form(form)

    def update_form_problem_and_state(self, form):
        self.db_accessor.update_form_problem_and_state(form)

    def get_deleted_form_ids_for_user(self, domain, user_id):
        return self.db_accessor.get_deleted_form_ids_for_user(domain, user_id)

    def get_form_ids_for_user(self, user_id):
        return self.db_accessor.get_form_ids_for_user(self.domain, user_id)

    def get_attachment_content(self, form_id, attachment_name):
        return self.db_accessor.get_attachment_content(form_id, attachment_name)

    def forms_have_multimedia(self, app_id, xmlns):
        return self.db_accessor.forms_have_multimedia(self.domain, app_id, xmlns)

    def soft_delete_forms(self, form_ids, deletion_date=None, deletion_id=None):
        return self.db_accessor.soft_delete_forms(self.domain, form_ids, deletion_date, deletion_id)


class AbstractCaseAccessor(six.with_metaclass(ABCMeta)):
    """
    Contract for common methods expected on CaseAccessor(SQL/Couch). All methods
    should be static or classmethods.
    """
    @abstractmethod
    def get_case(case_id):
        raise NotImplementedError

    @abstractmethod
    def get_cases(case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_case_xform_ids(case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_case_ids_in_domain(domain, type=None):
        raise NotImplementedError

    @abstractmethod
    def get_case_ids_in_domain_by_owners(domain, owner_ids):
        raise NotImplementedError

    @abstractmethod
    def get_open_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError

    @abstractmethod
    def get_closed_case_ids_for_owner(domain, owner_id):
        raise NotImplementedError

    @abstractmethod
    def get_open_case_ids_in_domain_by_type(domain, case_type, owner_ids=None):
        raise NotImplementedError

    @abstractmethod
    def get_case_ids_modified_with_owner_since(domain, owner_id, reference_date):
        raise NotImplementedError

    @abstractmethod
    def get_extension_case_ids(domain, case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_indexed_case_ids(domain, case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_reverse_indexed_cases(domain, case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_last_modified_dates(domain, case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_all_reverse_indices_info(domain, case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_attachment_content(case_id, attachment_id):
        """
        :param attachment_id:
        :return: AttachmentContent object
        """
        raise NotImplementedError

    @abstractmethod
    def get_case_by_domain_hq_user_id(domain, user_id, case_type):
        raise NotImplementedError

    @abstractmethod
    def get_case_types_for_domain(domain):
        raise NotImplementedError

    @abstractmethod
    def get_cases_by_external_id(domain, external_id, case_type=None):
        raise NotImplementedError

    @abstractmethod
    def soft_delete_cases(domain, case_ids, deletion_date=None, deletion_id=None):
        raise NotImplementedError


class CaseAccessors(object):
    """
    Facade for Case DB access that proxies method calls to SQL or Couch version
    """

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
        if should_use_sql_backend(self.domain):
            return CaseAccessorSQL
        else:
            return CaseAccessorCouch

    def get_case(self, case_id):
        return self.db_accessor.get_case(case_id)

    def get_cases(self, case_ids, ordered=False):
        return self.db_accessor.get_cases(case_ids, ordered=ordered)

    def iter_cases(self, case_ids):
        for chunk in chunked(case_ids, 100):
            chunk = list(filter(None, chunk))
            for case in self.get_cases(chunk):
                yield case

    def get_case_xform_ids(self, case_ids):
        return self.db_accessor.get_case_xform_ids(case_ids)

    def get_case_ids_in_domain(self, type=None):
        return self.db_accessor.get_case_ids_in_domain(self.domain, type)

    def get_case_ids_by_owners(self, owner_ids, closed=None):
        """
        get case_ids for open, closed, or all cases in a domain
        that belong to a list of owner_ids

        owner_ids: a list of owner ids to filter on.
            A case matches if it belongs to any of them.
        closed: True (only closed cases), False (only open cases), or None (all)

        returns a list of case_ids
        """
        return self.db_accessor.get_case_ids_in_domain_by_owners(self.domain, owner_ids)

    def get_open_case_ids_for_owner(self, owner_id):
        return self.db_accessor.get_open_case_ids_for_owner(self.domain, owner_id)

    def get_open_case_ids_in_domain_by_type(self, case_type, owner_ids=None):
        return self.db_accessor.get_open_case_ids_in_domain_by_type(self.domain, case_type, owner_ids)

    def get_case_ids_modified_with_owner_since(self, owner_id, reference_date):
        return self.db_accessor.get_case_ids_modified_with_owner_since(self.domain, owner_id, reference_date)

    def get_extension_case_ids(self, case_ids):
        return self.db_accessor.get_extension_case_ids(self.domain, case_ids)

    def get_indexed_case_ids(self, case_ids):
        return self.db_accessor.get_indexed_case_ids(self.domain, case_ids)

    def get_last_modified_dates(self, case_ids):
        return self.db_accessor.get_last_modified_dates(self.domain, case_ids)

    def get_closed_case_ids_for_owner(self, owner_id):
        return self.db_accessor.get_closed_case_ids_for_owner(self.domain, owner_id)

    def get_all_reverse_indices_info(self, case_ids):
        return self.db_accessor.get_all_reverse_indices_info(self.domain, case_ids)

    def get_attachment_content(self, case_id, attachment_id):
        return self.db_accessor.get_attachment_content(case_id, attachment_id)

    def get_case_by_domain_hq_user_id(self, user_id, case_type):
        return self.db_accessor.get_case_by_domain_hq_user_id(self.domain, user_id, case_type)

    def get_cases_by_external_id(self, external_id, case_type=None):
        return self.db_accessor.get_cases_by_external_id(self.domain, external_id, case_type)

    def soft_delete_cases(self, case_ids, deletion_date=None, deletion_id=None):
        return self.db_accessor.soft_delete_cases(self.domain, case_ids, deletion_date, deletion_id)

    def get_extension_chain(self, case_ids):
        assert isinstance(case_ids, list)
        get_extension_case_ids = self.db_accessor.get_extension_case_ids

        incoming_extensions = set(get_extension_case_ids(self.domain, case_ids))
        all_extension_ids = set(incoming_extensions)
        new_extensions = set(incoming_extensions)
        while new_extensions:
            new_extensions = (
                set(get_extension_case_ids(self.domain, list(new_extensions))) -
                all_extension_ids
            )
            all_extension_ids = all_extension_ids | new_extensions
        return all_extension_ids

    @quickcache(['self.domain'], timeout=30 * 60)
    def get_case_types(self):
        return self.db_accessor.get_case_types_for_domain(self.domain)


def get_cached_case_attachment(domain, case_id, attachment_id, is_image=False):
    attachment_cache_key = "%(case_id)s_%(attachment)s" % {
        "case_id": case_id,
        "attachment": attachment_id
    }

    from dimagi.utils.django.cached_object import CachedObject, CachedImage
    cobject = CachedImage(attachment_cache_key) if is_image else CachedObject(attachment_cache_key)
    if not cobject.is_cached():
        content = CaseAccessors(domain).get_attachment_content(case_id, attachment_id)
        stream = StringIO(content.content_body)
        metadata = {'content_type': content.content_type}
        cobject.cache_put(stream, metadata)

    return cobject


class AbstractLedgerAccessor(six.with_metaclass(ABCMeta)):

    @abstractmethod
    def get_transactions_for_consumption(domain, case_id, product_id, section_id, window_start, window_end):
        raise NotImplementedError

    @abstractmethod
    def get_ledger_value(case_id, section_id, entry_id):
        raise NotImplementedError

    @abstractmethod
    def get_ledger_transactions_for_case(case_id, section_id=None, entry_id=None):
        """
        :return: List of transactions orderd by date ascending
        """
        raise NotImplementedError

    @abstractmethod
    def get_latest_transaction(case_id, section_id, entry_id):
        raise NotImplementedError\

    @abstractmethod
    def get_current_ledger_state(case_ids, ensure_form_id=False):
        """
        Given a list of case IDs return a dict of all current ledger data of the following format:
        {
            "case_id": {
                "section_id": {
                     "product_id": StockState,
                     "product_id": StockState,
                     ...
                },
                ...
            },
            ...
        }
        """
        raise NotImplementedError


class LedgerAccessors(object):
    """
    Facade for Ledger DB access that proxies method calls to SQL or Couch version
    """

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
        from corehq.form_processor.backends.couch.dbaccessors import LedgerAccessorCouch
        if should_use_sql_backend(self.domain):
            return LedgerAccessorSQL
        else:
            return LedgerAccessorCouch

    def get_transactions_for_consumption(self, case_id, product_id, section_id, window_start, window_end):
        return self.db_accessor.get_transactions_for_consumption(
            self.domain, case_id, product_id, section_id, window_start, window_end
        )

    def get_ledger_value(self, case_id, section_id, entry_id):
        return self.db_accessor.get_ledger_value(case_id, section_id, entry_id)

    def get_ledger_transactions_for_case(self, case_id, section_id=None, entry_id=None):
        return self.db_accessor.get_ledger_transactions_for_case(case_id, section_id, entry_id)

    def get_latest_transaction(self, case_id, section_id, entry_id):
        return self.db_accessor.get_latest_transaction(case_id, section_id, entry_id)

    def get_ledger_values_for_case(self, case_id):
        return self.db_accessor.get_ledger_values_for_case(case_id)

    def get_current_ledger_state(self, case_ids):
        if not case_ids:
            return {}
        return self.db_accessor.get_current_ledger_state(case_ids)

    def get_case_ledger_state(self, case_id, ensure_form_id=False):
        return self.db_accessor.get_current_ledger_state([case_id], ensure_form_id=ensure_form_id)[case_id]
