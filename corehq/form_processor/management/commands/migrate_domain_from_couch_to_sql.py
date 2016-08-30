from datetime import datetime
from django.core.management.base import LabelCommand, CommandError
from mock import MagicMock
from casexml.apps.case.xform import get_all_extensions_to_close, CaseProcessingResult
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import XFormInstanceSQL
from corehq.form_processor.submission_post import CaseStockProcessingResult
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import set_local_domain_sql_backend_override
from corehq.util.dates import iso_string_to_datetime
from couchforms.models import XFormInstance
from fluff.management.commands.ptop_reindexer_fluff import ReindexEventHandler
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider


class Command(LabelCommand):

    def handle_label(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(u'It looks like {} has already been migrated.'.format(domain))

        _do_couch_to_sql_migration(domain)


def _do_couch_to_sql_migration(domain):
    # (optional) collect some information about the domain's cases and forms for cross-checking
    set_local_domain_sql_backend_override(domain)
    assert should_use_sql_backend(domain)
    _process_main_forms(domain)
    _copy_unprocessed_forms(domain)
    # (optional) compare the information collected to the information at the beginning


def _process_main_forms(domain):
    last_received_on = datetime.min
    # process main forms (including cases and ledgers)
    for change in _get_main_form_iterator(domain).iter_all_changes():
        form = change.get_document()
        wrapped_form = XFormInstance.wrap(form)
        form_received = wrapped_form.received_on
        assert last_received_on <= form_received
        last_received_on = form_received
        print 'processing form {}: {}'.format(form['_id'], form_received)
        _migrate_form_and_associated_models(domain, wrapped_form)


def _get_main_form_iterator(domain):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=['XFormInstance'],
        event_handler=ReindexEventHandler(u'couch to sql migrator ({})'.format(domain)),
    )


def _migrate_form_and_associated_models(domain, couch_form):
    sql_form = _migrate_form_and_attachments(domain, couch_form)
    # todo: this should hopefully not be necessary once all attachments are in blobDB
    sql_form.get_xml = MagicMock(return_value=couch_form.get_xml())
    case_stock_result = _get_case_and_ledger_updates(domain, sql_form)
    _save_migrated_models(domain, sql_form, case_stock_result)


def _migrate_form_and_attachments(domain, couch_form):
    """
    This copies the couch form into a new sql form but does not save it.

    See form_processor.parsers.form._create_new_xform
    and SubmissionPost._set_submission_properties for what this should do.
    """
    interface = FormProcessorInterface(domain)

    form_data = couch_form.form
    # todo: timezone migration if we want here
    # adjust_datetimes(form_data)
    sql_form = interface.new_xform(form_data)
    assert isinstance(sql_form, XFormInstanceSQL)
    sql_form.domain = domain

    # todo: attachments.
    # note that if these are in the blobdb then we likely don't need to move them,
    # just need to bring the references across
    # interface.store_attachments(xform, attachments)

    # submission properties
    sql_form.auth_context = couch_form.auth_context
    sql_form.submit_ip = couch_form.submit_ip

    # todo: this property appears missing from sql forms - do we need it?
    # sql_form.path = couch_form.path

    sql_form.openrosa_headers = couch_form.openrosa_headers
    sql_form.last_sync_token = couch_form.last_sync_token
    sql_form.received_on = couch_form.received_on
    sql_form.date_header = couch_form.date_header
    sql_form.app_id = couch_form.app_id
    sql_form.build_id = couch_form.build_id
    # export_tag intentionally removed
    # sql_form.export_tag = ["domain", "xmlns"]
    sql_form.partial_submission = couch_form.partial_submission
    return sql_form


def _get_case_and_ledger_updates(domain, sql_form):
    """
    Get a CaseStockProcessingResult with the appropriate cases and ledgers to
    be saved.

    See SubmissionPost.process_xforms_for_cases and methods it calls for the equivalent
    section of the form-processing code.
    """
    from casexml.apps.case.xform import get_and_check_xform_domain
    from corehq.apps.commtrack.processing import process_stock

    interface = FormProcessorInterface(domain)

    get_and_check_xform_domain(sql_form)
    xforms = [sql_form]

    # todo: I think this can be changed to lock=False
    with interface.casedb_cache(domain=domain, lock=True, deleted_ok=True, xforms=xforms) as case_db:
        touched_cases = FormProcessorInterface(domain).get_cases_from_forms(case_db, xforms)
        extensions_to_close = get_all_extensions_to_close(domain, touched_cases.values())
        case_result = CaseProcessingResult(
            domain,
            [update.case for update in touched_cases.values()],
            [],  # ignore dirtiness_flags,
            extensions_to_close
        )
        # todo: is this necessary?
        for case in case_result.cases:
            case_db.mark_changed(case)

        stock_result = process_stock(xforms, case_db)
        cases = case_db.get_cases_for_saving(sql_form.received_on)
        stock_result.populate_models()

    return CaseStockProcessingResult(
        case_result=case_result,
        case_models=cases,
        stock_result=stock_result,
    )


def _save_migrated_models(domain, sql_form, case_stock_result):
    """
    See SubmissionPost.save_processed_models for ~what this should do.
    However, note that that function does some things that this one shouldn't,
    e.g. process ownership cleanliness flags.
    """
    interface = FormProcessorInterface(domain)
    interface.save_processed_models(
        [sql_form],
        case_stock_result.case_models,
        case_stock_result.stock_result
    )
    case_stock_result.case_result.close_extensions()


def _copy_unprocessed_forms(domain):
    # copy unprocessed forms
    for change in _get_unprocessed_form_iterator(domain).iter_all_changes():
        form = change.get_document()
        print 'copying unprocessed {} {}: {}'.format(form['doc_type'], form['_id'], form['received_on'])
        # save updated models


def _get_unprocessed_form_iterator(domain):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=[
            'XFormArchived',
            'XFormError',
            'XFormDeprecated',
            'XFormDuplicate',
            # todo: need to figure out which of these we plan on supporting
            'XFormInstance-Deleted',
            'HQSubmission',
            'SubmissionErrorLog',
        ],
        event_handler=ReindexEventHandler(u'couch to sql migrator ({} unprocessed forms)'.format(domain)),
    )
