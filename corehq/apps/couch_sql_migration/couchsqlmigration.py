import json
import logging
import os
import signal
import sys
from collections import defaultdict
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from functools import partial
from threading import Lock

from django.db.utils import IntegrityError

import attr
from memoized import memoized

from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.xform import CaseProcessingResult, get_case_updates
from casexml.apps.case.xml.parser import CaseNoopAction
from couchforms.models import XFormInstance, XFormOperation, all_known_formlike_doc_types
from couchforms.models import doc_types as form_doc_types
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs, retry_on_couch_error
from dimagi.utils.couch.undo import DELETED_SUFFIX

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    PROBLEM_TEMPLATE_START,
)
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.tzmigration.api import (
    force_phone_timezones_should_be_processed,
)
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, MISSING
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.mixin import BlobMetaRef
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    LedgerAccessorSQL,
    doc_type_to_state,
)
from corehq.form_processor.backends.sql.ledger import LedgerProcessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import (
    AttachmentNotFound,
    CaseNotFound,
    CaseSaveError,
    MissingFormXml,
    XFormNotFound,
)
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
from corehq.util.log import with_progress_bar
from corehq.util.pagination import (
    PaginationEventHandler,
    ResumableFunctionIterator,
    StopToResume,
)
from corehq.util.timer import TimingContext
from corehq.util.metrics import metrics_counter, metrics_histogram

from .asyncforms import AsyncFormProcessor, get_case_ids
from .casediff import MISSING_BLOB_PRESENT, diff_form_state
from .casediffqueue import CaseDiffProcess, CaseDiffPending
from .json2xml import convert_form_to_xml
from .patches import migration_patches
from .retrydb import (
    couch_form_exists,
    get_couch_case,
    get_couch_forms,
    get_sql_case,
    get_sql_form,
    get_sql_forms,
    get_sql_ledger_value,
    sql_form_exists,
)
from .statedb import init_state_db
from .staterebuilder import iter_unmigrated_docs
from .system_action import do_system_action
from .util import (
    exit_on_error,
    get_ids_from_string_or_file,
    str_to_datetime,
    worker_pool,
)
from corehq.apps.domain.utils import get_custom_domain_module

log = logging.getLogger(__name__)

CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted', ]

UNPROCESSED_DOC_TYPES = list(all_known_formlike_doc_types() - {'XFormInstance'})
_old_handler = None


