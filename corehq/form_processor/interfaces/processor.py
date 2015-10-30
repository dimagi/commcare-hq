from corehq.form_processor.utils import to_generic
from corehq.util.test_utils import unit_testing_only
from couchforms.util import process_xform
from couchforms.attachments import AttachmentsManager
from casexml.apps.case.util import post_case_blocks


class FormProcessorInterface(object):
    """
    The FormProcessorInterface serves as the base transactions that take place in forms. Different
    backends can implement this class in order to make common interface.
    """

    def __init__(self, domain=None):
        self.domain = domain

    @to_generic
    @unit_testing_only
    def post_xform(self, instance_xml, attachments=None, process=None, domain='test-domain'):
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

    def submit_form_locally(self, instance, domain='test-domain', **kwargs):
        from corehq.apps.receiverwrapper.util import submit_form_locally
        response, xform, cases = submit_form_locally(instance, domain, **kwargs)
        # response is an iterable so @to_generic doesn't work
        return response, xform.to_generic(), [case.to_generic() for case in cases]

    @to_generic
    def post_case_blocks(self, case_blocks, form_extras=None, domain=None):
        return post_case_blocks(case_blocks, form_extras=form_extras, domain=domain)

    def create_xform(self, xml_string, attachments=None, process=None):
        from couchforms.models import XFormInstance
        """
        create but do not save an XFormInstance from an xform payload (xml_string)
        optionally set the doc _id to a predefined value (_id)
        return doc _id of the created doc

        `process` is transformation to apply to the form right before saving
        This is to avoid having to save multiple times

        If xml_string is bad xml
          - raise couchforms.XMLSyntaxError

        """
        assert attachments is not None
        json_form = convert_xform_to_json(xml_string)
        adjust_datetimes(json_form)

        _id = extract_meta_instance_id(json_form) or XFormInstance.get_db().server.next_uuid()
        assert _id

        xform = XFormInstance(
            # form has to be wrapped
            {'form': json_form},
            # other properties can be set post-wrap
            _id=_id,
            xmlns=json_form.get('@xmlns'),
            received_on=datetime.datetime.utcnow(),
        )
        attachment_manager = AttachmentsManager(xform)

        # Always save the Form XML as an attachment
        attachment_manager.store_attachment('form.xml', xml_string, 'text/xml')

        for name, filestream in attachments.items():
            attachment_manager.store_attachment(name, filestream, filestream.content_type)

        attachment_manager.commit()

        # this had better not fail, don't think it ever has
        # if it does, nothing's saved and we get a 500
        if process:
            process(xform)

        lock = acquire_lock_for_xform(_id)
        with ReleaseOnError(lock):
            if _id in XFormInstance.get_db():
                raise DuplicateError(xform)

        return LockManager(xform, lock)

