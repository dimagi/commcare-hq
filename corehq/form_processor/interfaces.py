from couchdbkit import ResourceNotFound
from dimagi.utils.couch.undo import DELETED_SUFFIX
from casexml.apps.case.models import CommCareCase

from couchforms.util import process_xform
from couchforms.models import doc_types, XFormInstance, XFormError
from couchforms.exceptions import UnexpectedDeletedXForm


class FormProcessorInterface(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

    @staticmethod
    def create_from_generic(generic_xform, generic_attachment=None):
        xform = XFormInstance.from_generic(generic_xform)
        xform.save()
        if generic_attachment:
            xform.put_attachment(**generic_attachment.to_json())
        return xform

    @staticmethod
    def xpath(xform, xpath):
        return xform.xpath(xpath)

    @staticmethod
    def get_attachment(xform_id, attachment_name):
        return XFormInstance.get_db().fetch_attachment(xform_id, attachment_name)

    @staticmethod
    def archive_xform(xform, user=None):
        return xform.archive(user=user)

    @staticmethod
    def unarchive_xform(xform, user=None):
        return xform.unarchive(user=user)

    @staticmethod
    def get_xml_element(xform):
        return xform.get_xml_element()

    @staticmethod
    def get_xform(xform_id):
        db = XFormInstance.get_db()
        doc = db.get(xform_id)
        if doc['doc_type'] in doc_types():
            return doc_types()[doc['doc_type']].wrap(doc)
        if doc['doc_type'] == "%s%s" % (XFormInstance.__name__, DELETED_SUFFIX):
            raise UnexpectedDeletedXForm(xform_id)
        raise ResourceNotFound(xform_id)

    @staticmethod
    def get_case(case_id):
        return CommCareCase.get(case_id)

    @staticmethod
    def get_by_doc_type(domain, doc_type):
        return XFormError.view(
            'domain/docs',
            startkey=[domain, doc_type],
            endkey=[domain, doc_type, {}],
            reduce=False,
            include_docs=True,
        ).all()

    @staticmethod
    def update_properties(xform, **properties):
        for prop, value in properties.iteritems():
            setattr(xform, prop, value)
        xform.save()

    @staticmethod
    def post_xform(instance_xml, attachments=None, process=None,
                            domain='test-domain'):
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
