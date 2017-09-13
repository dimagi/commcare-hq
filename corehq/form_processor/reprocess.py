import logging
from collections import namedtuple
from datetime import datetime

from couchdbkit import ResourceNotFound

from casexml.apps.case.exceptions import IllegalCaseId, InvalidCaseIndex, CaseValueError, PhoneDateValueError
from casexml.apps.case.exceptions import UsesReferrals
from casexml.apps.case.signals import case_post_save
from corehq.apps.commtrack.exceptions import MissingProductId
from corehq.blobs.mixin import bulk_atomic_blobs
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.change_publishers import publish_form_saved
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstanceSQL, FormReprocessRebuild
from corehq.form_processor.submission_post import SubmissionPost
from corehq.form_processor.utils.general import should_use_sql_backend
from couchforms.models import XFormInstance


ReprocessingResult = namedtuple('ReprocessingResult', 'form cases ledgers')

logger = logging.getLogger('reprocess')


class ReprocessingError(Exception):
    pass


def reprocess_unfinished_stub(stub, save=True):
    if stub.saved:
        # ignore for now
        logger.info("Ignoring 'saved' stub: %s", stub.xform_id)
        return

    if not should_use_sql_backend(stub.domain):
        # ignore for couch domains
        logger.info('Removing stub from non SQL domain: %s', stub.xform_id)
        save and stub.delete()
        return

    form_id = stub.xform_id
    try:
        form = FormAccessorSQL.get_form(form_id)
    except XFormNotFound:
        # form doesn't exist which means the failure probably happend during saving so
        # let mobile handle re-submitting it
        logger.error('Form not found: %s', form_id)
        save and stub.delete()
        return

    if form.is_deleted:
        save and stub.delete()

    if form.is_normal:
        result = _reprocess_form(form, save)
        save and stub.delete()
        return result


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

    return _reprocess_form(form).form


def reprocess_xform_error_by_id(form_id, domain=None):
    form = _get_form(form_id)
    if domain and form.domain != domain:
        raise ReprocessingError('Form not found')
    return reprocess_xform_error(form)


def _reprocess_form(form, save=True):
    logger.info('Reprocessing form: %s (%s)', form.form_id, form.domain)
    # reset form state prior to processing
    if should_use_sql_backend(form.domain):
        form.state = XFormInstanceSQL.NORMAL
    else:
        form.doc_type = 'XFormInstance'

    form.initial_processing_complete = True
    form.problem = None

    interface = FormProcessorInterface(form.domain)
    accessors = FormAccessors(form.domain)
    cache = interface.casedb_cache(
        domain=form.domain, lock=True, deleted_ok=True, xforms=[form]
    )
    with cache as casedb:
        try:
            case_stock_result = SubmissionPost.process_xforms_for_cases([form], casedb)
        except (IllegalCaseId, UsesReferrals, MissingProductId,
                PhoneDateValueError, InvalidCaseIndex, CaseValueError) as e:
            error_message = '{}: {}'.format(type(e).__name__, unicode(e))
            form = interface.xformerror_from_xform_instance(form, error_message)
            accessors.update_form_problem_and_state(form)
            return ReprocessingResult(form, [], [])

        stock_result = case_stock_result.stock_result
        assert stock_result.populated

        cases = case_stock_result.case_models
        _log_changes('unfiltered', cases, stock_result.models_to_save, stock_result.models_to_delete)

        ledgers = []
        if should_use_sql_backend(form.domain):
            cases = _filter_already_processed_cases(form, cases)
            cases_needing_rebuild = _get_case_ids_needing_rebuild(form, cases)
            if save:
                for case in cases:
                    CaseAccessorSQL.save_case(case)

            ledgers = _filter_already_processed_ledgers(form, stock_result.models_to_save)
            ledgers_updated = {ledger.ledger_reference for ledger in ledgers if ledger.is_saved()}
            if save:
                LedgerAccessorSQL.save_ledger_values(ledgers)

            if save:
                FormAccessorSQL.update_form_problem_and_state(form)
                publish_form_saved(form)

            _log_changes('filtered', cases, ledgers, [])

            # rebuild cases and ledgers that were affected
            for case in cases:
                if case.case_id in cases_needing_rebuild:
                    logger.info('Rebuilding case: %s', case.case_id)
                    if save:
                        # only rebuild cases that were updated
                        detail = FormReprocessRebuild(form_id=form.form_id)
                        interface.hard_rebuild_case(case.case_id, detail, lock=False)
                save and case_post_save.send(case.__class__, case=case)

            for ledger in ledgers:
                if ledger.ledger_reference in ledgers_updated:
                    logger.info('Rebuilding ledger: %s', ledger.ledger_reference)
                    if save:
                        # only rebuild upated ledgers
                        interface.ledger_processor.hard_rebuild_ledgers(**ledger.ledger_reference._asdict())

        else:
            if save:
                with bulk_atomic_blobs([form] + cases):
                    XFormInstance.save(form)  # use this save to that we don't overwrite the doc_type
                    XFormInstance.get_db().bulk_save(cases)
                stock_result.commit()

        save and case_stock_result.stock_result.finalize()
        save and case_stock_result.case_result.commit_dirtiness_flags()

    return ReprocessingResult(form, cases, ledgers)


def _log_changes(slug, cases, stock_updates, stock_deletes):
    if logger.isEnabledFor(logging.INFO):
        case_ids = [case.case_id for case in cases]
        logger.info(
            "%s changes:\n\tcases: %s\n\tstock changes%s\n\tstock deletes%s",
            slug, case_ids, stock_updates, stock_deletes
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


def _filter_already_processed_cases(form, cases):
    """Remove any cases that already have a case transaction for this form"""
    cases_by_id = {
        case.case_id: case
        for case in cases
    }
    for trans in CaseAccessorSQL.get_case_transactions_for_form(form.form_id, cases_by_id.keys()):
        del cases_by_id[trans.case_id]
    return cases_by_id.values()


def _filter_already_processed_ledgers(form, ledgers):
    """Remove any ledgers that already have a ledger transaction for this form"""
    ledgers_by_id = {
        ledger.ledger_reference: ledger
        for ledger in ledgers
    }
    case_ids = [ledger.case_id for ledger in ledgers]
    for trans in LedgerAccessorSQL.get_ledger_transactions_for_form(form.form_id, case_ids):
        del ledgers_by_id[trans.ledger_reference]
    return ledgers_by_id.values()


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
