import json
import logging
import os
import signal
import sys
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import partial
from threading import Lock

from django.conf import settings
from django.db.utils import IntegrityError

import attr
from gevent.pool import Pool
from memoized import memoized

from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.xform import (
    CaseProcessingResult,
    get_case_updates,
)
from casexml.apps.case.xml.parser import CaseNoopAction
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from couchforms.models import doc_types as form_doc_types
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs, retry_on_couch_error
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.tzmigration.api import (
    force_phone_timezones_should_be_processed,
)
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.mixin import BlobMetaRef
from corehq.form_processor.backends.couch.dbaccessors import CaseAccessorCouch
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
    doc_type_to_state,
)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import (
    AttachmentNotFound,
    MissingFormXml,
    XFormNotFound,
    CaseSaveError)
from corehq.form_processor.interfaces.processor import (
    FormProcessorInterface,
    ProcessedForms,
)
from corehq.form_processor.models import (
    Attachment,
    CaseAttachmentSQL,
    CaseTransaction,
    CommCareCaseIndexSQL,
    CommCareCaseSQL,
    RebuildWithReason,
    XFormInstanceSQL,
    XFormOperationSQL,
)
from corehq.form_processor.submission_post import CaseStockProcessingResult
from corehq.form_processor.system_action import SYSTEM_ACTION_XMLNS
from corehq.form_processor.utils import (
    adjust_datetimes,
    extract_meta_user_id,
    should_use_sql_backend,
)
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
    set_local_domain_sql_backend_override,
)
from corehq.form_processor.utils.xform import convert_xform_to_json
from corehq.toggles import COUCH_SQL_MIGRATION_BLACKLIST, NAMESPACE_DOMAIN
from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.datadog.gauges import datadog_counter
from corehq.util.datadog.utils import bucket_value
from corehq.util.log import with_progress_bar
from corehq.util.pagination import (
    PaginationEventHandler,
    ResumableFunctionIterator,
    StopToResume,
)
from corehq.util.timer import TimingContext

from .asyncforms import AsyncFormProcessor, get_case_ids
from .casediff import diff_form_state
from .casediffqueue import CaseDiffProcess, CaseDiffQueue, NoCaseDiff
from .json2xml import convert_form_to_xml
from .statedb import init_state_db
from .staterebuilder import iter_unmigrated_docs
from .system_action import do_system_action
from .util import get_ids_from_string_or_file, exit_on_error, str_to_datetime

log = logging.getLogger(__name__)

CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted', ]

UNPROCESSED_DOC_TYPES = list(all_known_formlike_doc_types() - {'XFormInstance'})


def setup_logging(log_dir, slug, debug=False):
    if debug:
        assert log.level <= logging.DEBUG, log.level
        logging.root.setLevel(logging.DEBUG)
        for handler in logging.root.handlers:
            if handler.name in ["file", "console"]:
                handler.setLevel(logging.DEBUG)
    if not log_dir:
        return
    time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, f"couch2sql-form-case-{time}-{slug}.log")
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    log.info("command: %s", " ".join(sys.argv))


def do_couch_to_sql_migration(domain, state_dir, **kw):
    set_local_domain_sql_backend_override(domain)
    CouchSqlDomainMigrator(domain, state_dir, **kw).migrate()


