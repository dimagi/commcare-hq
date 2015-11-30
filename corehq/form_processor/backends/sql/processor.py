import datetime
import logging
import uuid

from django.db import transaction

from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.interfaces.processor import CaseUpdateMetadata
from couchforms.const import ATTACHMENT_NAME

from corehq.form_processor.models import (
    XFormInstanceSQL, XFormAttachmentSQL,
    XFormOperationSQL, CommCareCaseIndexSQL, CaseTransaction,
    CommCareCaseSQL, FormEditRebuild, Attachment)
from corehq.form_processor.utils import extract_meta_instance_id, extract_meta_user_id


class FormProcessorSQL(object):

    @classmethod
    def store_attachments(cls, xform, attachments):
        xform_attachments = []
        for attachment in attachments:
            xform_attachment = XFormAttachmentSQL(
                name=attachment.name,
                attachment_id=uuid.uuid4(),
                content_type=attachment.content_type,
                md5=attachment.md5,
            )
            xform_attachment.write_content(attachment.content)
            xform_attachments.append(xform_attachment)

        xform.unsaved_attachments = xform_attachments

    @classmethod
    def new_xform(cls, form_data):
        form_id = extract_meta_instance_id(form_data) or unicode(uuid.uuid4())

        return XFormInstanceSQL(
            # other properties can be set post-wrap
            form_id=form_id,
            xmlns=form_data.get('@xmlns'),
            received_on=datetime.datetime.utcnow(),
            user_id=extract_meta_user_id(form_data),
        )

    @classmethod
    def is_duplicate(cls, xform_id, domain=None):
        return FormAccessorSQL.form_with_id_exists(xform_id, domain=domain)

    @classmethod
    def hard_delete_case_and_forms(cls, case, xforms):
        form_ids = [xform.form_id for xform in xforms]
        FormAccessorSQL.hard_delete_forms(form_ids)
        CaseAccessorSQL.hard_delete_case(case.case_id)

    @classmethod
    def save_processed_models(cls, xforms, cases=None, stock_updates=None):
        with transaction.atomic():
            logging.debug('Beginning atomic commit\n')
            # Ensure already saved forms get saved first to avoid ID conflicts
            is_deprecation = len(xforms) > 1
            for xform in sorted(xforms, key=lambda xform: not xform.is_saved()):
                cls.save_xform(xform, is_deprecation)

            if cases:
                for case in cases:
                    cls.save_case(case)
            for stock_update in stock_updates or []:
                stock_update.commit()

    @classmethod
    def save_xform(cls, xform, is_deprecation=False):
        """
        :param xform: The xform to save
        :param is_deprecation: Set to True if this save is part of a deprecation save.
        """
        with transaction.atomic():
            logging.debug('Saving form: %s', xform)
            xform.save()
            if is_deprecation and xform.is_deprecated:
                logging.debug(
                    'Reassigning attachments and operations to deprecated form: %s -> %s',
                    xform.orig_id, xform.form_id
                )
                attachments = XFormAttachmentSQL.objects.filter(form_id=xform.orig_id)
                attachments.update(form_id=xform.form_id)

                operations = XFormOperationSQL.objects.filter(form_id=xform.orig_id)
                operations.update(form_id=xform.form_id)

            unsaved_attachments = getattr(xform, 'unsaved_attachments', None)
            if unsaved_attachments:
                logging.debug('Saving %s attachments for form: %s', len(unsaved_attachments), xform.form_id)
                for unsaved_attachment in unsaved_attachments:
                    unsaved_attachment.form = xform
                xform.attachment_set.bulk_create(unsaved_attachments)
                del xform.unsaved_attachments

    @classmethod
    def save_case(cls, case):
        with transaction.atomic():
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
        for i, model in enumerate(to_create):
            logging.debug('Creating %s %s: %s', i, model_class, model)
            model.save()

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

    @classmethod
    def submission_error_form_instance(cls, domain, instance, message):
        xform = XFormInstanceSQL(
            domain=domain,
            form_id=uuid.uuid4().hex,
            received_on=datetime.datetime.utcnow(),
            problem=message,
            state=XFormInstanceSQL.SUBMISSION_ERROR_LOG
        )
        cls.store_attachments(xform, [Attachment(
            name=ATTACHMENT_NAME,
            raw_content=instance,
            content_type='text/xml',
        )])

        return xform

    @staticmethod
    def get_cases_from_forms(case_db, xforms):
        """Get all cases affected by the forms. Includes new cases, updated cases.
        """
        touched_cases = {}
        if len(xforms) > 1:
            domain = xforms[0].domain
            affected_cases = set()
            deprecated_form = None
            for xform in xforms:
                if xform.is_deprecated:
                    deprecated_form = xform
                affected_cases.update(case_update.id for case_update in get_case_updates(xform))

            rebuild_detail = FormEditRebuild(deprecated_form_id=deprecated_form.form_id)
            for case_id in affected_cases:
                case = case_db.get(case_id)
                is_creation = False
                if not case:
                    case = CommCareCaseSQL(domain=domain, case_id=case_id)
                    is_creation = True
                    case_db.set(case_id, case)
                previous_owner = case.owner_id
                case = FormProcessorSQL._rebuild_case_from_transactions(case, rebuild_detail, updated_xforms=xforms)
                if case:
                    touched_cases[case.case_id] = CaseUpdateMetadata(
                        case=case, is_creation=is_creation, previous_owner_id=previous_owner,
                    )
        else:
            xform = xforms[0]
            for case_update in get_case_updates(xform):
                case_update_meta = case_db.get_case_from_case_update(case_update, xform)
                if case_update_meta.case:
                    touched_cases[case_update_meta.case.case_id] = case_update_meta
                else:
                    logging.error(
                        "XForm %s had a case block that wasn't able to create a case! "
                        "This usually means it had a missing ID" % xform.get_id
                    )

        return touched_cases

    @staticmethod
    def hard_rebuild_case(domain, case_id, detail):
        try:
            case = CaseAccessorSQL.get_case(case_id)
            assert case.domain == domain
            found = True
        except CaseNotFound:
            case = CommCareCaseSQL(case_id=case_id, domain=domain)
            found = False

        case = FormProcessorSQL._rebuild_case_from_transactions(case, detail)
        if case.is_deleted and not found:
            return None
        FormProcessorSQL.save_case(case)

    @staticmethod
    def _rebuild_case_from_transactions(case, detail, updated_xforms=None):
        transactions = get_case_transactions(case.case_id, updated_xforms=updated_xforms)
        strategy = SqlCaseUpdateStrategy(case)

        rebuild_transaction = CaseTransaction.rebuild_transaction(case, detail)
        strategy.rebuild_from_transactions(transactions, rebuild_transaction)
        return case

    @staticmethod
    def get_case_forms(case_id):
        xform_ids = CaseAccessorSQL.get_case_xform_ids(case_id)
        return FormAccessorSQL.get_forms_with_attachments_meta(xform_ids)


def get_case_transactions(case_id, updated_xforms=None):
    transactions = CaseAccessorSQL.get_transactions_for_case_rebuild(case_id)
    form_ids = {tx.form_id for tx in transactions}
    updated_xforms_map = {
        xform.form_id: xform for xform in updated_xforms if not xform.is_deprecated
    } if updated_xforms else {}

    form_ids_to_fetch = form_ids - set(updated_xforms_map.keys())
    xform_map = {form.form_id: form for form in FormAccessorSQL.get_forms_with_attachments_meta(form_ids_to_fetch)}

    def get_form(form_id):
        if form_id in updated_xforms_map:
            return updated_xforms_map[form_id]

        try:
            return xform_map[form_id]
        except KeyError:
            raise XFormNotFound

    for transaction in transactions:
        if transaction.form_id:
            try:
                transaction.cached_form = get_form(transaction.form_id)
            except XFormNotFound:
                logging.error('Form not found during rebuild: %s', transaction.form_id)

    return transactions
