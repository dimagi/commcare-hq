import datetime
import uuid

from dimagi.utils.couch import LockManager
from couchforms.util import process_xform, acquire_lock_for_xform

from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.utils import convert_xform_to_json, adjust_datetimes, extract_meta_instance_id


class FormProcessorSQL(object):

    @classmethod
    def post_xform(cls, instance_xml, attachments=None, process=None, domain='test-domain'):
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

    @classmethod
    def create_xform(cls, xml_string, attachments=None, process=None):
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

        form_id = extract_meta_instance_id(json_form) or unicode(uuid.uuid4())

        xform = XFormInstanceSQL(
            # form has to be wrapped
            form=json_form,
            # other properties can be set post-wrap
            form_uuid=form_id,
            xmlns=json_form.get('@xmlns'),
        )
        #attachment_manager = AttachmentsManager(xform)

        ## Always save the Form XML as an attachment
        #attachment_manager.store_attachment('form.xml', xml_string, 'text/xml')

        #for name, filestream in attachments.items():
        #    attachment_manager.store_attachment(name, filestream, filestream.content_type)

        #attachment_manager.commit()

        # this had better not fail, don't think it ever has
        # if it does, nothing's saved and we get a 500
        if process:
            process(xform)

        lock = acquire_lock_for_xform(form_id)
        #with ReleaseOnError(lock):
        #    if _id in XFormInstance.get_db():
        #        raise DuplicateError(xform)

        return LockManager(xform, lock)