def setup_logging(state_dir, slug, debug=False):
    global _old_handler
    if debug:
        assert log.level <= logging.DEBUG, log.level
        logging.root.setLevel(logging.DEBUG)
        for handler in logging.root.handlers:
            if handler.name in ["file", "console"]:
                handler.setLevel(logging.DEBUG)
    if not state_dir:
        return
    log_dir = os.path.join(state_dir, "log")
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, f"{time}-{slug}.log")
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    if _old_handler is not None:
        logging.root.removeHandler(_old_handler)
    _old_handler = handler
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
        case_diff="after",
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
        assert case_diff in {"after", "patch", "asap", "none"}, case_diff
        assert case_diff != "patch" or forms in [None, "missing"], (case_diff, forms)
        self.should_patch_diffs = case_diff == "patch"
        self.should_diff_cases = case_diff == "after"
        if case_diff == "asap":
            diff_queue = CaseDiffProcess
        else:
            diff_queue = CaseDiffPending
        self.stop_on_error = stop_on_error
        self.forms = forms
        self.case_diff_queue = diff_queue(self.statedb)

    def migrate(self):
        log.info('{live}migrating domain {domain} ({state})\n{stats}'.format(
            live=("live " if self.live_migrate else ""),
            domain=self.domain,
            state=self.statedb.unique_id,
            stats="\n".join(iter_couch_stats(self.domain)),
        ))
        patch = migration_patches()
        with self.counter, patch, self.case_diff_queue, self.stopper:
            if self.forms:
                self._process_forms_subset(self.forms)
            else:
                self._process_main_forms()
                self._copy_unprocessed_forms()
                self._copy_unprocessed_cases()
            if self.should_patch_diffs:
                self._patch_diffs()
            elif self.should_diff_cases:
                self._diff_cases()

        if self.stopper.clean_break:
            raise CleanBreak

        log.info('migrated domain {}'.format(self.domain))

    def _process_main_forms(self):
        """process main forms (including cases and ledgers)"""
        def process_form(doc):
            if not doc.get('problem'):
                pool.process_xform(doc)
            elif str(doc['problem']).startswith(PROBLEM_TEMPLATE_START):
                doc = _fix_replacement_form_problem_in_couch(doc)
                pool.process_xform(doc)
            else:
                log.debug("defer 'problem' form: %s", doc["_id"])
                self.statedb.add_problem_form(doc["_id"])

        def migrate_form(form, case_ids):
            self._migrate_form(form, case_ids, form_is_processed=True)
            add_form()

        with self.counter('main_forms', 'XFormInstance') as add_form, \
                AsyncFormProcessor(self.statedb, migrate_form) as pool:
            for doc in self._get_resumable_iterator(['XFormInstance']):
                process_form(doc)

    def _migrate_form(self, couch_form, case_ids, **kw):
        form_id = couch_form.form_id
        self._migrate_form_and_associated_models(couch_form, **kw)
        self.case_diff_queue.update(case_ids, form_id)

    def _migrate_form_and_associated_models(self, couch_form, form_is_processed=None):
        """
        Copies `couch_form` into a new sql form
        """
        set_local_domain_sql_backend_override(self.domain)
        sql_form = None
        try:
            assert couch_form.domain == self.domain, couch_form.form_id
            should_process = couch_form.doc_type == 'XFormInstance'
            if form_is_processed is None:
                form_is_processed = should_process
            else:
                assert form_is_processed == should_process, \
                    (couch_form.doc_type, couch_form.form_id, form_is_processed)
            if form_is_processed:
                form_data = couch_form.form
                with force_phone_timezones_should_be_processed():
                    adjust_datetimes(form_data)
                xmlns = form_data.get("@xmlns", "")
                user_id = extract_meta_user_id(form_data)
            else:
                xmlns = couch_form.xmlns or ""
                user_id = couch_form.user_id
            if xmlns == SYSTEM_ACTION_XMLNS:
                for form_id, case_ids in do_system_action(couch_form, self.statedb):
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
            save_migrated_models(sql_form, case_stock_result)
        except IntegrityError as err:
            exc_info = sys.exc_info()
            try:
                sql_form = get_sql_form(couch_form.form_id)
            except XFormNotFound:
                sql_form = None
                proc = "" if form_is_processed else " unprocessed"
                log.error("Error migrating%s form %s",
                    proc, couch_form.form_id, exc_info=exc_info)
            if self.stop_on_error:
                raise err from None
        except Exception as err:
            proc = "" if form_is_processed else " unprocessed"
            log.exception("Error migrating%s form %s", proc, couch_form.form_id)
            try:
                sql_form = get_sql_form(couch_form.form_id)
            except XFormNotFound:
                sql_form = None
            if self.stop_on_error:
                raise err from None
        finally:
            if couch_form.doc_type != 'SubmissionErrorLog':
                self._save_diffs(couch_form, sql_form)

    def _save_diffs(self, couch_form, sql_form):
        if sql_form is not None:
            couch_json = couch_form.to_json()
            sql_json = sql_form_to_json(sql_form)
            self.statedb.save_form_diffs(couch_json, sql_json)
        else:
            self.statedb.add_missing_docs(couch_form.doc_type, [couch_form.form_id])

    def _get_case_stock_result(self, sql_form, couch_form):
        case_stock_result = None
        if sql_form.initial_processing_complete:
            case_stock_result = get_case_and_ledger_updates(self.domain, sql_form)
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
        with self.counter("unprocessed_forms") as add_form, worker_pool() as pool:
            problems = self.statedb.iter_problem_forms()
            for couch_form_json in iter_docs(XFormInstance.get_db(), problems, chunksize=1000):
                assert couch_form_json['problem']
                couch_form_json['doc_type'] = 'XFormError'
                pool.spawn(copy_form, couch_form_json)

            doc_types = sorted(UNPROCESSED_DOC_TYPES)
            for couch_form_json in self._get_resumable_iterator(doc_types):
                pool.spawn(copy_form, couch_form_json)

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
        with self.counter("unprocessed_cases", 'CommCareCase-Deleted') as add_case, \
                worker_pool() as pool:
            for doc in self._get_resumable_iterator(doc_types):
                pool.spawn(copy_case, doc)

    def _copy_unprocessed_case(self, doc):
        set_local_domain_sql_backend_override(self.domain)
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
        try:
            _migrate_case_actions(couch_case, sql_case)
            _migrate_case_indices(couch_case, sql_case)
            _migrate_case_attachments(couch_case, sql_case)
        except Exception:
            log.exception("unprocessed case error: %s", couch_case.case_id)
            self.case_diff_queue.enqueue(couch_case.case_id)
            return
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

    def _patch_diffs(self):
        from .casedifftool import CaseDiffTool
        casediff = CaseDiffTool(self)
        if not self.forms:
            casediff.diff_cases()
            self._process_missing_forms()
        casediff.diff_cases("pending")
        casediff.patch_diffs()
        casediff.diff_cases("pending")

    def _diff_cases(self):
        from .casedifftool import CaseDiffTool
        casediff = CaseDiffTool(self)
        if not self.forms:
            casediff.diff_cases()
        if casediff.should_diff_pending():
            casediff.diff_cases("pending")

    def _process_forms_subset(self, forms):
        from .missingdocs import MissingIds
        if forms == "missing":
            self._process_missing_forms()
            return
        form_ids = get_ids_from_string_or_file(forms)
        orig_ids = set(form_ids)
        form_ids = list(MissingIds.forms(self.statedb).drop_sql_ids(form_ids))
        migrated_ids = orig_ids - set(form_ids)
        if migrated_ids:
            migrated_ids -= self._migrate_missing_cases_and_ledgers(migrated_ids)
        if migrated_ids:
            log.info("already migrated: %s",
                f"{len(migrated_ids)} forms" if len(migrated_ids) > 5 else migrated_ids)
        for form_id in form_ids:
            log.info("migrating form: %s", form_id)
            self._migrate_form_id(form_id)
        self._rediff_already_migrated_forms(migrated_ids)

    def _migrate_form_id(self, form_id, case_id=None):
        try:
            form = XFormInstance.get(form_id)
        except XFormNotFound:
            form = MissingFormLoader(self.domain).load_form(form_id, case_id)
            blob = "missing" if form is None else "present"
            log.warning("couch form missing, blob %s: %s", blob, form_id)
        except Exception:
            log.exception("Error migrating form %s", form_id)
            form = None
        if form is None:
            self.statedb.add_missing_docs("XFormInstance", [form_id])
            return
        if form.domain != self.domain:
            log.warning("skipping form %s with wrong domain", form_id)
            return
        if getattr(form, "problem", "") and not form.is_error and case_id is None:
            doc = self._transform_problem(form.to_json())
            form = XFormInstance.wrap(doc)
        proc = case_id is not None or form.doc_type not in UNPROCESSED_DOC_TYPES
        case_ids = get_case_ids(form) if proc else []
        self._migrate_form(form, case_ids, form_is_processed=proc)

    def _transform_problem(self, doc):
        if str(doc['problem']).startswith(PROBLEM_TEMPLATE_START):
            doc = _fix_replacement_form_problem_in_couch(doc)
        else:
            doc['doc_type'] = 'XFormError'
        return doc

    def _rediff_already_migrated_forms(self, form_ids):
        for form_id in form_ids:
            log.info("re-diffing form: %s", form_id)
            couch_form = XFormInstance.get(form_id)
            sql_form = get_sql_form(form_id)
            self._save_diffs(couch_form, sql_form)

    def _process_missing_forms(self):
        """process forms missed by a previous migration"""
        migrated = 0
        with self.counter('missing_forms', 'XFormInstance.id') as add_form:
            for doc_type, doc in _iter_missing_forms(self.statedb, self.stopper):
                if doc.get("problem") and doc_type == "XFormInstance":
                    doc = self._transform_problem(doc)
                try:
                    form = XFormInstance.wrap(doc)
                except Exception:
                    log.exception("Error wrapping form %s", doc)
                    continue
                if form.domain != self.domain:
                    log.warning("skipping form %s with wrong domain", form.form_id)
                    continue
                proc = form.doc_type not in UNPROCESSED_DOC_TYPES
                case_ids = get_case_ids(form) if proc else []
                self._migrate_form(form, case_ids, form_is_processed=proc)
                self.statedb.doc_not_missing(doc_type, form.form_id)
                add_form()
                migrated += 1
                if migrated % 100 == 0:
                    log.info("migrated %s previously missed forms", migrated)
        log.info("finished migrating %s previously missed forms", migrated)
        self._process_missing_case_references()

    def _process_missing_case_references(self):
        """Extract forms from case diffs and process missing elements"""
        def maybe_drop_duplicate_ledgers(jdiff, stock_id, seen=set()):
            """Drop ledger transactions from duplicate forms

            Fix up ledgers affected by duplicate forms that had their
            ledger transactions processed as normal forms. At the time
            of writing it is still unknown why those forms were
            processed that way.
            """
            if (jdiff.path != ["last_modified_form_id"]
                    or "-" in jdiff.new_value
                    or jdiff.new_value in seen):
                return False
            seen.add(jdiff.new_value)
            case_id, section_id, entry_id = stock_id.split("/")
            ledger_value = get_sql_ledger_value(case_id, section_id, entry_id)
            if ledger_value.last_modified_form_id != jdiff.new_value:
                return False
            try:
                couch_form = XFormInstance.get(jdiff.new_value)
            except XFormNotFound as err:
                try:
                    sql_form = get_sql_form(jdiff.new_value)
                    if sql_form.xmlns == "http://commcarehq.org/couch-to-sql/patch-case-diff":
                        return False
                except XFormNotFound:
                    pass
                raise err
            if couch_form.doc_type != "XFormDuplicate":
                return False
            log.info("dropping duplicate ledgers for form %s case %s",
                couch_form.form_id, case_id)
            sql_form = get_sql_form(couch_form.form_id)
            MigrationLedgerProcessor(self.domain).process_form_archived(sql_form)
            self.case_diff_queue.update([case_id], couch_form.form_id)
            return True

        def iter_form_ids(jdiff, kind):
            old_value = jdiff.old_value
            if old_value is MISSING or not old_value:
                return
            if kind == "CommCareCase":
                if isinstance(old_value, dict) and "forms" in old_value:
                    for form_id, status in old_value["forms"].items():
                        if status != MISSING_BLOB_PRESENT:
                            yield form_id
                elif jdiff.diff_type == 'set_mismatch' and jdiff.path[0] == 'xform_ids':
                    yield from old_value.split(",")
            elif (
                kind == "stock state"
                and isinstance(old_value, dict)
                and "ledger" in old_value
                and old_value.get("form_state") != MISSING_BLOB_PRESENT
                and old_value["ledger"]["last_modified_form_id"] is not None
            ):
                yield old_value["ledger"]["last_modified_form_id"]

        from .missingdocs import MissingIds
        loader = MissingFormLoader(self.domain)
        drop_sql_ids = MissingIds.forms(self.statedb).drop_sql_ids
        for diff in _iter_case_diffs(self.statedb, self.stopper):
            case_id = diff.doc_id
            json_diff = diff.json_diff
            for form in loader.iter_blob_forms(diff):
                log.info("migrating form %s received on %s from case %s",
                    form.form_id, form.received_on, case_id)
                self._migrate_form(form, get_case_ids(form), form_is_processed=True)
            if diff.kind == "stock state":
                dropped = maybe_drop_duplicate_ledgers(json_diff, case_id)
                if dropped:
                    continue
            elif (diff.kind == "CommCareCase" and list(json_diff.path) == ["*"]
                    and json_diff.old_value is MISSING
                    and json_diff.new_value == "present"):
                self._delete_sql_case_missing_in_couch(case_id, json_diff)
                continue
            form_ids = list(iter_form_ids(json_diff, diff.kind))
            if not form_ids:
                continue
            missing_ids = set(drop_sql_ids(form_ids))
            for form_id in missing_ids:
                log.info("migrating missing form %s from case %s", form_id, case_id)
                self._migrate_form_id(form_id, case_id)
            couch_ids = {f for f in form_ids if couch_form_exists(f)}
            self._migrate_missing_cases_and_ledgers(couch_ids - missing_ids, case_id)

    def _migrate_missing_cases_and_ledgers(self, form_ids, case_id=None):
        """Update cases and ledgers for forms that have already been migrated

        This operation should be idempotent for cases and ledgers that
        have previously had the given forms applied to them.

        :returns: a set of form ids that had cases or ledgers to migrate.
        """
        migrated_ids = set()
        for form_id in form_ids:
            saved = self._save_missing_cases_and_ledgers(form_id, case_id)
            if saved:
                migrated_ids.add(form_id)
        return migrated_ids

    def _save_missing_cases_and_ledgers(self, form_id, case_id):
        def did_update(case):
            new_tx, = case.get_live_tracked_models(CaseTransaction)
            if not new_tx.is_saved():
                return True
            old_tx = CaseAccessorSQL.get_transaction_by_form_id(case.case_id, form_id)
            assert old_tx, (form_id, case_id)
            return old_tx.type != new_tx.type or old_tx.revoked != new_tx.revoked

        def iter_missing_ledgers(stock_result):
            assert not stock_result.models_to_delete, (form_id, stock_result)
            if not (stock_result and stock_result.models_to_save):
                return
            get_transactions = LedgerAccessorSQL.get_ledger_transactions_for_form
            case_ids = {v.case_id for v in stock_result.models_to_save}
            refs = {t.ledger_reference for t in get_transactions(form_id, case_ids)}
            for value in stock_result.models_to_save:
                if value.ledger_reference not in refs:
                    yield value

        from django.db import transaction
        couch_form = XFormInstance.get(form_id)
        if couch_form.doc_type in UNPROCESSED_DOC_TYPES:
            if case_id is not None:
                log.warning("unprocessed form %s referenced by case %s", form_id, case_id)
            return False
        sql_form = get_sql_form(form_id)
        result = self._apply_form_to_case(sql_form, couch_form)
        if not result:
            return False
        cases = [c for c in result.case_models if did_update(c)]
        rebuild_ledger = partial(
            MigrationLedgerProcessor(self.domain)._rebuild_ledger, form_id)
        ledgers = [rebuild_ledger(v) for v in iter_missing_ledgers(result.stock_result)]
        if not (cases or ledgers):
            return False
        case_ids = {c.case_id for c in cases} | {v.case_id for v in ledgers}
        self.case_diff_queue.update(case_ids, form_id)
        saved = False
        with ExitStack() as stack:
            for db_name in {c.db for c in cases} | {v.db for v in ledgers}:
                stack.enter_context(transaction.atomic(db_name))
            for case in cases:
                log.info("migrating case %s for form %s", case.case_id, form_id)
                try:
                    CaseAccessorSQL.save_case(case)
                    saved = True
                except Exception:
                    log.warn("error saving case %s", case.case_id, exc_info=True)
            if ledgers:
                log.info("migrating %s ledgers for form %s", len(ledgers), form_id)
                LedgerAccessorSQL.save_ledger_values(ledgers, result.stock_result)
                saved = True
        return saved

    def _apply_form_to_case(self, sql_form, couch_form):
        if (sql_form.is_error and couch_form.doc_type == "XFormInstance"
                and getattr(couch_form, "problem", "")):
            # Note: does not clear "problem" field
            sql_form.state = XFormInstanceSQL.NORMAL
            sql_form.save()
        elif (sql_form.is_normal and couch_form.doc_type == "XFormInstance"
                and not couch_form.initial_processing_complete
                and not sql_form.initial_processing_complete):
            # Note: creates an un-recorded form diff. This is an
            # internal flag and there are cases that reference the form,
            # implying that the form was processed, and therefore the
            # 'initial_processing_complete' state in Couch is wrong.
            sql_form.initial_processing_complete = True
            sql_form.save()
        result = self._get_case_stock_result(sql_form, couch_form)
        if sql_form.is_normal and sql_form.initial_processing_complete:
            for case in result.case_models:
                for tx in case.get_live_tracked_models(CaseTransaction):
                    assert tx.form_id == sql_form.form_id, (sql_form.form_id, tx)
                    if tx.revoked:
                        tx.revoked = False
        return result

    def _delete_sql_case_missing_in_couch(self, case_id, json_diff):
        assert (list(json_diff.path) == ["*"]
                and json_diff.old_value is MISSING
                and json_diff.new_value == "present"), (case_id, json_diff)
        try:
            sql_case = get_sql_case(case_id)
        except CaseNotFound:
            return  # already deleted
        assert sql_case.xform_ids, case_id
        sql_forms = {f.form_id: f for f in get_sql_forms(sql_case.xform_ids)}
        form_pairs = []
        normal_forms = []
        for couch_form in get_couch_forms(sql_case.xform_ids):
            if (couch_form.initial_processing_complete
                    and not getattr(couch_form, "problem", None)
                    and couch_form.doc_type == "XFormInstance"):
                normal_forms.append(couch_form.form_id)
                continue
            try:
                sql_form = sql_forms[couch_form.form_id]
            except KeyError:
                log.error("case %s: form not in SQL %s", case_id, couch_form.form_id)
                return
            form_pairs.append((couch_form, sql_form))
        all_case_ids = set()
        for couch_form, sql_form in form_pairs:
            changed = False
            if not couch_form.initial_processing_complete:
                sql_form.initial_processing_complete = False
                changed = True
            couch_problem = getattr(couch_form, "problem", None)
            if couch_problem and sql_form.problem != couch_problem:
                sql_form.problem = couch_form.problem
                changed = True
            if sql_form.is_normal:
                sql_form.state = XFormInstanceSQL.ERROR
                changed = True
            if not changed:
                continue
            sql_form.save()
            case_ids = get_case_ids(sql_form)
            self.case_diff_queue.update(case_ids, couch_form.form_id)
            all_case_ids.update(case_ids)
        if normal_forms:
            log.info("soft-deleting case %s with normal or missing forms %s",
                case_id, normal_forms)
            CaseAccessorSQL.soft_delete_cases(self.domain, [case_id])
        elif case_id in all_case_ids:
            log.info("deleting SQL case missing in Couch: %s forms=%s",
                case_id, sql_case.xform_ids)
            CaseAccessorSQL.hard_delete_cases(self.domain, [case_id])
        else:
            log.warning("refusing to delete case %s: form not found?", case_id)

    def _check_for_migration_restrictions(self, domain_name):
        msgs = []
        if not should_use_sql_backend(domain_name):
            msgs.append("does not have SQL backend enabled")
        if COUCH_SQL_MIGRATION_BLACKLIST.enabled(domain_name, NAMESPACE_DOMAIN):
            msgs.append("is blacklisted")
        if get_custom_domain_module(domain_name):
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


