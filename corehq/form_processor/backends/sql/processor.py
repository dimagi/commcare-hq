import datetime
import uuid
import hashlib

from couchforms.util import process_xform
from django.db import transaction

from corehq.form_processor.models import XFormInstanceSQL, XFormAttachmentSQL
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
            cls.bulk_save(xforms[0], xforms)
            return xforms[0]

    @classmethod
    def store_attachments(cls, xform, attachments):
        xform_attachments = []
        for attachment in attachments:
            xform_attachment = XFormAttachmentSQL(
                name=attachment.name,
                attachment_uuid=unicode(uuid.uuid4()),
                content_type=attachment.content_type,
                md5=hashlib.md5(attachment.content).hexdigest(),
            )
            xform_attachment.write_content(attachment.content)
            xform_attachments.append(xform_attachment)

        xform.unsaved_attachments = xform_attachments

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

    @classmethod
    def bulk_save(cls, instance, xforms, cases=None):
        try:
            with transaction.atomic():
                for xform in xforms:
                    xform.save()
                for unsaved_attachment in instance.unsaved_attachments:
                    unsaved_attachment.xform = instance
                instance.xformattachmentsql_set.bulk_create(instance.unsaved_attachments)

                for case in cases:
                    case.save()
                if getattr(case, 'unsaved_indices', None):
                    case.index_set.bulk_create(case.unsaved_indices)
        except Exception as e:
            xforms_being_saved = [xform.form_id for xform in xforms]
            error_message = u'Unexpected error bulk saving docs {}: {}, doc_ids: {}'.format(
                type(e).__name__,
                unicode(e),
                ', '.join(xforms_being_saved)
            )
            # instance = _handle_unexpected_error(instance, error_message)
            raise

    @classmethod
    def process_stock(cls, xforms, case_db):
        from corehq.apps.commtrack.processing import StockProcessingResult
        return StockProcessingResult(xforms[0])
