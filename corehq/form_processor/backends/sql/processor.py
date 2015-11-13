import datetime
import logging
import uuid
import hashlib

from django.db import transaction
from couchforms.util import process_xform

from corehq.form_processor.models import (
    XFormInstanceSQL, XFormAttachmentSQL,
    XFormOperationSQL, CommCareCaseIndexSQL, CaseTransaction
)
from corehq.form_processor.utils import extract_meta_instance_id, extract_meta_user_id


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
            received_on=datetime.datetime.utcnow(),
            user_id=extract_meta_user_id(form_data),
        )

    @classmethod
    def is_duplicate(cls, xform):
        return XFormInstanceSQL.objects.filter(form_uuid=xform.form_id).exists()

    @classmethod
    def should_handle_as_duplicate_or_edit(cls, xform_id, domain):
        return XFormInstanceSQL.objects.filter(form_uuid=xform_id, domain=domain).exists()

    @classmethod
    def bulk_save(cls, instance, xforms, cases=None):
        with transaction.atomic():
            logging.debug('Beginning atomic commit\n')
            # Ensure already saved forms get saved first to avoid ID conflicts
            for xform in sorted(xforms, key=lambda xform: not xform.is_saved()):
                xform.save()
                if xform.is_deprecated:
                    attachments = XFormAttachmentSQL.objects.filter(xform_id=xform.orig_id)
                    attachments.update(xform_id=xform.form_id)

                    operations = XFormOperationSQL.objects.filter(xform_id=xform.orig_id)
                    operations.update(xform_id=xform.form_id)

                    CaseTransaction.objects.filter(form_uuid=xform.orig_id).delete()

            for unsaved_attachment in instance.unsaved_attachments:
                unsaved_attachment.xform = instance
            instance.attachments.bulk_create(instance.unsaved_attachments)

            if cases:
                for case in cases:
                    logging.debug('Saving case: %s', case)
                    if logging.root.isEnabledFor(logging.DEBUG):
                        logging.debug(case.dumps(pretty=True))

                    case.save()

                    FormProcessorSQL.save_tracked_models(case, CommCareCaseIndexSQL)
                    FormProcessorSQL.save_tracked_models(case, CaseTransaction)
                    case.clear_tracked_models()

    @staticmethod
    def save_tracked_models(case, model_class):
        to_delete = case.get_tracked_models_to_delete(model_class)
        if to_delete:
            logging.debug('Deleting %s: %s', model_class, to_delete)
            ids = [index.pk for index in to_delete]
            model_class.objects.filter(pk__in=ids).delete()

        to_update = case.get_tracked_models_to_update(model_class)
        for model in to_update:
            logging.debug('Updating %s: %s', model_class, model)
            model.save()

        to_create = case.get_tracked_models_to_create(model_class)
        for model in to_create:
            logging.debug('Creating %s: %s', model_class, to_create)
            model.save()

    @classmethod
    def process_stock(cls, xforms, case_db):
        from corehq.apps.commtrack.processing import StockProcessingResult
        return StockProcessingResult(xforms[0])

    @classmethod
    def deprecate_xform(cls, existing_xform, new_xform):
        # if the form contents are not the same:
        #  - "Deprecate" the old form by making a new document with the same contents
        #    but a different ID and a doc_type of XFormDeprecated
        #  - Save the new instance to the previous document to preserve the ID

        old_id = existing_xform.form_id
        new_xform = cls.assign_new_id(new_xform)

        # swap the two documents so the original ID now refers to the new one
        # and mark original as deprecated
        new_xform.form_id, existing_xform.form_id = old_id, new_xform.form_id

        # flag the old doc with metadata pointing to the new one
        existing_xform.state = XFormInstanceSQL.DEPRECATED
        existing_xform.orig_id = old_id

        # and give the new doc server data of the old one and some metadata
        new_xform.received_on = existing_xform.received_on
        new_xform.deprecated_form_id = existing_xform.form_id
        new_xform.edited_on = datetime.datetime.utcnow()
        return existing_xform, new_xform

    @classmethod
    def deduplicate_xform(cls, xform):
        xform.state = XFormInstanceSQL.DUPLICATE
        xform.problem = "Form is a duplicate of another! (%s)" % xform.form_id
        return cls.assign_new_id(xform)

    @classmethod
    def assign_new_id(cls, xform):
        new_id = unicode(uuid.uuid4())
        xform.form_id = new_id
        return xform

    @classmethod
    def xformerror_from_xform_instance(cls, instance, error_message, with_new_id=False):
        instance.state = XFormInstanceSQL.ERROR
        instance.problem = error_message

        if with_new_id:
            orig_id = instance.form_id
            cls.assign_new_id(instance)
            instance.orig_id = orig_id
            if instance.is_saved():
                # clear the ID since we want to make a new doc
                instance.id = None

        return instance