class MigrationLedgerProcessor(LedgerProcessorSQL):

    @staticmethod
    def _rebuild_ledger_value_from_transactions(ledger_value, transactions, domain):
        ledger_value = LedgerProcessorSQL._rebuild_ledger_value_from_transactions(
            ledger_value, transactions, domain)
        tx = max(transactions, key=lambda tx: tx.server_date)
        ledger_value.last_modified = tx.server_date
        ledger_value.last_modified_form_id = tx.form_id
        return ledger_value


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
        assert all(m.domain == sql_form.domain for m in metas), \
            (parent_id, [m.domain for m in metas])
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
        except MissingFormXml:
            pass
        else:
            if meta is None:
                blob = couch_form.blobs["form.xml"]
                assert blob.blobmeta_id is None, couch_form.form_id
                meta = new_meta_for_blob(blob, CODES.form_xml, "form.xml")
            return meta
        metas = get_blob_metadata(couch_form.form_id)[(CODES.form_xml, "form.xml")]
        if len(metas) == 1:
            couch_meta = couch_form.blobs.get("form.xml")
            if couch_meta is None:
                if metas[0].blob_exists():
                    # not sure how this is possible, but at least one
                    # form existed that hit this branch.
                    return metas[0]
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

    def new_meta_for_blob(blob, type_code, name):
        meta = metadb.new(
            domain=sql_form.domain,
            name=name,
            parent_id=sql_form.form_id,
            type_code=type_code,
            content_type=blob.content_type,
            content_length=blob.content_length,
            key=blob.key,
        )
        meta.save()
        return meta

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
            meta = new_meta_for_blob(blob, CODES.form_attachment, name)

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


