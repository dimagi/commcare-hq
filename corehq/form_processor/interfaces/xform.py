from ..utils import to_generic, get_backend


class XFormInterface(object):

    backend = get_backend()

    @classmethod
    def get_attachment(cls, xform_id, attachment_name):
        return cls.backend.get_attachment(xform_id, attachment_name)

    @classmethod
    def get_attachments(cls, xform_id):
        return cls.backend.get_attachments(xform_id)

    @classmethod
    def archive(cls, xform_generic, user=None):
        return cls.backend.archive(xform_generic, user=user)

    @classmethod
    def unarchive(cls, xform_generic, user=None):
        return cls.backend.unarchive(xform_generic, user=user)

    @classmethod
    def get_xml_element(cls, xform_generic):
        return cls.backend.get_xml_element(xform_generic)

    @classmethod
    @to_generic
    def get_xform(cls, xform_id):
        return cls.backend.get_xform(xform_id)

    @classmethod
    @to_generic
    def get_by_doc_type(cls, domain, doc_type):
        return cls.backend.get_by_doc_type(domain, doc_type)
