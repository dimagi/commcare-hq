from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import sys
from datetime import datetime

import gevent
import six
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.xform import (
    CaseProcessingResult,
    get_all_extensions_to_close,
    get_case_updates,
)
from casexml.apps.case.xml.parser import CaseNoopAction
from django.conf import settings
from django.db.utils import IntegrityError
from gevent.pool import Pool

from corehq.apps.couch_sql_migration.asyncforms import AsyncFormProcessor
from corehq.apps.couch_sql_migration.casediff import CaseDiffProcess
from corehq.apps.couch_sql_migration.diff import filter_form_diffs
from corehq.apps.couch_sql_migration.statedb import init_state_db
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.tzmigration.api import force_phone_timezones_should_be_processed
from corehq.blobs import CODES, get_blob_db, NotFound as BlobNotFound
from corehq.blobs.models import BlobMeta
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    doc_type_to_state,
)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import AttachmentNotFound
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.models import (
    CaseAttachmentSQL,
    CaseTransaction,
    CommCareCaseIndexSQL,
    CommCareCaseSQL,
    RebuildWithReason,
    XFormInstanceSQL,
    XFormOperationSQL,
)
from corehq.form_processor.parsers.ledgers.form import MissingFormXml
from corehq.form_processor.submission_post import CaseStockProcessingResult
from corehq.form_processor.utils import (
    adjust_datetimes,
    extract_meta_user_id,
    should_use_sql_backend,
)
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
    set_local_domain_sql_backend_override,
)
from corehq.toggles import (
    COUCH_SQL_MIGRATION_BLACKLIST,
    NAMESPACE_DOMAIN,
)
from corehq.util import cache_utils
from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value
from corehq.util.log import with_progress_bar
from corehq.util.pagination import PaginationEventHandler
from corehq.util.timer import TimingContext
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from couchforms.models import doc_types as form_doc_types
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider

log = logging.getLogger(__name__)

CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted', ]

UNPROCESSED_DOC_TYPES = list(all_known_formlike_doc_types() - {'XFormInstance'})


def setup_logging(log_dir, debug=False):
    if debug:
        assert log.level <= logging.DEBUG, log.level
        logging.root.setLevel(logging.DEBUG)
        for handler in logging.root.handlers:
            if handler.name in ["file", "console"]:
                handler.setLevel(logging.DEBUG)
    if not log_dir:
        return
    time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, "couch2sql-form-case-{}.log".format(time))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    log.info("command: %s", " ".join(sys.argv))


def do_couch_to_sql_migration(domain, state_dir, with_progress=True):
    set_local_domain_sql_backend_override(domain)
    CouchSqlDomainMigrator(domain, state_dir, with_progress).migrate()


