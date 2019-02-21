from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from collections import namedtuple
from datetime import datetime

from couchdbkit import ResourceNotFound

from casexml.apps.case.exceptions import IllegalCaseId, InvalidCaseIndex, CaseValueError, PhoneDateValueError
from casexml.apps.case.exceptions import UsesReferrals
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.apps.domain_migration_flags.api import any_migrations_in_progress
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import XFormNotFound, PostSaveError
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.models import XFormInstanceSQL, FormReprocessRebuild
from corehq.form_processor.submission_post import SubmissionPost
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.datadog.utils import form_load_counter
from dimagi.utils.couch import LockManager
import six

ReprocessingResult = namedtuple('ReprocessingResult', 'form cases ledgers error')

logger = logging.getLogger('reprocess')


class ReprocessingError(Exception):
    pass


def reprocess_unfinished_stub(stub, save=True):
    if any_migrations_in_progress(stub.domain):
        logger.info("Ignoring stub during data migration: %s", stub.xform_id)
        return

    form_id = stub.xform_id
    try:
        form = FormAccessors(stub.domain).get_form(form_id)
    except XFormNotFound:
        if stub.saved:
            logger.error("Form not found for reprocessing", extra={
                'form_id': form_id,
                'domain': stub.domain
            })
        save and stub.delete()
        return

    return reprocess_unfinished_stub_with_form(stub, form, save)


def reprocess_unfinished_stub_with_form(stub, form, save=True, lock=True):
    if form.is_deleted:
        save and stub.delete()
        return ReprocessingResult(form, None, None, None)

    if stub.saved:
        complete_ = (form.is_normal, form.initial_processing_complete)
        assert all(complete_), complete_
        result = _perfom_post_save_actions(form, save)
    else:
        result = reprocess_form(form, save, lock_form=lock)

    save and not result.error and stub.delete()
    return result


def _perfom_post_save_actions(form, save=True):
    interface = FormProcessorInterface(form.domain)
    cache = interface.casedb_cache(
        domain=form.domain, lock=False, deleted_ok=True, xforms=[form],
        load_src="reprocess_form_post_save",
    )
    with cache as casedb:
        case_stock_result = SubmissionPost.process_xforms_for_cases([form], casedb)
        case_models = case_stock_result.case_models

        if interface.use_sql_domain:
            forms = ProcessedForms(form, None)
            stock_result = case_stock_result.stock_result
            try:
                FormProcessorSQL.publish_changes_to_kafka(forms, case_models, stock_result)
            except Exception:
                error_message = "Error publishing to kafka"
                return ReprocessingResult(form, None, None, error_message)

        try:
            save and SubmissionPost.do_post_save_actions(casedb, [form], case_stock_result)
        except PostSaveError:
            error_message = "Error performing post save operations"
            return ReprocessingResult(form, None, None, error_message)
        return ReprocessingResult(form, case_models, None, None)


def reprocess_xform_error(form):
    """
    Attempt to re-process an error form. This was created specifically to address
    the issue of out of order forms and child cases (form creates child case before
    parent case has been created).

    See http://manage.dimagi.com/default.asp?250459
    :param form_id: ID of the error form to process
    """
    if not form:
        raise ReprocessingError('Form with ID {} not found'.format(form.form_id))

    if not form.is_error:
        raise ReprocessingError('Form was not an error form: {}={}'.format(form.form_id, form.doc_type))

    return reprocess_form(form).form


def reprocess_xform_error_by_id(form_id, domain=None):
    form = _get_form(form_id)
    if domain and form.domain != domain:
        raise ReprocessingError('Form not found')
    return reprocess_xform_error(form)


