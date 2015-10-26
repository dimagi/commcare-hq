import datetime
from dimagi.utils.couch import ReleaseOnError, LockManager

from couchforms.models import XFormInstance
from couchforms.attachments import AttachmentsManager
from couchforms.util import acquire_lock_for_xform
from couchforms.exceptions import DuplicateError
from corehq.form_processor.utils import (
    extract_meta_instance_id,
    convert_xform_to_json,
    adjust_datetimes,
)


class FormProcessorCouch(object):

    @classmethod
    def new_xform(cls, instance_xml, attachments=None, process=None):
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
        json_form = convert_xform_to_json(instance_xml)
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
        attachment_manager.store_attachment('form.xml', instance_xml, 'text/xml')

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
