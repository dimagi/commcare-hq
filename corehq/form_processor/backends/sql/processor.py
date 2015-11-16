import datetime
import logging
import uuid
import hashlib

from django.db import transaction

from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from couchforms.util import process_xform

from corehq.form_processor.models import (
    XFormInstanceSQL, XFormAttachmentSQL,
    XFormOperationSQL, CommCareCaseIndexSQL, CaseTransaction,
    CommCareCaseSQL, FormEditRebuild)
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

    @staticmethod
    def get_cases_from_forms(case_db, xforms):
        """Get all cases affected by the forms. Includes new cases, updated cases.
        """
        touched_cases = {}
        if len(xforms) > 1:
            domain = xforms[0].domain
            affected_cases = set()
            deprecated_form_id = None
            for xform in xforms:
                if xform.is_deprecated:
                    deprecated_form_id = xform.form_id
                affected_cases.update(case_update.id for case_update in get_case_updates(xform))

            rebuild_detail = FormEditRebuild(deprecated_form_id=deprecated_form_id)
            for case_id in affected_cases:
                case = case_db.get(case_id)
                if not case:
                    case = CommCareCaseSQL(domain=domain, case_id=case_id)
                    case_db.set(case_id, case)

                case = FormProcessorSQL._rebuild_case_from_transactions(case, rebuild_detail, updated_xforms=xforms)
                if case:
                    touched_cases[case.case_id] = case
        else:
            xform = xforms[0]
            for case_update in get_case_updates(xform):
                case = case_db.get_case_from_case_update(case_update, xform)
                if case:
                    touched_cases[case.case_id] = case
                else:
                    logging.error(
                        "XForm %s had a case block that wasn't able to create a case! "
                        "This usually means it had a missing ID" % xform.get_id
                    )

        return touched_cases

    @staticmethod
    def hard_rebuild_case(domain, case_id, detail):
        try:
            case = CommCareCaseSQL.get(case_id)
            assert case.domain == domain
            found = True
        except CaseNotFound:
            case = CommCareCaseSQL(case_uuid=case_id, domain=domain)
            found = False

        case = FormProcessorSQL._rebuild_case_from_transactions(case, detail)
        if case.is_deleted and not found:
            return None
        case.save()

    @staticmethod
    def _rebuild_case_from_transactions(case, detail, updated_xforms=None):
        transactions = get_case_transactions(case.case_id, updated_xforms=updated_xforms)
        strategy = SqlCaseUpdateStrategy(case)

        rebuild_transaction = CaseTransaction.rebuild_transaction(case, detail)
        strategy.rebuild_from_transactions(transactions, rebuild_transaction)
        return case


def get_case_transactions(case_id, updated_xforms=None):
    transactions = list(CaseTransaction.objects.filter(case_id=case_id).all())
    form_ids = {tx.form_uuid for tx in transactions}
    updated_xforms_map = {
        xform.form_id: xform for xform in updated_xforms if not xform.is_deprecated
    } if updated_xforms else {}

    form_ids_to_fetch = form_ids - set(updated_xforms_map.keys())
    xform_map = {form.form_id: form for form in XFormInstanceSQL.get_forms_with_attachments(form_ids_to_fetch)}

    def get_form(form_id):
        if form_id in updated_xforms_map:
            return updated_xforms_map[form_id]

        try:
            return xform_map[form_id]
        except KeyError:
            raise XFormNotFound

    for transaction in transactions:
        if transaction.form_uuid:
            try:
                transaction.cached_form = get_form(transaction.form_uuid)
            except XFormNotFound:
                logging.error('Form not found during rebuild: %s', transaction.form_uuid)

    return transactions
