from dimagi.utils.decorators.memoized import memoized

from ..utils import should_use_sql_backend


class FormDbAccessors(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def db_accessor(self):
        from couchforms.models import XFormInstance
        from corehq.form_processor.models import XFormInstanceSQL

        if should_use_sql_backend(self.domain):
            return FormDbAccessorSQL
        else:
            return FormDbAccessorCouch

    def get_forms_by_type(self, type_, recent_first=False, limit=None):
