from abc import ABCMeta, abstractmethod

import six

from dimagi.utils.decorators.memoized import memoized

from ..utils import should_use_sql_backend


class FormAccessors(object):
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

    def get_forms_by_type(self, type_, recent_first=False, limit=None):
        return self.db_accessor.get_forms_by_type(self.domain, type_, recent_first, limit)

    def get_forms_with_attachments(self, form_ids):
        return self.db_accessor.get_forms_with_attachments(form_ids)


class AbstractCaseAccessor(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def get_case(case_id):
        raise NotImplementedError

    @abstractmethod
    def get_cases(case_ids):
        raise NotImplementedError

    @abstractmethod
    def get_case_xform_ids(case_ids):
        raise NotImplementedError


class CaseAccessors(object):
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

    def get_cases(self, case_ids):
        return self.db_accessor.get_cases(case_ids)

    def get_case_xform_ids(self, case_ids):
        return self.db_accessor.get_case_xform_ids(case_ids)
