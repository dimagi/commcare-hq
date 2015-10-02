from couchdbkit import ResourceNotFound
from dimagi.utils.couch.undo import DELETED_SUFFIX
from casexml.apps.case.models import CommCareCase

from couchforms.util import process_xform
from couchforms.models import doc_types, XFormInstance, XFormError
from couchforms.exceptions import UnexpectedDeletedXForm

from .utils import to_generic


class FormProcessorInterface(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

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
    def archive_xform(cls, xform_generic, user=None):
        xform = cls._get_xform(xform_generic.id)
        return xform.archive(user=user)

    @classmethod
    def unarchive_xform(cls, xform_generic, user=None):
        xform = cls._get_xform(xform_generic.id)
        return xform.unarchive(user=user)

    @classmethod
    def get_xml_element(cls, xform_generic):
        xform = cls._get_xform(xform_generic.id)
        return xform.get_xml_element()

    @classmethod
    @to_generic
    def get_xform(cls, xform_id):
        return cls._get_xform(xform_id)

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
    def get_case(case_id):
        return CommCareCase.get(case_id)

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

    @staticmethod
    @to_generic
    def post_xform(instance_xml, attachments=None, process=None, domain='test-domain'):
        """
        create a new xform and releases the lock

        this is a testing entry point only and is not to be used in real code

        """
        if not process:
            def process(xform):
                xform.domain = domain
        xform_lock = process_xform(instance_xml, attachments=attachments, process=process, domain=domain)
        with xform_lock as xforms:
            for xform in xforms:
                xform.save()
            return xforms[0]