class CouchSqlDomainMigrator(object):
    def __init__(self, domain, state_dir, with_progress=True):
        self._check_for_migration_restrictions(domain)
        self.with_progress = with_progress
        self.domain = domain
        self.statedb = init_state_db(domain, state_dir)
        self.case_diff_queue = CaseDiffProcess(self.statedb)
        # exit immediately on uncaught greenlet error
        gevent.get_hub().SYSTEM_ERROR = BaseException

    def migrate(self):
        log.info('migrating domain {}'.format(self.domain))

        self.processed_docs = 0
        timing = TimingContext("couch_sql_migration")
        with timing as timing_context, self.case_diff_queue:
            self.timing_context = timing_context
            with timing_context('main_forms'):
                self._process_main_forms()
            with timing_context("unprocessed_forms"):
                self._copy_unprocessed_forms()
            with timing_context("unprocessed_cases"):
                self._copy_unprocessed_cases()

        self._send_timings(timing_context)
        log.info('migrated domain {}'.format(self.domain))

    def _process_main_forms(self):
        """process main forms (including cases and ledgers)"""
        with AsyncFormProcessor(self.statedb, self._migrate_form) as pool:
            changes = self._get_resumable_iterator(['XFormInstance'], 'main_forms')
            for change in self._with_progress(['XFormInstance'], changes):
                pool.process_xform(change.get_document())

        self._log_main_forms_processed_count()

    def _migrate_form(self, wrapped_form, case_ids):
        set_local_domain_sql_backend_override(self.domain)
        form_id = wrapped_form.form_id
        try:
            self._migrate_form_and_associated_models(wrapped_form)
        except Exception:
            log.exception("Unable to migrate form: %s", form_id)
        finally:
            self.processed_docs += 1
            self.case_diff_queue.update(case_ids, form_id)
            self._log_main_forms_processed_count(throttled=True)

    def _migrate_form_and_associated_models(self, couch_form, form_is_processed=True):
        """
        Copies `couch_form` into a new sql form
        """
        if form_is_processed:
            form_data = couch_form.form
            with force_phone_timezones_should_be_processed():
                adjust_datetimes(form_data)
            xmlns = form_data.get("@xmlns", "")
            user_id = extract_meta_user_id(form_data)
        else:
            xmlns = couch_form.xmlns
            user_id = couch_form.user_id
        sql_form = XFormInstanceSQL(
            form_id=couch_form.form_id,
            domain=self.domain,
            xmlns=xmlns,
            user_id=user_id,
        )
        _copy_form_properties(sql_form, couch_form)
        _migrate_form_attachments(sql_form, couch_form)
        _migrate_form_operations(sql_form, couch_form)
        if couch_form.doc_type != 'SubmissionErrorLog':
            self._save_diffs(couch_form, sql_form)
        case_stock_result = self._get_case_stock_result(sql_form, couch_form) if form_is_processed else None
        _save_migrated_models(sql_form, case_stock_result)

    def _save_diffs(self, couch_form, sql_form):
        from corehq.apps.tzmigration.timezonemigration import json_diff
        couch_form_json = couch_form.to_json()
        sql_form_json = sql_form_to_json(sql_form)
        diffs = json_diff(couch_form_json, sql_form_json, track_list_indices=False)
        self.statedb.add_diffs(
            couch_form.doc_type, couch_form.form_id,
            filter_form_diffs(couch_form_json, sql_form_json, diffs)
        )

    def _get_case_stock_result(self, sql_form, couch_form):
        case_stock_result = None
        if sql_form.initial_processing_complete:
            case_stock_result = _get_case_and_ledger_updates(self.domain, sql_form)
            if case_stock_result.case_models:
                has_noop_update = any(
                    len(update.actions) == 1 and isinstance(update.actions[0], CaseNoopAction)
                    for update in get_case_updates(couch_form)
                )
                if has_noop_update:
                    # record these for later use when filtering case diffs.
                    # See ``_filter_forms_touch_case``
                    self.statedb.add_no_action_case_form(couch_form.form_id)
        return case_stock_result

    def _copy_unprocessed_forms(self):
        pool = Pool(10)
        problems = self.statedb.iter_problem_forms()
        for couch_form_json in iter_docs(XFormInstance.get_db(), problems, chunksize=1000):
            assert couch_form_json['problem']
            couch_form_json['doc_type'] = 'XFormError'
            pool.spawn(self._migrate_unprocessed_form, couch_form_json)

        changes = self._get_resumable_iterator(UNPROCESSED_DOC_TYPES, 'unprocessed_forms')
        for change in self._with_progress(UNPROCESSED_DOC_TYPES, changes):
            couch_form_json = change.get_document()
            pool.spawn(self._migrate_unprocessed_form, couch_form_json)

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        self._log_unprocessed_forms_processed_count()

    def _migrate_unprocessed_form(self, couch_form_json):
        log.debug('Processing doc: {}({})'.format(couch_form_json['doc_type'], couch_form_json['_id']))
        try:
            couch_form = _wrap_form(couch_form_json)
            self._migrate_form_and_associated_models(couch_form, form_is_processed=False)
            self.processed_docs += 1
            self._log_unprocessed_forms_processed_count(throttled=True)
        except Exception:
            log.exception("Error migrating form %s", couch_form_json["_id"])

    def _copy_unprocessed_cases(self):
        doc_types = ['CommCareCase-Deleted']
        pool = Pool(10)
        changes = self._get_resumable_iterator(doc_types, 'unprocessed_cases')
        for change in self._with_progress(doc_types, changes):
            pool.spawn(self._copy_unprocessed_case, change)

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        self._log_unprocessed_cases_processed_count()

    def _copy_unprocessed_case(self, change):
        doc = change.get_document()
        couch_case = CommCareCase.wrap(doc)
        log.debug('Processing doc: {}({})'.format(couch_case['doc_type'], change.id))
        try:
            first_action = couch_case.actions[0]
        except IndexError:
            first_action = CommCareCaseAction()

        sql_case = CommCareCaseSQL(
            case_id=couch_case.case_id,
            domain=self.domain,
            type=couch_case.type or '',
            name=couch_case.name,
            owner_id=couch_case.owner_id or couch_case.user_id or '',
            opened_on=couch_case.opened_on or first_action.date,
            opened_by=couch_case.opened_by or first_action.user_id,
            modified_on=couch_case.modified_on,
            modified_by=couch_case.modified_by or couch_case.user_id or '',
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
        try:
            CaseAccessorSQL.save_case(sql_case)
        except IntegrityError:
            # case re-created by form processing so just mark the case as deleted
            CaseAccessorSQL.soft_delete_cases(
                self.domain,
                [sql_case.case_id],
                sql_case.deleted_on,
                sql_case.deletion_id
            )

        self.case_diff_queue.enqueue(doc)
        self.processed_docs += 1
        self._log_unprocessed_cases_processed_count(throttled=True)

    def _check_for_migration_restrictions(self, domain_name):
        msgs = []
        if not should_use_sql_backend(domain_name):
            msgs.append("does not have SQL backend enabled")
        if COUCH_SQL_MIGRATION_BLACKLIST.enabled(domain_name, NAMESPACE_DOMAIN):
            msgs.append("is blacklisted")
        if domain_name in settings.DOMAIN_MODULE_MAP:
            msgs.append("has custom reports")
        if msgs:
            raise MigrationRestricted("{}: {}".format(domain_name, "; ".join(msgs)))

    def _with_progress(self, doc_types, iterable, progress_name='Migrating'):
        doc_count = sum([
            get_doc_count_in_domain_by_type(self.domain, doc_type, XFormInstance.get_db())
            for doc_type in doc_types
        ])
        if self.timing_context:
            current_timer = self.timing_context.peek()
            current_timer.normalize_denominator = doc_count

        if self.with_progress:
            prefix = "{} ({})".format(progress_name, ', '.join(doc_types))
            return with_progress_bar(iterable, doc_count, prefix=prefix, oneline=False)
        else:
            log.info("{} ({})".format(doc_count, ', '.join(doc_types)))
            return iterable

    def _log_processed_docs_count(self, tags, throttled=False):
        if throttled and self.processed_docs < 100:
            return

        processed_docs = self.processed_docs
        self.processed_docs = 0

        datadog_counter("commcare.couchsqlmigration.processed_docs",
                        value=processed_docs,
                        tags=tags)

    def _log_main_forms_processed_count(self, throttled=False):
        self._log_processed_docs_count(['type:main_forms'], throttled)

    def _log_unprocessed_forms_processed_count(self, throttled=False):
        self._log_processed_docs_count(['type:unprocessed_forms'], throttled)

    def _log_unprocessed_cases_processed_count(self, throttled=False):
        self._log_processed_docs_count(['type:unprocessed_cases'], throttled)

    def _get_resumable_iterator(self, doc_types, slug):
        key = "%s.%s.%s" % (self.domain, slug, self.statedb.unique_id)
        return _iter_changes(self.domain, doc_types, resumable_key=key)

    def _send_timings(self, timing_context):
        metric_name_template = "commcare.%s.count"
        metric_name_template_normalized = "commcare.%s.count.normalized"
        for timing in timing_context.to_list():
            datadog_counter(
                metric_name_template % timing.full_name,
                tags=['duration:%s' % bucket_value(timing.duration, TIMING_BUCKETS)])
            normalize_denominator = getattr(timing, 'normalize_denominator', None)
            if normalize_denominator:
                datadog_counter(
                    metric_name_template_normalized % timing.full_name,
                    tags=['duration:%s' % bucket_value(timing.duration / normalize_denominator,
                                                       NORMALIZED_TIMING_BUCKETS)])


TIMING_BUCKETS = (0.1, 1, 5, 10, 30, 60, 60 * 5, 60 * 10, 60 * 60, 60 * 60 * 12, 60 * 60 * 24)
NORMALIZED_TIMING_BUCKETS = (0.001, 0.01, 0.1, 0.25, 0.5, 0.75, 1, 2, 3, 5, 10, 30)


def _wrap_form(doc):
    if doc['doc_type'] in form_doc_types():
        return form_doc_types()[doc['doc_type']].wrap(doc)
    if doc['doc_type'] in ("XFormInstance-Deleted", "HQSubmission"):
        return XFormInstance.wrap(doc)


def _copy_form_properties(sql_form, couch_form):
    assert isinstance(sql_form, XFormInstanceSQL)

    # submission properties
    sql_form.auth_context = couch_form.auth_context
    sql_form.submit_ip = couch_form.submit_ip

    # todo: this property appears missing from sql forms - do we need it?
    # sql_form.path = couch_form.path

    sql_form.openrosa_headers = couch_form.openrosa_headers
    sql_form.last_sync_token = couch_form.last_sync_token
    sql_form.server_modified_on = couch_form.server_modified_on
    sql_form.received_on = couch_form.received_on
    sql_form.date_header = couch_form.date_header
    sql_form.app_id = couch_form.app_id
    sql_form.build_id = couch_form.build_id
    # export_tag intentionally removed
    # sql_form.export_tag = ["domain", "xmlns"]
    sql_form.partial_submission = couch_form.partial_submission
    sql_form.initial_processing_complete = couch_form.initial_processing_complete in (None, True)

    if couch_form.doc_type.endswith(DELETED_SUFFIX):
        doc_type = couch_form.doc_type[:-len(DELETED_SUFFIX)]
        sql_form.state = doc_type_to_state[doc_type] | XFormInstanceSQL.DELETED
    elif couch_form.doc_type == 'HQSubmission':
        sql_form.state = XFormInstanceSQL.NORMAL
    else:
        sql_form.state = doc_type_to_state[couch_form.doc_type]

    sql_form.deletion_id = couch_form.deletion_id
    sql_form.deleted_on = couch_form.deletion_date

    sql_form.deprecated_form_id = getattr(couch_form, 'deprecated_form_id', None)

    if couch_form.is_error:
        # doc_type != XFormInstance (includes deleted)
        sql_form.problem = getattr(couch_form, 'problem', None)
        sql_form.orig_id = getattr(couch_form, 'orig_id', None)

    sql_form.edited_on = getattr(couch_form, 'edited_on', None)
    if couch_form.is_deprecated:
        sql_form.edited_on = getattr(couch_form, 'deprecated_date', sql_form.edited_on)

    if couch_form.is_submission_error_log:
        sql_form.xmlns = sql_form.xmlns or ''

    return sql_form


def _migrate_form_attachments(sql_form, couch_form):
    """Copy over attachment meta - includes form.xml"""
    attachments = []
    metadb = get_blob_db().metadb

    def try_to_get_blob_meta(parent_id, type_code, name):
        try:
            meta = metadb.get(
                parent_id=parent_id,
                type_code=type_code,
                name=name
            )
            assert meta.domain == couch_form.domain, (meta.domain, couch_form.domain)
            return meta
        except BlobMeta.DoesNotExist:
            return None

    if couch_form._attachments and any(
        name not in couch_form.blobs for name in couch_form._attachments
    ):
        _migrate_couch_attachments_to_blob_db(couch_form)

    for name, blob in six.iteritems(couch_form.blobs):
        type_code = CODES.form_xml if name == "form.xml" else CODES.form_attachment
        meta = try_to_get_blob_meta(sql_form.form_id, type_code, name)

        # there was a bug in a migration causing the type code for many form attachments to be set as form_xml
        # this checks the db for a meta resembling this and fixes it for postgres
        # https://github.com/dimagi/commcare-hq/blob/3788966119d1c63300279418a5bf2fc31ad37f6f/corehq/blobs/migrate.py#L371
        if not meta and name != "form.xml":
            meta = try_to_get_blob_meta(sql_form.form_id, CODES.form_xml, name)
            if meta:
                meta.type_code = CODES.form_attachment
                meta.save()

        if not meta:
            meta = metadb.new(
                domain=couch_form.domain,
                name=name,
                parent_id=sql_form.form_id,
                type_code=type_code,
                content_type=blob.content_type,
                content_length=blob.content_length,
                key=blob.key,
            )
            meta.save()

        attachments.append(meta)
    sql_form.attachments_list = attachments


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


def _migrate_couch_attachments_to_blob_db(couch_form):
    """Migrate couch attachments to blob db

    Should have already been done, but somehow some forms still have not
    been migrated. This operation is not reversible. It will permanently
    mutate the couch document.
    """
    from couchdbkit.client import Document

    log.warning("migrating couch attachments for form %s", couch_form.form_id)
    blobs = couch_form.blobs
    doc = Document(couch_form.get_db().cloudant_database, couch_form.form_id)
    with couch_form.atomic_blobs():
        for name, meta in six.iteritems(couch_form._attachments):
            if name not in blobs:
                couch_form.put_attachment(
                    doc.get_attachment(name, attachment_type='binary'),
                    name,
                    content_type=meta.get("content_type"),
                )
        assert not set(couch_form._attachments) - set(couch_form.blobs), couch_form


def sql_form_to_json(form):
    """Serialize SQL form to JSON

    Handles missing form XML gracefully.
    """
    try:
        form.get_xml()
    except (AttachmentNotFound, BlobNotFound):
        form.get_xml.get_cache(form)[()] = ""
        assert form.get_xml() == "", form.get_xml()
    return form.to_json()


def _migrate_case_attachments(couch_case, sql_case):
    """Copy over attachment meta """
    for name, attachment in six.iteritems(couch_case.case_attachments):
        blob = couch_case.blobs[name]
        assert name == attachment.identifier or not attachment.identifier or not name, \
            (name, attachment.identifier)
        sql_case.track_create(CaseAttachmentSQL(
            name=name or attachment.identifier,
            case=sql_case,
            content_type=attachment.server_mime,
            content_length=attachment.content_length,
            blob_id=blob.id,
            blob_bucket=couch_case._blobdb_bucket(),
            properties=attachment.attachment_properties,
            md5=attachment.server_md5
        ))


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
    from corehq.apps.commtrack.processing import process_stock

    interface = FormProcessorInterface(domain)

    assert sql_form.domain
    xforms = [sql_form]

    with interface.casedb_cache(
        domain=domain, lock=False, deleted_ok=True, xforms=xforms,
        load_src="couchsqlmigration",
    ) as case_db:
        touched_cases = FormProcessorInterface(domain).get_cases_from_forms(case_db, xforms)
        extensions_to_close = get_all_extensions_to_close(domain, list(touched_cases.values()))
        case_result = CaseProcessingResult(
            domain,
            [update.case for update in touched_cases.values()],
            [],  # ignore dirtiness_flags,
            extensions_to_close
        )
        for case in case_result.cases:
            case_db.post_process_case(case, sql_form)
            case_db.mark_changed(case)
        cases = case_result.cases

        try:
            stock_result = process_stock(xforms, case_db)
            cases = case_db.get_cases_for_saving(sql_form.received_on)
            stock_result.populate_models()
        except MissingFormXml:
            stock_result = None

    return CaseStockProcessingResult(
        case_result=case_result,
        case_models=cases,
        stock_result=stock_result,
    )


def _save_migrated_models(sql_form, case_stock_result):
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


class MigrationPaginationEventHandler(PaginationEventHandler):
    RETRIES = 5

    def __init__(self, domain):
        self.domain = domain
        self.retries = self.RETRIES

    def _cache_key(self):
        return "couchsqlmigration.%s" % self.domain

    def page_end(self, total_emitted, duration, *args, **kwargs):
        self.retries = self.RETRIES
        cache_utils.clear_limit(self._cache_key())

    def page_exception(self, e):
        if self.retries <= 0:
            return False

        self.retries -= 1
        gevent.sleep(1)
        return True


def _iter_changes(domain, doc_types, **kw):
    return CouchDomainDocTypeChangeProvider(
        couch_db=XFormInstance.get_db(),
        domains=[domain],
        doc_types=doc_types,
        event_handler=MigrationPaginationEventHandler(domain),
    ).iter_all_changes(**kw)


def commit_migration(domain_name):
    domain_obj = Domain.get_by_name(domain_name, strict=True)
    domain_obj.use_sql_backend = True
    domain_obj.save()
    clear_local_domain_sql_backend_override(domain_name)
    if not should_use_sql_backend(domain_name):
        Domain.get_by_name.clear(Domain, domain_name)
        assert should_use_sql_backend(domain_name), \
            "could not set use_sql_backend for domain %s (try again)" % domain_name
    datadog_counter("commcare.couch_sql_migration.total_committed")
    log.info("committed migration for {}".format(domain_name))


class MigrationRestricted(Exception):
    pass