def reprocess_form(form, save=True, lock_form=True):
    if lock_form:
        # track load if locking; otherise it will be tracked elsewhere
        form_load_counter("reprocess_form", form.domain)()
    interface = FormProcessorInterface(form.domain)
    lock = interface.acquire_lock_for_xform(form.form_id) if lock_form else None
    with LockManager(form, lock):
        logger.info('Reprocessing form: %s (%s)', form.form_id, form.domain)
        # reset form state prior to processing
        if should_use_sql_backend(form.domain):
            form.state = XFormInstanceSQL.NORMAL
        else:
            form.doc_type = 'XFormInstance'

        cache = interface.casedb_cache(
            domain=form.domain, lock=True, deleted_ok=True, xforms=[form],
            load_src="reprocess_form",
        )
        with cache as casedb:
            try:
                case_stock_result = SubmissionPost.process_xforms_for_cases([form], casedb)
            except (IllegalCaseId, UsesReferrals, MissingProductId,
                    PhoneDateValueError, InvalidCaseIndex, CaseValueError) as e:
                error_message = '{}: {}'.format(type(e).__name__, six.text_type(e))
                form = interface.xformerror_from_xform_instance(form, error_message)
                return ReprocessingResult(form, [], [], error_message)

            form.initial_processing_complete = True
            form.problem = None

            stock_result = case_stock_result.stock_result
            assert stock_result.populated

            cases = case_stock_result.case_models
            _log_changes(cases, stock_result.models_to_save, stock_result.models_to_delete)

            ledgers = []
            if should_use_sql_backend(form.domain):
                cases_needing_rebuild = _get_case_ids_needing_rebuild(form, cases)

                ledgers = stock_result.models_to_save
                ledgers_updated = {ledger.ledger_reference for ledger in ledgers if ledger.is_saved()}

                if save:
                    for case in cases:
                        CaseAccessorSQL.save_case(case)
                    LedgerAccessorSQL.save_ledger_values(ledgers)
                    FormAccessorSQL.update_form_problem_and_state(form)
                    FormProcessorSQL.publish_changes_to_kafka(ProcessedForms(form, None), cases, stock_result)

                # rebuild cases and ledgers that were affected
                for case in cases:
                    if case.case_id in cases_needing_rebuild:
                        logger.info('Rebuilding case: %s', case.case_id)
                        if save:
                            # only rebuild cases that were updated
                            detail = FormReprocessRebuild(form_id=form.form_id)
                            interface.hard_rebuild_case(case.case_id, detail, lock=False)

                for ledger in ledgers:
                    if ledger.ledger_reference in ledgers_updated:
                        logger.info('Rebuilding ledger: %s', ledger.ledger_reference)
                        if save:
                            # only rebuild updated ledgers
                            interface.ledger_processor.rebuild_ledger_state(**ledger.ledger_reference._asdict())

            else:
                if save:
                    interface.processor.save_processed_models([form], cases, stock_result)
                    from casexml.apps.stock.models import StockTransaction
                    ledgers = [
                        model
                        for model in stock_result.models_to_save
                        if isinstance(model, StockTransaction)
                    ]
                    for ledger in ledgers:
                        interface.ledger_processor.rebuild_ledger_state(**ledger.ledger_reference._asdict())

            save and SubmissionPost.do_post_save_actions(casedb, [form], case_stock_result)

        return ReprocessingResult(form, cases, ledgers, None)


def _log_changes(cases, stock_updates, stock_deletes):
    if logger.isEnabledFor(logging.INFO):
        case_ids = [case.case_id for case in cases]
        logger.info(
            "changes:\n\tcases: %s\n\tstock changes%s\n\tstock deletes%s",
            case_ids, stock_updates, stock_deletes
        )


def _get_case_ids_needing_rebuild(form, cases):
    """Return a set of case IDs for cases that have been modified since the form was
    originally submitted i.e. are needing to be rebuilt"""

    # exclude any cases that didn't already exist
    case_ids = [case.case_id for case in cases if case.is_saved()]
    modified_dates = CaseAccessorSQL.get_last_modified_dates(form.domain, case_ids)
    return {
        case_id for case_id in case_ids
        if modified_dates.get(case_id, datetime.max) > form.received_on
    }


def _get_form(form_id):
    from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
    from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
    try:
        return FormAccessorSQL.get_form(form_id)
    except XFormNotFound:
        pass

    try:
        return FormAccessorCouch.get_form(form_id)
    except ResourceNotFound:
        pass

    return None
