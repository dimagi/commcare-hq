from couchdbkit import ResourceNotFound

from couchforms.models import doc_types, XFormInstance, XFormError
from couchforms.exceptions import UnexpectedDeletedXForm
from dimagi.utils.couch.undo import DELETED_SUFFIX

from ..utils import to_generic
from ..exceptions import XFormNotFound


class XFormInterface(object):

    @staticmethod
    @to_generic
    def create_from_generic(generic_xform, generic_attachment=None):
        xform = XFormInstance.from_generic(generic_xform)
        xform.save()
        if generic_attachment:
            xform.put_attachment(**generic_attachment.to_json())
        return xform

    @staticmethod
    def get_attachment(xform_id, attachment_name):
        return XFormInstance.get_db().fetch_attachment(xform_id, attachment_name)

    @classmethod
    def get_attachments(cls, xform_id):
        xform = cls._get_xform(xform_id)
        return xform.attachments

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
    @to_generic
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

    @staticmethod
    @to_generic
    def get_by_doc_type(domain, doc_type):
        return XFormError.view(
            'domain/docs',
            startkey=[domain, doc_type],
            endkey=[domain, doc_type, {}],
            reduce=False,
            include_docs=True,
        ).all()

    @classmethod
    @to_generic
    def update_properties(cls, xform_generic, **properties):
        xform = cls._get_xform(xform_generic.id)
        for prop, value in properties.iteritems():
            setattr(xform, prop, value)
        xform.save()
        return xform
