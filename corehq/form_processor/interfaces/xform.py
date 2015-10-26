from dimagi.utils.decorators.memoized import memoized

from ..utils import to_generic, should_use_sql_backend


class XFormInterface(object):

    def __init__(self, domain=None):
        self.domain = domain

    @property
    @memoized
    def backend(self):
        from ..backends.couch import XFormCouch
        from ..backends.sql import XFormSql

        if should_use_sql_backend(self.domain):
            return XFormSql
        else:
            return XFormCouch

    def get_attachment(cls, xform_id, attachment_name):
        return cls.backend.get_attachment(xform_id, attachment_name)

    def get_attachments(cls, xform_id):
        return cls.backend.get_attachments(xform_id)

    def archive(cls, xform_generic, user=None):
        return cls.backend.archive(xform_generic, user=user)

    def unarchive(cls, xform_generic, user=None):
        return cls.backend.unarchive(xform_generic, user=user)

    def get_xml_element(cls, xform_generic):
        return cls.backend.get_xml_element(xform_generic)

    @to_generic
    def get_xform(cls, xform_id):
        return cls.backend.get_xform(xform_id)
