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