class CouchSqlDomainMigrator:
    def __init__(
        self,
        domain,
        state_dir,
        with_progress=True,
        live_migrate=False,
        diff_process=True,
        rebuild_state=False,
        stop_on_error=False,
        forms=None,
    ):
        self._check_for_migration_restrictions(domain)
        self.domain = domain
        self.with_progress = with_progress
        self.live_migrate = live_migrate
        self.stopper = Stopper(live_migrate)
        self.statedb = init_state_db(domain, state_dir)
        self.counter = DocCounter(self.statedb)
        if rebuild_state:
            self.statedb.is_rebuild = True
        if diff_process is None:
            diff_queue = NoCaseDiff
        elif diff_process:
            diff_queue = CaseDiffProcess
        else:
            diff_queue = CaseDiffQueue
        self.stop_on_error = stop_on_error
        self.forms = forms
        self.case_diff_queue = diff_queue(self.statedb)

    def migrate(self):
        log.info('{live}migrating domain {domain} ({state})'.format(
            live=("live " if self.live_migrate else ""),
            domain=self.domain,
            state=self.statedb.unique_id,
        ))
        patch = migration_patches()
        with self.counter, patch, self.case_diff_queue, self.stopper:
            if self.forms:
                self._process_forms_subset(self.forms)
                return
            self._process_main_forms()
            self._copy_unprocessed_forms()
            self._copy_unprocessed_cases()

        log.info('migrated domain {}'.format(self.domain))

    def _process_main_forms(self):
        """process main forms (including cases and ledgers)"""
        def migrate_form(form, case_ids):
            self._migrate_form(form, case_ids)
            add_form()
        with self.counter('main_forms', 'XFormInstance') as add_form, \
                AsyncFormProcessor(self.statedb, migrate_form) as pool:
            for doc in self._get_resumable_iterator(['XFormInstance']):
                pool.process_xform(doc)

    def _migrate_form(self, couch_form, case_ids, **kw):
        set_local_domain_sql_backend_override(self.domain)
        form_id = couch_form.form_id
        self._migrate_form_and_associated_models(couch_form, **kw)
        self.case_diff_queue.update(case_ids, form_id)

    def _migrate_form_and_associated_models(self, couch_form, form_is_processed=True):
        """
        Copies `couch_form` into a new sql form
        """
        sql_form = None
        try:
            if form_is_processed:
                form_data = couch_form.form
                with force_phone_timezones_should_be_processed():
                    adjust_datetimes(form_data)
                xmlns = form_data.get("@xmlns", "")
                user_id = extract_meta_user_id(form_data)
            else:
                xmlns = couch_form.xmlns
                user_id = couch_form.user_id
            if xmlns == SYSTEM_ACTION_XMLNS:
                for form_id, case_ids in do_system_action(couch_form):
                    self.case_diff_queue.update(case_ids, form_id)
            sql_form = XFormInstanceSQL(
                form_id=couch_form.form_id,
                domain=self.domain,
                xmlns=xmlns,
                user_id=user_id,
            )
            _copy_form_properties(sql_form, couch_form)
            _migrate_form_attachments(sql_form, couch_form)
            _migrate_form_operations(sql_form, couch_form)
            case_stock_result = (self._get_case_stock_result(sql_form, couch_form)
                if form_is_processed else None)
            _save_migrated_models(sql_form, case_stock_result)
        except IntegrityError as err:
            exc_info = sys.exc_info()
            try:
                sql_form = FormAccessorSQL.get_form(couch_form.form_id)
            except XFormNotFound:
                proc = "" if form_is_processed else " unprocessed"
                log.error("Error migrating%s form %s",
                    proc, couch_form.form_id, exc_info=exc_info)
            if self.stop_on_error:
                raise err from None
        except Exception as err:
            proc = "" if form_is_processed else " unprocessed"
            log.exception("Error migrating%s form %s", proc, couch_form.form_id)
            try:
                sql_form = FormAccessorSQL.get_form(couch_form.form_id)
            except XFormNotFound:
                pass
            if self.stop_on_error:
                raise err from None
        finally:
            if couch_form.doc_type != 'SubmissionErrorLog':
                self._save_diffs(couch_form, sql_form)

    def _save_diffs(self, couch_form, sql_form):
        couch_json = couch_form.to_json()
        sql_json = {} if sql_form is None else sql_form_to_json(sql_form)
        self.statedb.save_form_diffs(couch_json, sql_json)

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
        @exit_on_error
        def copy_form(doc):
            self._migrate_unprocessed_form(doc)
            add_form(doc['doc_type'])
        pool = Pool(10)
        with self.counter("unprocessed_forms") as add_form:
            problems = self.statedb.iter_problem_forms()
            for couch_form_json in iter_docs(XFormInstance.get_db(), problems, chunksize=1000):
                assert couch_form_json['problem']
                couch_form_json['doc_type'] = 'XFormError'
                pool.spawn(copy_form, couch_form_json)

            doc_types = sorted(UNPROCESSED_DOC_TYPES)
            for couch_form_json in self._get_resumable_iterator(doc_types):
                pool.spawn(copy_form, couch_form_json)

            while not pool.join(timeout=10):
                log.info('Waiting on {} docs'.format(len(pool)))

    def _migrate_unprocessed_form(self, couch_form_json):
        log.debug('Processing doc: {}({})'.format(couch_form_json['doc_type'], couch_form_json['_id']))
        couch_form = _wrap_form(couch_form_json)
        self._migrate_form_and_associated_models(couch_form, form_is_processed=False)

    def _copy_unprocessed_cases(self):
        @exit_on_error
        def copy_case(doc):
            self._copy_unprocessed_case(doc)
            add_case()
        doc_types = ['CommCareCase-Deleted']
        pool = Pool(10)
        with self.counter("unprocessed_cases", 'CommCareCase-Deleted') as add_case:
            for doc in self._get_resumable_iterator(doc_types):
                pool.spawn(copy_case, doc)

            while not pool.join(timeout=10):
                log.info('Waiting on {} docs'.format(len(pool)))

    def _copy_unprocessed_case(self, doc):
        couch_case = CommCareCase.wrap(doc)
        log.debug('Processing doc: %(doc_type)s(%(_id)s)', doc)
        try:
            first_action = couch_case.actions[0]
        except IndexError:
            first_action = CommCareCaseAction()

        opened_on = couch_case.opened_on or first_action.date
        sql_case = CommCareCaseSQL(
            case_id=couch_case.case_id,
            domain=self.domain,
            type=couch_case.type or '',
            name=couch_case.name,
            owner_id=couch_case.owner_id or couch_case.user_id or '',
            opened_on=opened_on,
            opened_by=couch_case.opened_by or first_action.user_id,
            modified_on=couch_case.modified_on or opened_on,
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
        except CaseSaveError:
            # case re-created by form processing so just mark the case as deleted
            CaseAccessorSQL.soft_delete_cases(
                self.domain,
                [sql_case.case_id],
                sql_case.deleted_on,
                sql_case.deletion_id
            )
        finally:
            self.case_diff_queue.enqueue(couch_case.case_id)

    def _process_forms_subset(self, forms):
        if forms == "missing":
            self._process_missing_forms()
            return
        if forms == "missing-blob-present":
            for form in _iter_missing_blob_present_forms(self.statedb, self.stopper):
                log.info("migrating form %s received on %s", form.form_id, form.received_on)
                self._migrate_form(form, get_case_ids(form))
            return
        form_ids = get_ids_from_string_or_file(forms)
        orig_ids = set(form_ids)
        form_ids = list(_drop_sql_form_ids(form_ids, self.statedb))
        migrated_ids = orig_ids - set(form_ids)
        if migrated_ids:
            log.info("already migrated: %s",
                f"{len(migrated_ids)} forms" if len(migrated_ids) > 5 else migrated_ids)
        for form_id in form_ids:
            log.info("migrating form: %s", form_id)
            form = XFormInstance.get(form_id)
            self._migrate_form(form, get_case_ids(form))
        self._rediff_already_migrated_forms(migrated_ids)

    def _rediff_already_migrated_forms(self, form_ids):
        for form_id in form_ids:
            log.info("re-diffing form: %s", form_id)
            couch_form = XFormInstance.get(form_id)
            sql_form = FormAccessorSQL.get_form(form_id)
            self._save_diffs(couch_form, sql_form)

    def _process_missing_forms(self):
        """process forms missed by a previous migration"""
        migrated = 0
        with self.counter('missing_forms', 'XFormInstance.id') as add_form:
            for doc_type, doc in _iter_missing_forms(self.statedb, self.stopper):
                try:
                    form = XFormInstance.wrap(doc)
                except Exception:
                    log.exception("Error wrapping form %s", doc)
                else:
                    proc = doc_type not in UNPROCESSED_DOC_TYPES
                    self._migrate_form(form, get_case_ids(form), form_is_processed=proc)
                    self.statedb.doc_not_missing(doc_type, form.form_id)
                    add_form()
                    migrated += 1
                    if migrated % 100 == 0:
                        log.info("migrated %s previously missed forms", migrated)
        log.info("finished migrating %s previously missed forms", migrated)

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

    def _with_progress(self, doc_types, iterable, progress_name='Migrating', offset_key=None):
        doc_count = sum([
            get_doc_count_in_domain_by_type(self.domain, doc_type, XFormInstance.get_db())
            for doc_type in (d.split(".", 1)[0] for d in doc_types)
        ])
        if offset_key is None:
            offset = sum(self.counter.get(doc_type) for doc_type in doc_types)
        else:
            offset = self.counter.get(offset_key)
        self.counter.normalize_timing(doc_count)

        if self.with_progress:
            prefix = "{} ({})".format(progress_name, ', '.join(doc_types))
            return with_progress_bar(
                iterable, doc_count, prefix=prefix, oneline=False, offset=offset)
        else:
            log.info("{} {} ({})".format(progress_name, doc_count, ', '.join(doc_types)))
            return iterable

    def _get_resumable_iterator(self, doc_types, **kw):
        # resumable iteration state is associated with statedb.unique_id,
        # so it will be reset (orphaned in couch) if that changes
        migration_id = self.statedb.unique_id
        if self.statedb.is_rebuild and doc_types == ["XFormInstance"]:
            yield from iter_unmigrated_docs(
                self.domain, doc_types, migration_id, self.counter)
        docs = self._iter_docs(doc_types, migration_id)
        yield from self._with_progress(doc_types, docs, **kw)

    def _iter_docs(self, doc_types, migration_id):
        for doc_type in doc_types:
            yield from _iter_docs(
                self.domain,
                doc_type,
                resume_key="%s.%s.%s" % (self.domain, doc_type, migration_id),
                stopper=self.stopper,
            )


TIMING_BUCKETS = (0.1, 1, 5, 10, 30, 60, 60 * 5, 60 * 10, 60 * 60, 60 * 60 * 12, 60 * 60 * 24)
NORMALIZED_TIMING_BUCKETS = (0.001, 0.01, 0.1, 0.25, 0.5, 0.75, 1, 2, 3, 5, 10, 30)


@contextmanager
def migration_patches():
    with patch_case_property_validators(), patch_XFormInstance_get_xml():
        yield


@contextmanager
def patch_case_property_validators():
    def truncate_255(value):
        return value[:255]

    from corehq.form_processor.backends.sql.update_strategy import PROPERTY_TYPE_MAPPING
    original = PROPERTY_TYPE_MAPPING.copy()
    PROPERTY_TYPE_MAPPING.update(
        name=truncate_255,
        type=truncate_255,
        owner_id=truncate_255,
        external_id=truncate_255,
    )
    try:
        yield
    finally:
        PROPERTY_TYPE_MAPPING.update(original)


@contextmanager
def patch_XFormInstance_get_xml():
    @memoized
    def get_xml(self):
        try:
            return self._unsafe_get_xml()
        except MissingFormXml as err:
            try:
                data = self.to_json()
            except Exception:
                raise err
            return convert_form_to_xml(data["form"]).encode('utf-8')

    if hasattr(XFormInstance, "_unsafe_get_xml"):
        # noop when already patched
        yield
        return

    XFormInstance._unsafe_get_xml = XFormInstance.get_xml
    XFormInstance.get_xml = get_xml
    try:
        yield
    finally:
        XFormInstance.get_xml = XFormInstance._unsafe_get_xml
        del XFormInstance._unsafe_get_xml


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
    @memoized
    def get_blob_metadata(parent_id):
        metas = defaultdict(list)
        for meta in metadb.get_for_parent(parent_id):
            metas[(meta.type_code, meta.name)].append(meta)
        return metas

    def try_to_get_blob_meta(parent_id, type_code, name):
        metas = get_blob_metadata(parent_id)[(type_code, name)]
        assert all(m.domain == couch_form.domain for m in metas), metas
        if len(metas) > 1:
            # known issue: duplicate blob metadata with missing blob
            missing = [m for m in metas if not m.blob_exists()]
            if missing and len(missing) < len(metas):
                for meta in missing:
                    blobdb.delete(meta.key)
                    metas.remove(meta)
            # NOTE there is still a chance that len(metas) > 1
            # Not resolving that issue here since it is not
            # thought to be caused by this migration.
        return metas[0] if metas else None

    def get_form_xml_metadata(meta):
        try:
            couch_form._unsafe_get_xml()
            assert meta is not None, couch_form.form_id
            return meta
        except MissingFormXml:
            pass
        metas = get_blob_metadata(couch_form.form_id)[(CODES.form_xml, "form.xml")]
        if len(metas) == 1:
            couch_meta = couch_form.blobs.get("form.xml")
            if couch_meta is None:
                assert not metas[0].blob_exists(), metas
            elif metas[0].key != couch_meta.key:
                assert not blobdb.exists(couch_meta.key), couch_meta
                if metas[0].blob_exists():
                    return metas[0]
            else:
                assert metas[0].key == couch_meta.key, (metas, couch_meta)
                assert not metas[0].blob_exists(), metas
            blobdb.delete(metas[0].key)
            metas.remove(metas[0])
        else:
            assert not metas, metas  # protect against yet another duplicate
        log.warning("Rebuilding missing form XML: %s", couch_form.form_id)
        xml = convert_form_to_xml(couch_form.to_json()["form"])
        att = Attachment("form.xml", xml.encode("utf-8"), content_type="text/xml")
        return att.write(blobdb, sql_form)

    if couch_form._attachments and any(
        name not in couch_form.blobs for name in couch_form._attachments
    ):
        _migrate_couch_attachments_to_blob_db(couch_form)

    attachments = []
    blobdb = get_blob_db()
    metadb = blobdb.metadb

    xml_meta = try_to_get_blob_meta(sql_form.form_id, CODES.form_xml, "form.xml")
    attachments.append(get_form_xml_metadata(xml_meta))

    for name, blob in couch_form.blobs.items():
        if name == "form.xml":
            continue
        meta = try_to_get_blob_meta(sql_form.form_id, CODES.form_attachment, name)

        # there was a bug in a migration causing the type code for many form attachments to be set as form_xml
        # this checks the db for a meta resembling this and fixes it for postgres
        # https://github.com/dimagi/commcare-hq/blob/3788966119d1c63300279418a5bf2fc31ad37f6f/corehq/blobs/migrate.py#L371
        if not meta:
            meta = try_to_get_blob_meta(sql_form.form_id, CODES.form_xml, name)
            if meta:
                meta.type_code = CODES.form_attachment
                meta.save()

        if not meta:
            meta = metadb.new(
                domain=sql_form.domain,
                name=name,
                parent_id=sql_form.form_id,
                type_code=CODES.form_attachment,
                content_type=blob.content_type,
                content_length=blob.content_length,
                key=blob.key,
            )
            meta.save()

        attachments.append(meta)
    sql_form.attachments_list = attachments
    sql_form.form_data  # should not raise MissingFormXML


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
        for name, meta in couch_form._attachments.items():
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
    except (AttachmentNotFound, MissingFormXml):
        form.get_xml.get_cache(form)[()] = ""
        assert form.get_xml() == "", form.get_xml()
    return form.to_json()


def _migrate_case_attachments(couch_case, sql_case):
    """Copy over attachment meta """
    for name, attachment in couch_case.case_attachments.items():
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
        touched_cases = interface.get_cases_from_forms(case_db, xforms)
        case_result = CaseProcessingResult(
            domain,
            [update.case for update in touched_cases.values()],
            []  # ignore dirtiness_flags
        )
        for case in case_result.cases:
            case_db.post_process_case(case, sql_form)
            case_db.mark_changed(case)
        cases = case_result.cases

        stock_result = process_stock(xforms, case_db)
        cases = case_db.get_cases_for_saving(sql_form.received_on)
        stock_result.populate_models()

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


class Stopper:

    # Minimum age of forms processed during live migration. This
    # prevents newly submitted forms from being skipped by the
    # migration.
    MIN_AGE = timedelta(hours=1)

    _lock = Lock()

    def __init__(self, live_migrate):
        self.live_migrate = live_migrate
        self.clean_break = False

    def __enter__(self):
        locked = self._lock.acquire(blocking=False)
        assert locked, "illegal concurrent stopper"
        signal.signal(signal.SIGINT, self.on_break)

    def __exit__(self, exc_type, exc, tb):
        signal.signal(signal.SIGINT, signal.default_int_handler)
        self._lock.release()
        # the case diff queue can safely be stopped with ^C at this
        # point, although proceed with care so as not to interrupt it at
        # a point where it is saving resume state. There will be a log
        # message indicating "DO NOT BREAK" just before it saves state.

    def on_break(self, signum, frame):
        if self.clean_break:
            raise KeyboardInterrupt
        log.info("clean break... (Ctrl+C to abort)")
        self.clean_break = True

    def get_stopper(self):
        """Get `should_stop(key_date)` function or `None`

        :returns: `should_stop(key_date)` function if in "live" mode
        else `None`. The first time this is called in "live" mode the
        returned function will calculate a new stop date based on the
        current time each time it is called. Subsequent calls of this
        method will return a function that uses the final stop date
        calculated in the first iteration, so all iterations will end
        up using the same stop date. It is expected that all iterations
        are done serially; concurrent iterations are not supported.
        """
        if not self.live_migrate:
            should_stop = None
        elif hasattr(self, "stop_date"):
            def should_stop(key_date):
                return key_date > stop_date

            stop_date = self.stop_date
        else:
            def should_stop(key_date):
                self.stop_date = stop_date = datetime.utcnow() - min_age
                return key_date > stop_date

            min_age = self.MIN_AGE
        return should_stop


class MigrationPaginationEventHandler(PaginationEventHandler):

    def __init__(self, domain, stopper):
        self.domain = domain
        self.stopper = stopper
        self.should_stop = stopper.get_stopper()

    def page_start(self, *args, **kw):
        if self.stopper.clean_break:
            raise StopToResume

    def page(self, results):
        if self.should_stop is None or not results:
            return
        # this is tightly coupled to by_domain_doc_type_date/view in couch:
        # the last key element is expected to be a datetime string
        key_date = results[-1]['key'][-1]
        if key_date is None:
            return  # ...except when it isn't :(
        try:
            key_date = str_to_datetime(key_date)
        except ValueError:
            log.warn("could not get date from last element of key %r", results[-1]['key'])
            return
        if self.should_stop(key_date):
            raise StopToResume

    def stop(self):
        if self.should_stop is not None:
            # always stop to preserve resume state if we reach the end
            # of the iteration while in "live" mode
            raise StopToResume


def _iter_docs(domain, doc_type, resume_key, stopper):
    @retry_on_couch_error
    def data_function(**view_kwargs):
        view_name = 'by_domain_doc_type_date/view'
        results = list(couch_db.view(view_name, **view_kwargs))
        assert all(r['key'][0] == domain for r in results), \
            _repr_bad_results(view_name, view_kwargs, results, domain)
        return results

    if "." in doc_type:
        doc_type, row_key = doc_type.split(".")
    else:
        row_key = "doc"

    if stopper.clean_break:
        return []
    couch_db = XFormInstance.get_db()
    args_provider = NoSkipArgsProvider({
        'startkey': [domain, doc_type],
        'endkey': [domain, doc_type, {}],
        'limit': _iter_docs.chunk_size,
        'include_docs': row_key == "doc",
        'reduce': False,
    })
    rows = ResumableFunctionIterator(
        resume_key,
        data_function,
        args_provider,
        item_getter=None,
        event_handler=MigrationPaginationEventHandler(domain, stopper)
    )
    if rows.state.is_resume():
        log.info("iteration state: %r", rows.state.to_json())
    row = None
    try:
        for row in rows:
            yield row[row_key]
    finally:
        if row is not None:
            row_copy = dict(row)
            row_copy.pop("doc", None)
            log.info("last item: %r", row_copy)
        log.info("final iteration state: %r", rows.state.to_json())


_iter_docs.chunk_size = 1000


def _repr_bad_results(view, kwargs, results, domain):
    def dropdoc(row):
        if kwargs["include_docs"]:
            row = dict(row)
            row.pop("doc")
        return row

    def itr_ix(i, seen=set()):
        if i > 0 and (i - 1) not in seen:
            yield i - 1, "good"
        seen.add(i)
        yield i, "bad"

    context_rows = [
        f"{j} {status} {dropdoc(results[j])}"
        for i, result in enumerate(results)
        if result['key'][0] != domain
        for j, status in itr_ix(i)
    ]
    if len(context_rows) > 20:
        context_rows = context_rows[:20]
        context_rows.append(f"... {len(context_rows) - 20} results omitted")
    context = '\n'.join(context_rows)
    return f"bad results from {view} {kwargs}:\n{context}"


def _iter_missing_forms(statedb, stopper):
    from dimagi.utils.couch.bulk import get_docs
    from .missingdocs import MissingIds
    couch = XFormInstance.get_db()
    domain = statedb.domain
    for doc_type in MissingIds.form_types:
        missing_ids = statedb.iter_missing_doc_ids(doc_type)
        for form_ids in chunked(missing_ids, _iter_docs.chunk_size, list):
            for doc in get_docs(couch, form_ids):
                assert doc["domain"] == domain, doc
                yield doc_type, doc
            if stopper.clean_break:
                break


def _iter_missing_blob_present_forms(statedb, stopper):
    """Find missing Couch forms with XML in blob db

    Scans case diffs and missing SQL cases.
    """
    @attr.s
    class MissingCaseDiff:
        kind = "CommCareCase"
        doc_id = attr.ib()
        form_states = attr.ib()

        @property
        def old_value(self):
            return json.dumps({"forms": self.form_states})

    def iter_case_diffs():
        for kind, doc_id, diffs in statedb.iter_doc_diffs("CommCareCase"):
            yield from diffs
        for case_id in statedb.iter_missing_doc_ids("CommCareCase"):
            case = CaseAccessorCouch.get_case(case_id)
            yield MissingCaseDiff(case_id, form_states={
                form_id: diff_form_state(form_id)[0]["form_state"]
                for form_id in case.xform_ids
            })

    def get_blob_present_form_ids(diff):
        if diff.kind == "CommCareCase":
            case_id = diff.doc_id
            data = json.loads(diff.old_value)["forms"]
            form_ids = [form_id
                for form_id, status in data.items()
                if status == "missing, blob present"]
            assert form_ids, diff.old_value
        elif diff.kind == "stock state":
            case_id = diff.doc_id.split("/", 1)[0]
            data = json.loads(diff.old_value)
            assert data["form_state"] == "missing, blob present", data
            form_ids = [data["ledger"]["last_modified_form_id"]]
        return form_ids, case_id

    def iter_blob_metas(form_ids):
        metas = metadb.get_for_parents(form_ids)
        parents = set()
        for meta in metas:
            if meta.type_code == CODES.form_xml:
                yield meta, [m for m in metas if m.parent_id == meta.parent_id]
                assert meta.parent_id not in parents, metas
                parents.add(meta.parent_id)
        assert parents == set(form_ids), (form_ids, parents)

    def xml_to_form(domain, xml_meta, case_id, all_metas):
        form_id = xml_meta.parent_id
        with xml_meta.open() as fh:
            xml = fh.read()
        form_data = convert_xform_to_json(xml)
        form = FormProcessorCouch.new_xform(form_data)
        form.domain = domain
        form.received_on = get_received_on(case_id, form_id)
        for meta in all_metas:
            form.external_blobs[meta.name] = BlobMetaRef(
                key=meta.key,
                blobmeta_id=meta.id,
                content_type=meta.content_type,
                content_length=meta.content_length,
            )
        return form

    def get_received_on(case_id, form_id):
        case = CaseAccessorCouch.get_case(case_id)
        for action in case.actions:
            if action.xform_id == form_id:
                return action.server_date
        raise ValueError(f"case {case_id} has no actions for form {form_id}")

    domain = statedb.domain
    metadb = get_blob_db().metadb
    seen = set()
    for diff in iter_case_diffs():
        if not diff.old_value or "missing, blob present" not in diff.old_value:
            continue
        form_ids, case_id = get_blob_present_form_ids(diff)
        form_ids = [f for f in form_ids if f not in seen]
        if not form_ids or ("case", case_id) in seen:
            continue
        seen.update(form_ids)
        seen.add(("case", case_id))
        for xml_meta, all_metas in iter_blob_metas(form_ids):
            yield xml_to_form(domain, xml_meta, case_id, all_metas)


def _drop_sql_form_ids(couch_ids, statedb):
    from .missingdocs import MissingIds
    return MissingIds.forms(statedb, None).drop_sql_ids(couch_ids)


def get_main_forms_iteration_stop_date(statedb):
    resume_key = f"{statedb.domain}.XFormInstance.{statedb.unique_id}"
    itr = ResumableFunctionIterator(resume_key, None, None, None)
    kwargs = itr.state.kwargs
    assert kwargs, f"migration state not found: {resume_key}"
    # this is tightly coupled to by_domain_doc_type_date/view in couch:
    # the last key element is expected to be a datetime
    return kwargs["startkey"][-1]


class DocCounter:

    DD_KEY = "commcare.couchsqlmigration.processed_docs"
    DD_INTERVAL = 100
    STATE_KEY = "doc_counts"
    STATE_INTERVAL = 1000

    def __init__(self, statedb):
        self.statedb = statedb
        self.counts = defaultdict(int, self.statedb.get(self.STATE_KEY, {}))
        self.timing = TimingContext("couch_sql_migration")
        self.dd_session = 0
        self.state_session = 0

    def __enter__(self):
        self.timing.start()
        return self

    def __exit__(self, *exc_info):
        self.timing.stop()
        self._send_timings()

    @contextmanager
    def __call__(self, dd_type, doc_type=None):
        """Create counting context

        :param dd_type: datadog 'type' tag
        :param doc_type: optional doc type; doc type must be passed to
        the returned counter function if not provided here, and cannot
        be passed if it is provided here.
        :yields: counter function.
        """
        tags = [f"type:{dd_type}"]
        args = (doc_type,) if doc_type else ()
        with self.timing(dd_type):
            try:
                yield partial(self.add, tags, *args)
            finally:
                self.flush(tags)

    def add(self, tags, doc_type, count=1):
        self.counts[doc_type] += count
        self.dd_session += count
        self.state_session += count
        if self.state_session > self.STATE_INTERVAL:
            self.flush(tags)
        elif self.dd_session > self.DD_INTERVAL:
            self.flush(tags, state=False)

    def flush(self, tags, state=True):
        if state:
            counts = dict(self.counts)
            self.statedb.set(self.STATE_KEY, counts)
            log.debug("saved doc counts: %s", counts)
            self.state_session = 0
        if tags is not None:
            datadog_counter(self.DD_KEY, value=self.dd_session, tags=tags)
            self.dd_session = 0

    def get(self, doc_type):
        return self.counts.get(doc_type, 0)

    def pop(self, doc_type):
        return self.counts.pop(doc_type, 0)

    def normalize_timing(self, doc_count):
        self.timing.peek().normalize_denominator = doc_count

    def _send_timings(self):
        metric_name_template = "commcare.%s.count"
        metric_name_template_normalized = "commcare.%s.count.normalized"
        for timing in self.timing.to_list():
            datadog_counter(
                metric_name_template % timing.full_name,
                tags=['duration:%s' % bucket_value(timing.duration, TIMING_BUCKETS)])
            if getattr(timing, "normalize_denominator", 0):
                datadog_counter(
                    metric_name_template_normalized % timing.full_name,
                    tags=['duration:%s' % bucket_value(
                        timing.duration / timing.normalize_denominator,
                        NORMALIZED_TIMING_BUCKETS,
                    )]
                )


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
