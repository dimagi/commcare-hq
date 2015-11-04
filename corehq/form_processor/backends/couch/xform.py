from couchdbkit import ResourceNotFound

from couchforms.models import doc_types, XFormInstance
from couchforms.exceptions import UnexpectedDeletedXForm
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.form_processor.exceptions import XFormNotFound


class XFormCouch(object):

    @staticmethod
    def get_attachment(xform_id, attachment_name):
        return XFormInstance.get_db().fetch_attachment(xform_id, attachment_name)

    @classmethod
    def archive(cls, xform_generic, user=None):
        xform = cls._get_xform(xform_generic.id)
        return xform.archive(user=user)

    @classmethod
    def unarchive(cls, xform_generic, user=None):
        xform = cls._get_xform(xform_generic.id)
        return xform.unarchive(user=user)

    @classmethod
    def get_xml_element(cls, xform_generic):
        xform = cls._get_xform(xform_generic.id)
        return xform.get_xml_element()

    @classmethod
    def get_xform(cls, xform_id):
        try:
            return cls._get_xform(xform_id)
        except ResourceNotFound:
            raise XFormNotFound

    @staticmethod
    def _get_xform(xform_id):
        db = XFormInstance.get_db()
        doc = db.get(xform_id)
        if doc['doc_type'] in doc_types():
            return doc_types()[doc['doc_type']].wrap(doc)
        if doc['doc_type'] == "%s%s" % (XFormInstance.__name__, DELETED_SUFFIX):
            raise UnexpectedDeletedXForm(xform_id)
        raise ResourceNotFound(xform_id)