def _fix_replacement_form_problem_in_couch(doc):
    """Fix replacement form created by swap_duplicate_xforms

    The replacement form was incorrectly created with "problem" text,
    which causes it to be counted as an error form, and that messes up
    the diff counts at the end of this migration.

    NOTE the replacement form's _id does not match instanceID in its
    form.xml. That issue is not resolved here.

    See:
    - corehq/apps/cleanup/management/commands/swap_duplicate_xforms.py
    - couchforms/_design/views/all_submissions_by_domain/map.js
    """
    problem = doc["problem"]
    assert problem.startswith(PROBLEM_TEMPLATE_START), doc
    assert doc["doc_type"] == "XFormInstance", doc
    deprecated_id = problem[len(PROBLEM_TEMPLATE_START):].split(" on ", 1)[0]
    form = XFormInstance.wrap(doc)
    form.deprecated_form_id = deprecated_id
    form.history.append(XFormOperation(
        user="system",
        date=datetime.utcnow(),
        operation="Resolved bad duplicate form during couch-to-sql "
        "migration. Original problem: %s" % problem,
    ))
    form.problem = None
    old_form = XFormInstance.get(deprecated_id)
    if old_form.initial_processing_complete and not form.initial_processing_complete:
        form.initial_processing_complete = True
    form.save()
    return form.to_json()


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
            content_length=blob.content_length,
            blob_id=blob.key,
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


