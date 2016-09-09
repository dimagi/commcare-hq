import os
import uuid
from datetime import datetime

import settings
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xform import get_all_extensions_to_close, CaseProcessingResult
from corehq.apps.couch_sql_migration.diff import filter_form_diffs, filter_case_diffs, filter_ledger_diffs
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.tzmigration.api import force_phone_timezones_should_be_processed
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, doc_type_to_state, LedgerAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.models import (
    XFormInstanceSQL, XFormOperationSQL, XFormAttachmentSQL, CommCareCaseSQL,
    CaseTransaction, RebuildWithReason, CommCareCaseIndexSQL
)
from corehq.form_processor.submission_post import CaseStockProcessingResult
from corehq.form_processor.utils import adjust_datetimes
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import set_local_domain_sql_backend_override, \
    clear_local_domain_sql_backend_override
from corehq.util.log import with_progress_bar
from couchforms.models import XFormInstance, doc_types as form_doc_types, all_known_formlike_doc_types
from dimagi.utils.couch.undo import DELETED_SUFFIX
from fluff.management.commands.ptop_reindexer_fluff import ReindexEventHandler
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider

CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted', ]

UNPROCESSED_DOC_TYPES = list(all_known_formlike_doc_types() - {'XFormInstance'})


def do_couch_to_sql_migration(domain, with_progress=True):
    set_local_domain_sql_backend_override(domain)
    CouchSqlDomainMigrator(domain, with_progress=with_progress).migrate()


