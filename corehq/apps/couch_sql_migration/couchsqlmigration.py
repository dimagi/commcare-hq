import os
import uuid
from datetime import datetime

import settings
from casexml.apps.case.xform import get_all_extensions_to_close, CaseProcessingResult
from corehq.apps.tzmigration.planning import DiffDB
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, XFormAttachmentSQL
from corehq.form_processor.submission_post import CaseStockProcessingResult
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import set_local_domain_sql_backend_override
from couchforms.models import XFormInstance, doc_types
from fluff.management.commands.ptop_reindexer_fluff import ReindexEventHandler
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider


def do_couch_to_sql_migration(domain):
    # (optional) collect some information about the domain's cases and forms for cross-checking
    set_local_domain_sql_backend_override(domain)
    CouchSqlDomainMigrator(domain).migrate()
    # (optional) compare the information collected to the information at the beginning


class CouchSqlDomainMigrator(object):
    def __init__(self, domain):
        assert should_use_sql_backend(domain)
        self.domain = domain
        db_filepath = get_diff_db_filepath(domain)
        self.diff_db = DiffDB.init(db_filepath)

    def migrate(self):
        self._process_main_forms()
        self._copy_unprocessed_forms()

    def _process_main_forms(self):
        last_received_on = datetime.min
        # process main forms (including cases and ledgers)
        for change in _get_main_form_iterator(self.domain).iter_all_changes():
            form = change.get_document()
            wrapped_form = XFormInstance.wrap(form)
            form_received = wrapped_form.received_on
            assert last_received_on <= form_received
            last_received_on = form_received
            print 'processing form {}: {}'.format(form['_id'], form_received)
            self._migrate_form_and_associated_models(wrapped_form)

    def _migrate_form_and_associated_models(self, couch_form):
        sql_form = _migrate_form(self.domain, couch_form)
        _migrate_form_attachments(sql_form, couch_form)
        _migrate_form_operations(sql_form, couch_form)

        self.diff_db.add_diffs(
            'form', couch_form.form_id,
            json_diff(couch_form.to_json(), sql_form.to_json())
        )

        case_stock_result = _get_case_and_ledger_updates(self.domain, sql_form)
        _save_migrated_models(self.domain, sql_form, case_stock_result)

    def _copy_unprocessed_forms(self):
        for change in _get_unprocessed_form_iterator(self.domain).iter_all_changes():
            couch_form_json = change.get_document()
            couch_form = _wrap_form(couch_form_json)
            print 'copying unprocessed {} {}: {}'.format(couch_form.doc_type, couch_form.form_id, couch_form.received_on)
            sql_form = XFormInstanceSQL(
                form_id=couch_form.form_id,
                xmlns=couch_form.xmlns,
                user_id=couch_form.user_id,
            )
            _copy_form_properties(self.domain, sql_form, couch_form)
            _migrate_form_attachments(sql_form, couch_form)
            _migrate_form_operations(sql_form, couch_form)

            self.diff_db.add_diffs(
                'form', couch_form.form_id,
                json_diff(couch_form.to_json(), sql_form.to_json())
            )

            _save_migrated_models(self.domain, sql_form)


def _wrap_form(doc):
    if doc['doc_type'] in doc_types():
        return doc_types()[doc['doc_type']].wrap(doc)
    if doc['doc_type'] in ("XFormInstance-Deleted", "HQSubmission"):
        return XFormInstance.wrap(doc)


def _migrate_form(domain, couch_form):
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
    _copy_form_properties(domain, sql_form, couch_form)


def _copy_form_properties(domain, sql_form, couch_form):
    assert isinstance(sql_form, XFormInstanceSQL)
    sql_form.domain = domain

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
    sql_form.initial_processing_complete = couch_form.initial_processing_complete
    return sql_form


def _migrate_form_attachments(sql_form, couch_form):
    """Copy over attachement meta - includes form.xml"""
    for name, blob in couch_form.blobs.iteritems():
        sql_form.track_create(XFormAttachmentSQL(
            name=name,
            form=sql_form,
            attachment_id=uuid.uuid4().hex,
            content_type=blob.content_type,
            content_length=blob.content_length,
            blob_id=blob.id,
            md5=blob.info.md5_hash
        ))


def _migrate_form_operations(sql_form, couch_form):
    for couch_form_op in couch_form.history:
        sql_form.track_create(XFormOperationSQL(
            form=sql_form,
            user_id=couch_form_op.user,
            date=couch_form_op.date,
            operation=couch_form_op.operation
        ))


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

    with interface.casedb_cache(domain=domain, lock=False, deleted_ok=True, xforms=xforms) as case_db:
        touched_cases = FormProcessorInterface(domain).get_cases_from_forms(case_db, xforms)
        extensions_to_close = get_all_extensions_to_close(domain, touched_cases.values())
        case_result = CaseProcessingResult(
            domain,
            [update.case for update in touched_cases.values()],
            [],  # ignore dirtiness_flags,
            extensions_to_close
        )
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


def _save_migrated_models(domain, sql_form, case_stock_result=None):
    """
    See SubmissionPost.save_processed_models for ~what this should do.
    However, note that that function does some things that this one shouldn't,
    e.g. process ownership cleanliness flags.
    """
    forms_tuple = ProcessedForms(sql_form, None)
    stock_result = case_stock_result.stock_result if case_stock_result else None
    if stock_result:
        assert stock_result.populated
    return FormProcessorSQL.save_processed_models(
        forms_tuple,
        cases=case_stock_result.case_models if case_stock_result else None,
        stock_result=stock_result,
        publish_to_kafka=False
    )


def _get_main_form_iterator(domain):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=['XFormInstance'],
        event_handler=ReindexEventHandler(u'couch to sql migrator ({})'.format(domain)),
    )


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


def get_diff_db_filepath(domain):
    return os.path.join(settings.SHARED_DRIVE_CONF.restore_dir,
                        '{}-tzmigration.db'.format(domain))


def get_diff_db(domain):
    db_filepath = get_diff_db_filepath(domain)
    return DiffDB.open(db_filepath)


def delete_planning_db(domain):
    db_filepath = get_diff_db_filepath(domain)
    try:
        os.remove(db_filepath)
    except OSError as e:
        # continue if the file didn't exist to begin with
        # reraise on any other error
        if e.errno != 2:
            raise
