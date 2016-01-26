from abc import ABCMeta, abstractmethod
from collections import namedtuple

import six

from dimagi.utils.decorators.memoized import memoized

from ..utils import should_use_sql_backend


class AbstractFormAccessor(six.with_metaclass(ABCMeta)):
    """
    Contract for common methods expected on FormAccessor(SQL/Couch). All methods
    should be static or classmethods.
    """
    @abstractmethod
    def get_form(form_id):
        raise NotImplementedError

    @abstractmethod
    def get_forms_by_type(domain, type_, limit, recent_first=False):
        raise NotImplementedError

    @abstractmethod
    def get_with_attachments(form_id):
        raise NotImplementedError

    @abstractmethod
    def save_new_form(form):
        raise NotImplementedError

    @abstractmethod
    def update_form_problem_and_state(form):
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

    def get_forms_by_type(self, type_, limit, recent_first=False):
        return self.db_accessor.get_forms_by_type(self.domain, type_, limit, recent_first)

    def get_with_attachments(self, form_id):
        return self.db_accessor.get_with_attachments(form_id)

    def save_new_form(self, form):
        self.db_accessor.save_new_form(form)

    def update_form_problem_and_state(self, form):
        self.db_accessor.update_form_problem_and_state(form)

    def get_deleted_forms_for_user(self, domain, user_id, ids_only=False):
        return self.db_accessor.get_deleted_forms_for_user(domain, user_id, ids_only=False)

    def get_forms_for_user(self, domain, user_id, ids_only=False):
        return self.db_accessor.get_forms_for_user(domain, user_id, ids_only)


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
    def get_open_case_ids(domain, owner_id):
        raise NotImplementedError

    @abstractmethod
    def get_closed_case_ids(domain, owner_id):
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
    def get_last_modified_dates(domain, case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_all_reverse_indices_info(domain, case_ids):
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

    def get_case_xform_ids(self, case_ids):
        return self.db_accessor.get_case_xform_ids(case_ids)

    def get_case_ids_in_domain(self, type=None):
        return self.db_accessor.get_case_ids_in_domain(self.domain, type)

    def get_case_ids_by_owners(self, owner_ids):
        return self.db_accessor.get_case_ids_in_domain_by_owners(self.domain, owner_ids)

    def get_open_case_ids(self, owner_id):
        return self.db_accessor.get_open_case_ids(self.domain, owner_id)

    def get_case_ids_modified_with_owner_since(self, owner_id, reference_date):
        return self.db_accessor.get_case_ids_modified_with_owner_since(self.domain, owner_id, reference_date)

    def get_extension_case_ids(self, case_ids):
        return self.db_accessor.get_extension_case_ids(self.domain, case_ids)

    def get_indexed_case_ids(self, case_ids):
        return self.db_accessor.get_indexed_case_ids(self.domain, case_ids)

    def get_last_modified_dates(self, case_ids):
        return self.db_accessor.get_last_modified_dates(self.domain, case_ids)

    def get_closed_case_ids(self, owner_id):
        return self.db_accessor.get_closed_case_ids(self.domain, owner_id)

    def get_all_reverse_indices_info(self, case_ids):
        return self.db_accessor.get_all_reverse_indices_info(self.domain, case_ids)

CaseIndexInfo = namedtuple(
    'CaseIndexInfo', ['case_id', 'identifier', 'referenced_id', 'referenced_type', 'relationship']
)