class CouchSqlDomainMigrator(object):
    def __init__(self, domain, with_progress=True):
        self.with_progress = with_progress
        from corehq.apps.tzmigration.planning import DiffDB

        assert should_use_sql_backend(domain)
        self.domain = domain
        db_filepath = get_diff_db_filepath(domain)
        self.diff_db = DiffDB.init(db_filepath)

    def migrate(self):
        self._process_main_forms()
        self._copy_unprocessed_forms()
        self._copy_unprocessed_cases()
        self._calculate_case_diffs()

    def _process_main_forms(self):
        last_received_on = datetime.min
        # process main forms (including cases and ledgers)
        changes = _get_main_form_iterator(self.domain).iter_all_changes()
        for change in self._with_progress(['XFormInstance'], changes):
            form = change.get_document()
            wrapped_form = XFormInstance.wrap(form)
            form_received = wrapped_form.received_on
            assert last_received_on <= form_received
            last_received_on = form_received
            self._migrate_form_and_associated_models(wrapped_form)

    def _migrate_form_and_associated_models(self, couch_form):
        from corehq.apps.tzmigration.timezonemigration import json_diff

        sql_form = _migrate_form(self.domain, couch_form)
        _migrate_form_attachments(sql_form, couch_form)
        _migrate_form_operations(sql_form, couch_form)

        diffs = json_diff(couch_form.to_json(), sql_form.to_json(), track_list_indices=False)
        self.diff_db.add_diffs(
            couch_form.doc_type, couch_form.form_id,
            filter_form_diffs(couch_form.doc_type, diffs)
        )

        case_stock_result = _get_case_and_ledger_updates(self.domain, sql_form)
        _save_migrated_models(sql_form, case_stock_result)

    def _copy_unprocessed_forms(self):
        from corehq.apps.tzmigration.timezonemigration import json_diff

        changes = _get_unprocessed_form_iterator(self.domain).iter_all_changes()
        for change in self._with_progress(UNPROCESSED_DOC_TYPES, changes):
            couch_form_json = change.get_document()
            couch_form = _wrap_form(couch_form_json)
            sql_form = XFormInstanceSQL(
                form_id=couch_form.form_id,
                xmlns=couch_form.xmlns,
                user_id=couch_form.user_id,
            )
            _copy_form_properties(self.domain, sql_form, couch_form)
            _migrate_form_attachments(sql_form, couch_form)
            _migrate_form_operations(sql_form, couch_form)

            if couch_form.doc_type != 'SubmissionErrorLog':
                diffs = json_diff(couch_form.to_json(), sql_form.to_json(), track_list_indices=False)
                self.diff_db.add_diffs(
                    couch_form.doc_type, couch_form.form_id,
                    filter_form_diffs(couch_form.doc_type, diffs)
                )

            _save_migrated_models(sql_form)

    def _copy_unprocessed_cases(self):
        doc_types = ['CommCareCase-Deleted']
        changes = _get_case_iterator(self.domain, doc_types=doc_types).iter_all_changes()
        for change in self._with_progress(doc_types, changes):
            couch_case = CommCareCase.wrap(change.get_document())
            sql_case = CommCareCaseSQL(
                case_id=couch_case.case_id,
                domain=self.domain,
                type=couch_case.type,
                name=couch_case.name,
                owner_id=couch_case.owner_id,
                opened_on=couch_case.opened_on,
                opened_by=couch_case.opened_by,
                modified_on=couch_case.modified_on,
                modified_by=couch_case.modified_by,
                server_modified_on=couch_case.server_modified_on,
                closed=couch_case.closed,
                closed_on=couch_case.closed_on,
                closed_by=couch_case.closed_by,
                deleted=True,
                deletion_id=couch_case.deletion_id,
                deleted_on=couch_case.deletion_date,
                external_id=couch_case.external_id,
                case_json=couch_case.dynamic_case_properties()
            )
            _migrate_case_actions(couch_case, sql_case)
            _migrate_case_indices(couch_case, sql_case)
            _migrate_case_attachments(couch_case, sql_case)
            CaseAccessorSQL.save_case(sql_case)

    def _calculate_case_diffs(self):
        cases = {}
        changes = _get_case_iterator(self.domain).iter_all_changes()
        for change in self._with_progress(CASE_DOC_TYPES, changes, progress_name='Calculating diffs'):
            cases[change.id] = change.get_document()
            if len(cases) == 1000:
                self._diff_cases(cases)
                cases = {}

        if cases:
            self._diff_cases(cases)

    def _diff_cases(self, couch_cases):
        from corehq.apps.tzmigration.timezonemigration import json_diff
        case_ids = list(couch_cases)
        sql_cases = CaseAccessorSQL.get_cases(case_ids)
        for sql_case in sql_cases:
            couch_case = couch_cases[sql_case.case_id]
            sql_case_json = sql_case.to_json()
            diffs = json_diff(couch_case, sql_case_json, track_list_indices=False)
            self.diff_db.add_diffs(
                couch_case['doc_type'], sql_case.case_id,
                filter_case_diffs(couch_case, sql_case_json, diffs)
            )

        self._diff_ledgers(case_ids)

    def _diff_ledgers(self, case_ids):
        from corehq.apps.tzmigration.timezonemigration import json_diff
        from corehq.apps.commtrack.models import StockState
        couch_state_map = {
            state.ledger_reference: state
            for state in StockState.objects.filter(case_id__in=case_ids)
        }

        for ledger_value in LedgerAccessorSQL.get_ledger_values_for_cases(case_ids):
            couch_state = couch_state_map.get(ledger_value.ledger_reference, None)
            diffs = json_diff(couch_state.to_json(), ledger_value.to_json(), track_list_indices=False)
            self.diff_db.add_diffs(
                'stock state', ledger_value.ledger_reference.as_id(),
                filter_ledger_diffs(diffs)
            )

    def _with_progress(self, doc_types, iterable, progress_name='Migrating'):
        if self.with_progress:
            doc_count = sum([
                get_doc_count_in_domain_by_type(self.domain, doc_type, XFormInstance.get_db())
                for doc_type in doc_types
            ])
            prefix = "{} ({})".format(progress_name, ', '.join(doc_types))
            return with_progress_bar(iterable, doc_count, prefix=prefix, oneline=False)
        else:
            return iterable


def _wrap_form(doc):
    if doc['doc_type'] in form_doc_types():
        return form_doc_types()[doc['doc_type']].wrap(doc)
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
    with force_phone_timezones_should_be_processed():
        adjust_datetimes(form_data)
    sql_form = interface.new_xform(form_data)
    return _copy_form_properties(domain, sql_form, couch_form)


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

    if couch_form.doc_type.endswith(DELETED_SUFFIX):
        doc_type = couch_form.doc_type[:-len(DELETED_SUFFIX)]
        sql_form.state = doc_type_to_state[doc_type] | XFormInstanceSQL.DELETED
    elif couch_form.doc_type == 'HQSubmission':
        sql_form.state = XFormInstanceSQL.NORMAL
    else:
        sql_form.state = doc_type_to_state[couch_form.doc_type]

    if couch_form.is_deleted:
        sql_form.deletion_id = couch_form.deletion_id
        sql_form.deleted_on = couch_form.deletion_date

    if couch_form.is_error:
        # doc_type != XFormInstance (includes deleted)
        sql_form.problem = getattr(couch_form, 'problem', None)
        sql_form.orig_id = getattr(couch_form, 'orig_id', None)

    if couch_form.is_deprecated or couch_form.is_deleted:
        sql_form.edited_on = getattr(couch_form, 'deprecated_date', None)

    if couch_form.is_submission_error_log:
        sql_form.xmlns = sql_form.xmlns or ''

    return sql_form


