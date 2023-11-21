import datetime
import logging
import uuid
from itertools import chain

import redis
from contextlib import ExitStack
from django.db import transaction, DatabaseError
from lxml import etree

from casexml.apps.case import const
from casexml.apps.case.xform import get_case_updates
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
from corehq.form_processor.change_publishers import (
    publish_form_saved, publish_case_saved, publish_ledger_v2_saved)
from corehq.form_processor.exceptions import CaseNotFound, KafkaPublishingError
from corehq.form_processor.interfaces.processor import CaseUpdateMetadata
from corehq.form_processor.models import (
    XFormInstance, CaseTransaction,
    CommCareCase, FormEditRebuild, Attachment, XFormOperation)
from corehq.form_processor.utils import convert_xform_to_json, extract_meta_instance_id, extract_meta_user_id
from corehq.util.metrics.load_counters import case_load_counter
from corehq import toggles
from couchforms.const import ATTACHMENT_NAME
from dimagi.utils.couch import acquire_lock, release_lock


class FormProcessorSQL(object):

    @classmethod
    def store_attachments(cls, xform, attachments):
        xform.attachments_list = attachments

    @classmethod
    def copy_attachments(cls, from_form, to_form):
        to_form.copy_attachments(from_form)

    @classmethod
    def copy_form_operations(cls, from_form, to_form):
        for op in from_form.history:
            op.id = None
            op.form = to_form
            to_form.track_create(op)

    @classmethod
    def new_xform(cls, form_data):
        form_id = extract_meta_instance_id(form_data) or str(uuid.uuid4())

        return XFormInstance(
            # other properties can be set post-wrap
            form_id=form_id,
            xmlns=form_data.get('@xmlns'),
            received_on=datetime.datetime.utcnow(),
            user_id=extract_meta_user_id(form_data),
        )

    @classmethod
    def is_duplicate(cls, xform_id, domain=None):
        return XFormInstance.objects.form_exists(xform_id, domain=domain)

    @classmethod
    def hard_delete_case_and_forms(cls, domain, case, xforms):
        form_ids = [xform.form_id for xform in xforms]
        XFormInstance.objects.hard_delete_forms(domain, form_ids)
        CommCareCase.objects.hard_delete_cases(domain, [case.case_id])

    @classmethod
    def new_form_from_old(cls, existing_form, xml, value_responses_map, user_id):
        from corehq.form_processor.parsers.form import apply_deprecation

        new_xml = etree.tostring(xml, encoding='utf-8')
        form_json = convert_xform_to_json(new_xml)
        new_form = cls.new_xform(form_json)
        new_form.user_id = user_id
        new_form.domain = existing_form.domain
        new_form.app_id = existing_form.app_id
        cls.store_attachments(new_form, [Attachment(
            name=ATTACHMENT_NAME,
            raw_content=new_xml,
            content_type='text/xml',
        )])

        existing_form, new_form = apply_deprecation(existing_form, new_form)
        return (existing_form, new_form)

    @classmethod
    def save_processed_models(cls, processed_forms, cases=None, stock_result=None):
        db_names = {processed_forms.submitted.db}
        if processed_forms.deprecated:
            db_names |= {processed_forms.deprecated.db}

        if cases:
            db_names |= {case.db for case in cases}

        if stock_result:
            db_names |= {
                ledger_value.db for ledger_value in stock_result.models_to_save
            }

        all_models = filter(None, chain(
            processed_forms,
            cases or [],
            stock_result.models_to_save if stock_result else [],
        ))
        try:
            with ExitStack() as stack:
                for db_name in db_names:
                    stack.enter_context(transaction.atomic(db_name))

                # Save deprecated form first to avoid ID conflicts
                if processed_forms.deprecated:
                    XFormInstance.objects.update_form(processed_forms.deprecated, publish_changes=False)

                XFormInstance.objects.save_new_form(processed_forms.submitted)
                if cases:
                    for case in cases:
                        case.save(with_tracked_models=True)

                if stock_result:
                    ledgers_to_save = stock_result.models_to_save
                    LedgerAccessorSQL.save_ledger_values(ledgers_to_save, stock_result)

            if cases:
                sort_submissions = toggles.SORT_OUT_OF_ORDER_FORM_SUBMISSIONS_SQL.enabled(
                    processed_forms.submitted.domain, toggles.NAMESPACE_DOMAIN)
                if sort_submissions:
                    for case in cases:
                        if SqlCaseUpdateStrategy(case).reconcile_transactions_if_necessary():
                            case.save(with_tracked_models=True)
        except DatabaseError:
            for model in all_models:
                setattr(model, model._meta.pk.attname, None)
                for tracked in model.create_models:
                    setattr(tracked, tracked._meta.pk.attname, None)
            raise

        try:
            cls.publish_changes_to_kafka(processed_forms, cases, stock_result)
        except Exception as e:
            raise KafkaPublishingError(e)

    @staticmethod
    def publish_changes_to_kafka(processed_forms, cases, stock_result):
        publish_form_saved(processed_forms.submitted)
        cases = cases or []
        for case in cases:
            publish_case_saved(
                case,
                associated_form_id=processed_forms.submitted.form_id,
                send_post_save_signal=False
            )

        if stock_result:
            for ledger in stock_result.models_to_save:
                publish_ledger_v2_saved(ledger)

    @classmethod
    def apply_deprecation(cls, existing_xform, new_xform):
        existing_xform.state = XFormInstance.DEPRECATED
        default_user_id = new_xform.user_id or 'unknown'
        user_id = new_xform.auth_context and new_xform.auth_context.get('user_id') or default_user_id
        operation = XFormOperation(
            user_id=user_id,
            date=new_xform.edited_on,
            operation=XFormOperation.EDIT
        )
        new_xform.track_create(operation)
        return existing_xform, new_xform

    @classmethod
    def deduplicate_xform(cls, xform):
        xform.state = XFormInstance.DUPLICATE
        xform.orig_id = xform.form_id
        xform.problem = "Form is a duplicate of another! (%s)" % xform.form_id
        return cls.assign_new_id(xform)

    @classmethod
    def assign_new_id(cls, xform):
        from corehq.sql_db.util import new_id_in_same_dbalias
        # avoid moving to a separate sharded db
        xform.form_id = new_id_in_same_dbalias(xform.form_id)
        return xform

    @classmethod
    def xformerror_from_xform_instance(cls, instance, error_message, with_new_id=False):
        instance.state = XFormInstance.ERROR
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
        xform = XFormInstance(
            domain=domain,
            form_id=uuid.uuid4().hex,
            received_on=datetime.datetime.utcnow(),
            problem=message,
            state=XFormInstance.SUBMISSION_ERROR_LOG,
            xmlns=''
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
                if not (xform.is_deprecated and xform.problem):
                    # don't process deprecated forms which have errors.
                    # see http://manage.dimagi.com/default.asp?243382 for context.
                    # note that we have to use .problem instead of .is_error because applying
                    # the state=DEPRECATED overrides state=ERROR
                    affected_cases.update(case_update.id for case_update in get_case_updates(xform))

            rebuild_detail = FormEditRebuild(deprecated_form_id=deprecated_form.form_id)
            for case_id in affected_cases:
                case = case_db.get(case_id)
                is_creation = False
                if not case:
                    case = CommCareCase(domain=domain, case_id=case_id)
                    is_creation = True
                    case_db.set(case_id, case)
                previous_owner = case.owner_id
                case, _ = FormProcessorSQL._rebuild_case_from_transactions(
                    case, rebuild_detail, updated_xforms=xforms
                )
                if case:
                    touched_cases[case.case_id] = CaseUpdateMetadata(
                        case=case, is_creation=is_creation, previous_owner_id=previous_owner,
                        actions={const.CASE_ACTION_REBUILD}
                    )
        else:
            xform = xforms[0]
            for case_update in get_case_updates(xform):
                case_update_meta = case_db.get_case_from_case_update(case_update, xform)
                if case_update_meta.case:
                    case_id = case_update_meta.case.case_id
                    if case_id in touched_cases:
                        touched_cases[case_id] = touched_cases[case_id].merge(case_update_meta)
                    else:
                        touched_cases[case_id] = case_update_meta
                else:
                    logging.error(
                        "XForm %s had a case block that wasn't able to create a case! "
                        "This usually means it had a missing ID" % xform.get_id
                    )

        return touched_cases

    @staticmethod
    def hard_rebuild_case(domain, case_id, detail, lock=True, save=True):
        assert save or not lock, "refusing to lock when not saving"
        if lock:
            # only record metric if locking since otherwise it has been
            # (most likley) recorded elsewhere
            case_load_counter("rebuild_case", domain)()
        case, lock_obj = FormProcessorSQL.get_case_with_lock(case_id, lock=lock)
        found = bool(case)
        if not found:
            case = CommCareCase(case_id=case_id, domain=domain)
            if lock:
                lock_obj = CommCareCase.get_obj_lock_by_id(case_id)
                acquire_lock(lock_obj, degrade_gracefully=False)

        try:
            assert case.domain == domain, (case.domain, domain)
            case, rebuild_transaction = FormProcessorSQL._rebuild_case_from_transactions(case, detail)
            if case.is_deleted and not case.is_saved():
                return None

            case.server_modified_on = rebuild_transaction.server_date
            if save:
                case.save(with_tracked_models=True)
                publish_case_saved(case)
            return case
        finally:
            release_lock(lock_obj, degrade_gracefully=True)

    @staticmethod
    def _rebuild_case_from_transactions(case, detail, updated_xforms=None):
        strategy = SqlCaseUpdateStrategy(case)
        transactions = strategy.get_transactions_for_rebuild(updated_xforms)

        rebuild_transaction = CaseTransaction.rebuild_transaction(case, detail)
        if updated_xforms:
            rebuild_transaction.server_date = updated_xforms[0].edited_on
        unarchived_form_id = None
        if detail.type == CaseTransaction.TYPE_REBUILD_FORM_ARCHIVED and not detail.archived:
            # we're rebuilding because a form was un-archived
            unarchived_form_id = detail.form_id
        strategy.rebuild_from_transactions(
            transactions, rebuild_transaction, unarchived_form_id=unarchived_form_id
        )
        return case, rebuild_transaction

    @staticmethod
    def get_case_forms(case_id):
        xform_ids = CommCareCase.objects.get_case_xform_ids(case_id)
        return XFormInstance.objects.get_forms_with_attachments_meta(xform_ids)

    @staticmethod
    def form_has_case_transactions(form_id):
        return CaseTransaction.objects.exists_for_form(form_id)

    @staticmethod
    def get_case_with_lock(case_id, lock=False, wrap=False):
        try:
            if lock:
                try:
                    return CommCareCase.get_locked_obj(_id=case_id)
                except redis.RedisError:
                    case = CommCareCase.objects.get_case(case_id)
            else:
                case = CommCareCase.objects.get_case(case_id)
        except CaseNotFound:
            return None, None

        return case, None