def get_case_and_ledger_updates(domain, sql_form):
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


def save_migrated_models(sql_form, case_stock_result):
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
        event_handler=MigrationPaginationEventHandler(domain, stopper)
    )
    if rows.state.is_resume() and rows.state.to_json().get("kwargs"):
        log.debug("iteration state: %r", rows.state.to_json()["kwargs"])
    row = None
    log_message = log.debug
    try:
        for row in rows:
            yield row[row_key]
    except:  # noqa E772
        log_message = logging.info
        raise
    finally:
        final_state = rows.state.to_json().get("kwargs")
        if final_state:
            if stopper.clean_break:
                log_message = logging.info
            log_message("final iteration state: %r", final_state)


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


def _iter_case_diffs(statedb, stopper):
    """Generate case diffs from state db

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

        @property
        def json_diff(self):
            old_value = {"forms": self.form_states}
            return FormJsonDiff("diff", ["?"], old_value, MISSING)

    for kind, doc_id, diffs in statedb.iter_doc_diffs("CommCareCase"):
        yield from diffs
        if stopper.clean_break:
            return
    for case_id in statedb.iter_missing_doc_ids("CommCareCase"):
        yield MissingCaseDiff(case_id, form_states={
            form_id: diff_form_state(form_id)[0]["form_state"]
            for form_id in get_couch_case(case_id).xform_ids
        })
        if stopper.clean_break:
            return


@attr.s
class MissingFormLoader:
    """Reconstruct missing Couch forms with XML from blob db"""

    domain = attr.ib()
    seen = attr.ib(factory=set, init=False)

    def iter_blob_forms(self, diff):
        """Yield forms from blob XML that are missing in Couch and SQL

        The "missing in Couch, blob present" condition is encoded in
        the diff record, and therefore is not checked directly here.
        """
        if not diff.old_value or MISSING_BLOB_PRESENT not in diff.old_value:
            return
        form_ids, case_id = self.get_blob_present_form_ids(diff)
        form_ids = [f for f in form_ids if f not in self.seen]
        if form_ids:
            self.seen.update(form_ids)
            for xml_meta, all_metas in self.iter_blob_metas(form_ids):
                yield self.xml_to_form(xml_meta, case_id, all_metas)

    def load_form(self, form_id, case_id=None):
        """Load a form from blob XML that is missing in Couch and SQL"""
        metas = next(self.iter_blob_metas([form_id], maybe_missing=True), None)
        if metas is None:
            return None
        self.seen.add(form_id)
        xml_meta, all_metas = metas
        return self.xml_to_form(xml_meta, case_id, all_metas)

    def get_blob_present_form_ids(self, diff):
        if diff.kind == "CommCareCase":
            case_id = diff.doc_id
            data = json.loads(diff.old_value)["forms"]
            form_ids = [form_id
                for form_id, status in data.items()
                if status == MISSING_BLOB_PRESENT]
            assert form_ids, diff.old_value
        elif diff.kind == "stock state":
            case_id = diff.doc_id.split("/", 1)[0]
            data = json.loads(diff.old_value)
            assert data["form_state"] == MISSING_BLOB_PRESENT, data
            form_ids = [data["ledger"]["last_modified_form_id"]]
        else:
            raise ValueError(f"unknown diff kind: {diff.kind}")
        return form_ids, case_id

    def iter_blob_metas(self, form_ids, maybe_missing=False):
        form_ids = [f for f in form_ids if not sql_form_exists(f)]
        if not form_ids:
            return
        metas = get_blob_db().metadb.get_for_parents(form_ids)
        parents = set()
        for meta in metas:
            if meta.type_code == CODES.form_xml:
                yield meta, [m for m in metas if m.parent_id == meta.parent_id]
                assert meta.parent_id not in parents, \
                    f"found two XML blobs for form {meta.parent_id}"
                parents.add(meta.parent_id)
        assert maybe_missing or set(form_ids) == parents, \
            f"unexpected missing XML for forms: {set(form_ids) - parents}"

    def xml_to_form(self, xml_meta, case_id, all_metas):
        form_id = xml_meta.parent_id
        with xml_meta.open() as fh:
            xml = fh.read()
        form_data = convert_xform_to_json(xml)
        form = FormProcessorCouch.new_xform(form_data)
        form.domain = self.domain
        form.received_on = self.get_received_on(case_id, form_id, xml_meta)
        for meta in all_metas:
            form.external_blobs[meta.name] = BlobMetaRef(
                key=meta.key,
                blobmeta_id=meta.id,
                content_type=meta.content_type,
                content_length=meta.content_length,
            )
        return form

    def get_received_on(self, case_id, form_id, xml_meta):
        if case_id is None:
            return xml_meta.created_on
        case = get_couch_case(case_id)
        for action in case.actions:
            if action.xform_id == form_id:
                return action.server_date
        raise ValueError(f"case {case_id} has no actions for form {form_id}")


def get_main_forms_iteration_stop_date(statedb):
    resume_key = f"{statedb.domain}.XFormInstance.{statedb.unique_id}"
    itr = ResumableFunctionIterator(resume_key, None, None)
    if getattr(itr.state, "complete", False):
        return None
    kwargs = itr.state.kwargs
    assert kwargs, f"migration state not found: {resume_key}"
    if len(kwargs["startkey"]) != 3:
        return None
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
        tags = {"type": dd_type}
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
            metrics_counter(self.DD_KEY, value=self.dd_session, tags=tags)
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
            metrics_histogram(
                metric_name_template % timing.full_name, timing.duration,
                buckets=TIMING_BUCKETS, bucket_tag='duration'
            )
            if getattr(timing, "normalize_denominator", 0):
                normalized_value = timing.duration / timing.normalize_denominator
                metrics_histogram(
                    metric_name_template_normalized % timing.full_name, normalized_value,
                    buckets=NORMALIZED_TIMING_BUCKETS, bucket_tag='duration'
                )


def iter_couch_stats(domain_name):
    from .missingdocs import MissingIds
    from couchforms.analytics import get_last_form_submission_received
    couchdb = XFormInstance.get_db()
    for entity in MissingIds.DOC_TYPES:
        count = get_couch_doc_count(domain_name, entity, couchdb)
        yield f"Total {entity}s: {count}"
    received_on = get_last_form_submission_received(domain_name)
    yield f"Last form submission: {received_on}"


def get_couch_doc_count(domain_name, entity, couchdb):
    from .missingdocs import MissingIds
    return sum(
        get_doc_count_in_domain_by_type(domain_name, doc_type, couchdb)
        for doc_type in MissingIds.DOC_TYPES[entity]
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
    metrics_counter("commcare.couch_sql_migration.total_committed")
    log.info("committed migration for {}".format(domain_name))


class MigrationRestricted(Exception):
    pass


class CleanBreak(Exception):
    pass