def _migrate_form_attachments(sql_form, couch_form):
    """Copy over attachement meta - includes form.xml"""
    attachments = []
    for name, blob in couch_form.blobs.iteritems():
        attachments.append(XFormAttachmentSQL(
            name=name,
            form=sql_form,
            attachment_id=uuid.uuid4().hex,
            content_type=blob.content_type,
            content_length=blob.content_length,
            blob_id=blob.id,
            blob_bucket=couch_form._blobdb_bucket(),
            md5=blob.info.md5_hash
        ))
    sql_form.unsaved_attachments = attachments


def _migrate_form_operations(sql_form, couch_form):
    for couch_form_op in couch_form.history:
        sql_form.track_create(XFormOperationSQL(
            form=sql_form,
            user_id=couch_form_op.user,
            date=couch_form_op.date,
            operation=couch_form_op.operation
        ))


def _migrate_case_actions(couch_case, sql_case):
    from casexml.apps.case import const
    transactions = {}
    for action in couch_case.actions:
        if action.xform_id and action.xform_id in transactions:
            transaction = transactions[action.xform_id]
        else:
            transaction = CaseTransaction(
                case=sql_case,
                form_id=action.xform_id,
                sync_log_id=action.sync_log_id,
                type=CaseTransaction.TYPE_FORM if action.xform_id else 0,
                server_date=action.server_date,
            )
            if action.xform_id:
                transactions[action.xform_id] = transaction
            else:
                sql_case.track_create(transaction)
        if action.action_type == const.CASE_ACTION_CREATE:
            transaction.type |= CaseTransaction.TYPE_CASE_CREATE
        if action.action_type == const.CASE_ACTION_CLOSE:
            transaction.type |= CaseTransaction.TYPE_CASE_CLOSE
        if action.action_type == const.CASE_ACTION_INDEX:
            transaction.type |= CaseTransaction.TYPE_CASE_INDEX
        if action.action_type == const.CASE_ACTION_ATTACHMENT:
            transaction.type |= CaseTransaction.TYPE_CASE_ATTACHMENT
        if action.action_type == const.CASE_ACTION_REBUILD:
            transaction.type = CaseTransaction.TYPE_REBUILD_WITH_REASON
            transaction.details = RebuildWithReason(reason="Unknown")

    for transaction in transactions.values():
        sql_case.track_create(transaction)


def _migrate_case_attachments(couch_case, sql_case):
    # TODO: maybe wait until case attachments are in blobdb
    pass


def _migrate_case_indices(couch_case, sql_case):
    for index in couch_case.indices:
        sql_case.track_create(CommCareCaseIndexSQL(
            case=sql_case,
            domain=couch_case.domain,
            identifier=index.identifier,
            referenced_id=index.referenced_id,
            referenced_type=index.referenced_type,
            relationship_id=CommCareCaseIndexSQL.RELATIONSHIP_MAP[index.relationship]
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


def _save_migrated_models(sql_form, case_stock_result=None):
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
        doc_types=UNPROCESSED_DOC_TYPES,
        event_handler=ReindexEventHandler(u'couch to sql migrator ({} unprocessed forms)'.format(domain)),
    )


def _get_case_iterator(domain, doc_types=None):
    doc_types = doc_types or CASE_DOC_TYPES
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=doc_types,
        event_handler=ReindexEventHandler(u'couch to sql migrator ({})'.format(domain)),
    )


def get_diff_db_filepath(domain):
    return os.path.join(settings.SHARED_DRIVE_CONF.restore_dir,
                        '{}-tzmigration.db'.format(domain))


def get_diff_db(domain):
    from corehq.apps.tzmigration.planning import DiffDB

    db_filepath = get_diff_db_filepath(domain)
    return DiffDB.open(db_filepath)


def delete_diff_db(domain):
    db_filepath = get_diff_db_filepath(domain)
    try:
        os.remove(db_filepath)
    except OSError as e:
        # continue if the file didn't exist to begin with
        # reraise on any other error
        if e.errno != 2:
            raise


def commit_migration(domain_name):
    domain = Domain.get_by_name(domain_name)
    domain.use_sql_backend = True
    domain.save()
    clear_local_domain_sql_backend_override(domain_name)
    assert should_use_sql_backend(domain_name)
