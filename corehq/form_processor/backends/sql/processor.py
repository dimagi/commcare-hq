import datetime
import uuid

from couchforms.util import process_xform

from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.utils import extract_meta_instance_id


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
    def store_attachments(cls, xform, attachments):
        pass

    @classmethod
    def new_xform(cls, form_data):
        form_id = extract_meta_instance_id(form_data) or unicode(uuid.uuid4())

        return XFormInstanceSQL(
            # other properties can be set post-wrap
            form_uuid=form_id,
            xmlns=form_data.get('@xmlns'),
            received_on=datetime.datetime.now()
        )

    @classmethod
    def is_duplicate(cls, xform, lock):
        return False
