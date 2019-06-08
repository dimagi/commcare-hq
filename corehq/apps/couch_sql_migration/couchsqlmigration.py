from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import sys
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime, timedelta
from time import time

import gevent
import six
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.xform import (
    CaseProcessingResult,
    get_all_extensions_to_close,
    get_case_ids_from_form,
    get_case_updates,
)
from casexml.apps.case.xml.parser import CaseNoopAction
from django.conf import settings
from django.db.utils import IntegrityError
from django_redis import get_redis_connection
from gevent.pool import Pool

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    PROBLEM_TEMPLATE_START,
)
from corehq.apps.couch_sql_migration.diff import (
    filter_case_diffs,
    filter_form_diffs,
    filter_ledger_diffs,
)
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.tzmigration.api import force_phone_timezones_should_be_processed
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
from corehq.form_processor.backends.couch.dbaccessors import FormAccessorCouch
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    LedgerAccessorSQL,
    doc_type_to_state,
)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
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
from corehq.form_processor.submission_post import CaseStockProcessingResult
from corehq.form_processor.utils import adjust_datetimes, should_use_sql_backend
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
from couchforms.models import XFormOperation, doc_types as form_doc_types
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX
from pillowtop.reindexer.change_providers.couch import CouchDomainDocTypeChangeProvider

log = logging.getLogger(__name__)

CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted', ]

UNPROCESSED_DOC_TYPES = list(all_known_formlike_doc_types() - {'XFormInstance'})


def setup_logging(log_dir):
    if not log_dir:
        return
    time = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    log_file = os.path.join(log_dir, "couch2sql-form-case-{}.log".format(time))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logging.root.addHandler(handler)
    log.info("command: %s", " ".join(sys.argv))


def do_couch_to_sql_migration(domain, with_progress=True, debug=False, run_timestamp=None):
    set_local_domain_sql_backend_override(domain)
    CouchSqlDomainMigrator(
        domain,
        with_progress=with_progress,
        debug=debug,
        run_timestamp=run_timestamp
    ).migrate()


class CouchSqlDomainMigrator(object):
    def __init__(self, domain, with_progress=True, debug=False, run_timestamp=None):
        from corehq.apps.tzmigration.planning import DiffDB
        self._check_for_migration_restrictions(domain)
        self.with_progress = with_progress
        self.debug = debug
        self.domain = domain
        self.run_timestamp = run_timestamp or int(time())
        db_filepath = get_diff_db_filepath(domain)
        self.diff_db = DiffDB.init(db_filepath)
        if debug:
            assert log.level <= logging.DEBUG, log.level
            logging.root.setLevel(logging.DEBUG)
            for handler in logging.root.handlers:
                if handler.name in ["file", "console"]:
                    handler.setLevel(logging.DEBUG)

        self.errors_with_normal_doc_type = []
        self.forms_that_touch_cases_without_actions = set()

    def migrate(self):
        log.info('migrating domain {}'.format(self.domain))
        log.info('run timestamp is {}'.format(self.run_timestamp))

        self.processed_docs = 0
        with TimingContext("couch_sql_migration") as timing_context:
            self.timing_context = timing_context
            with timing_context('main_forms'):
                self._process_main_forms()
            with timing_context("unprocessed_forms"):
                self._copy_unprocessed_forms()
            with timing_context("unprocessed_cases"):
                self._copy_unprocessed_cases()
            with timing_context("case_diffs"):
                self._calculate_case_diffs()

        self._send_timings(timing_context)
        log.info('migrated domain {}'.format(self.domain))

    def _process_main_forms(self):
        last_received_on = datetime.min
        # form_id needs to be on self to release appropriately
        self.queues = PartiallyLockingQueue("form_id", max_size=10000, run_timestamp=self.run_timestamp)
        pool = Pool(15)
        self._rebuild_queues(pool)

        # process main forms (including cases and ledgers)
        changes = self._get_resumable_iterator(['XFormInstance'], 'main_forms')

        # form_id needs to be on self to release appropriately
        self.queues = PartiallyLockingQueue("form_id", max_size=10000)

        for change in self._with_progress(['XFormInstance'], changes):
            log.debug('Processing doc: {}({})'.format('XFormInstance', change.id))
            form = change.get_document()
            if form.get('problem'):
                if six.text_type(form['problem']).startswith(PROBLEM_TEMPLATE_START):
                    form = _fix_replacement_form_problem_in_couch(form)
                else:
                    self.errors_with_normal_doc_type.append(change.id)
                    continue
            try:
                wrapped_form = XFormInstance.wrap(form)
                form_received = wrapped_form.received_on
                assert last_received_on <= form_received
                last_received_on = form_received
                self._try_to_process_form(wrapped_form, pool)
                self._try_to_process_queues(pool)
            except Exception:
                log.exception("Error migrating form %s", change.id)

        # finish up the queues once all changes have been iterated through
        update_interval = timedelta(seconds=10)
        next_check = datetime.now()
        while self.queues.has_next():
            wrapped_form = self.queues.get_next()
            if wrapped_form:
                pool.spawn(self._migrate_form_and_associated_models_async, wrapped_form)
            else:
                gevent.sleep()  # swap greenlets

            remaining_items = self.queues.remaining_items + len(pool)
            now = datetime.now()
            if now > next_check:
                log.info('Waiting on {} docs'.format(remaining_items))
                next_check += update_interval

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        self._log_main_forms_processed_count()

    def _try_to_process_form(self, wrapped_form, pool):
        case_ids = get_case_ids_from_form(wrapped_form)
        if self.queues.try_obj(case_ids, wrapped_form):
            pool.spawn(self._migrate_form_and_associated_models_async, wrapped_form)
        elif self.queues.full:
            gevent.sleep()  # swap greenlets

    def _try_to_process_queues(self, pool):
        # regularly check if we can empty the queues
        while True:
            new_wrapped_form = self.queues.get_next()
            if not new_wrapped_form:
                break
            pool.spawn(self._migrate_form_and_associated_models_async, new_wrapped_form)

    def _rebuild_queues(self, pool):
        prev_ids = self.queues.get_ids_from_run_timestamp()

        for chunked_ids in chunked(prev_ids, 100):
            chunk = list([_id for _id in chunked_ids if _id])
            for form in FormAccessorCouch.get_forms(chunk):
                self._try_to_process_form(form, pool)

        self._try_to_process_queues(pool)

    def _migrate_form_and_associated_models_async(self, wrapped_form):
        set_local_domain_sql_backend_override(self.domain)
        try:
            self._migrate_form_and_associated_models(wrapped_form)
        except Exception:
            log.exception("Unable to migrate form: %s", wrapped_form.form_id)
        finally:
            self.queues.release_lock_for_queue_obj(wrapped_form)
            self.processed_docs += 1
            self._log_main_forms_processed_count(throttled=True)

    def _migrate_form_and_associated_models(self, couch_form, form_is_processed=True):
        """
        Copies `couch_form` into a new sql form
        """
        if form_is_processed:
            with force_phone_timezones_should_be_processed():
                adjust_datetimes(couch_form.form)

        sql_form = XFormInstanceSQL(
            form_id=couch_form.form_id,
            xmlns=couch_form.xmlns,
            user_id=couch_form.user_id,
        )
        _copy_form_properties(self.domain, sql_form, couch_form)
        _migrate_form_attachments(sql_form, couch_form)
        _migrate_form_operations(sql_form, couch_form)
        if couch_form.doc_type != 'SubmissionErrorLog':
            self._save_diffs(couch_form, sql_form)

        case_stock_result = None
        if form_is_processed and sql_form.initial_processing_complete:
            case_stock_result = _get_case_and_ledger_updates(self.domain, sql_form)
            if len(case_stock_result.case_models):
                touch_updates = [
                    update for update in get_case_updates(couch_form)
                    if len(update.actions) == 1 and isinstance(update.actions[0], CaseNoopAction)
                ]
                if len(touch_updates):
                    # record these for later use when filtering case diffs. See ``_filter_forms_touch_case``
                    self.forms_that_touch_cases_without_actions.add(couch_form.form_id)

        _save_migrated_models(sql_form, case_stock_result)

    def _save_diffs(self, couch_form, sql_form):
        from corehq.apps.tzmigration.timezonemigration import json_diff
        couch_form_json = couch_form.to_json()
        sql_form_json = sql_form.to_json()
        diffs = json_diff(couch_form_json, sql_form_json, track_list_indices=False)
        self.diff_db.add_diffs(
            couch_form.doc_type, couch_form.form_id,
            filter_form_diffs(couch_form_json, sql_form_json, diffs)
        )

    def _copy_unprocessed_forms(self):
        pool = Pool(10)
        for couch_form_json in iter_docs(XFormInstance.get_db(), self.errors_with_normal_doc_type, chunksize=1000):
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
        couch_case = CommCareCase.wrap(change.get_document())
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

        self.processed_docs += 1
        self._log_unprocessed_cases_processed_count(throttled=True)

    def _calculate_case_diffs(self):
        cases = {}
        batch_size = 100
        pool = Pool(10)
        changes = self._get_resumable_iterator(CASE_DOC_TYPES, 'case_diffs')
        for change in self._with_progress(CASE_DOC_TYPES, changes, progress_name='Calculating diffs'):
            cases[change.id] = change.get_document()
            if len(cases) == batch_size:
                pool.spawn(self._diff_cases, deepcopy(cases))
                cases = {}

        if cases:
            pool.spawn(self._diff_cases, cases)

        while not pool.join(timeout=10):
            log.info("Waiting on at most {} more docs".format(len(pool) * batch_size))

        self._log_case_diff_count()

    def _diff_cases(self, couch_cases):
        from corehq.apps.tzmigration.timezonemigration import json_diff
        log.debug('Calculating case diffs for {} cases'.format(len(couch_cases)))
        diff_db = self.diff_db
        counts = defaultdict(int)
        case_ids = list(couch_cases)
        sql_cases = CaseAccessorSQL.get_cases(case_ids)
        sql_case_ids = set()
        for sql_case in sql_cases:
            sql_case_ids.add(sql_case.case_id)
            couch_case = couch_cases[sql_case.case_id]
            sql_case_json = sql_case.to_json()
            diffs = json_diff(couch_case, sql_case_json, track_list_indices=False)
            diffs = filter_case_diffs(
                couch_case, sql_case_json, diffs, self.forms_that_touch_cases_without_actions
            )
            if diffs and not sql_case.is_deleted:
                try:
                    couch_case, diffs = self._rebuild_couch_case_and_re_diff(
                        couch_case, sql_case_json)
                except Exception as err:
                    log.warning('Case {} rebuild -> {}: {}'.format(
                        sql_case.case_id, type(err).__name__, err))
            if diffs:
                diff_db.add_diffs(couch_case['doc_type'], sql_case.case_id, diffs)
            counts[couch_case['doc_type']] += 1

        self._diff_ledgers(case_ids)

        if len(case_ids) != len(sql_case_ids):
            couch_ids = set(case_ids)
            assert not (sql_case_ids - couch_ids), sql_case_ids - couch_ids
            missing_cases = [couch_cases[x] for x in couch_ids - sql_case_ids]
            log.debug("Found %s missing SQL cases", len(missing_cases))
            for doc_type, doc_ids in self._filter_missing_cases(missing_cases):
                diff_db.add_missing_docs(doc_type, doc_ids)
                counts[doc_type] += len(doc_ids)

        for doc_type, count in six.iteritems(counts):
            diff_db.increment_counter(doc_type, count)
        self.processed_docs += len(case_ids)
        self._log_case_diff_count(throttled=True)

    def _rebuild_couch_case_and_re_diff(self, couch_case, sql_case_json):
        from corehq.form_processor.backends.couch.processor import FormProcessorCouch
        from corehq.apps.tzmigration.timezonemigration import json_diff

        rebuilt_case = FormProcessorCouch.hard_rebuild_case(
            self.domain, couch_case['_id'], None, save=False, lock=False
        )
        rebuilt_case_json = rebuilt_case.to_json()
        diffs = json_diff(rebuilt_case_json, sql_case_json, track_list_indices=False)
        diffs = filter_case_diffs(
            rebuilt_case_json, sql_case_json, diffs, self.forms_that_touch_cases_without_actions
        )
        return rebuilt_case_json, diffs

    def _diff_ledgers(self, case_ids):
        from corehq.apps.tzmigration.timezonemigration import json_diff
        from corehq.apps.commtrack.models import StockState
        couch_state_map = {
            state.ledger_reference: state
            for state in StockState.objects.filter(case_id__in=case_ids)
        }

        log.debug('Calculating ledger diffs for {} cases'.format(len(case_ids)))

        for ledger_value in LedgerAccessorSQL.get_ledger_values_for_cases(case_ids):
            couch_state = couch_state_map.get(ledger_value.ledger_reference, None)
            diffs = json_diff(couch_state.to_json(), ledger_value.to_json(), track_list_indices=False)
            self.diff_db.add_diffs(
                'stock state', ledger_value.ledger_reference.as_id(),
                filter_ledger_diffs(diffs)
            )

    def _filter_missing_cases(self, missing_cases):
        result = defaultdict(list)
        for couch_case in missing_cases:
            if self._is_orphaned_case(couch_case):
                log.info("Ignoring orphaned case: %s", couch_case["_id"])
            else:
                result[couch_case["doc_type"]].append(couch_case["_id"])
        return six.iteritems(result)

    def _is_orphaned_case(self, couch_case):
        def references_case(form_id):
            form = FormAccessorCouch.get_form(form_id)
            return case_id in get_case_ids_from_form(form)

        case_id = couch_case["_id"]
        return not any(references_case(x) for x in couch_case["xform_ids"])

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

    def _log_case_diff_count(self, throttled=False):
        self._log_processed_docs_count(['type:case_diffs'], throttled)

    def _get_resumable_iterator(self, doc_types, slug):
        key = "%s.%s.%s" % (self.domain, slug, self.run_timestamp)
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


def get_diff_db_filepath(domain):
    return os.path.join(settings.SHARED_DRIVE_CONF.tzmigration_planning_dir,
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


class PartiallyLockingQueue(object):
    """ Data structure that holds a queue of objects returning them as locks become free

    This is not currently thread safe

    Interface:
    `.try_obj(lock_ids, queue_obj)` use to add a new object, seeing if it can be
        processed immediately
    `.get_next()` use to get the next object off the queue that can be processed
    `.has_next()` use to make sure there are still objects in the queue
    `.release_lock_for_queue_obj(queue_obj)` use to release the locks associated
        with an object once finished processing
    """

    def __init__(self, queue_id_param="id", max_size=-1, run_timestamp=None):
        """
        :queue_id_param string: param of the queued objects to pull an id from
        :max_size int: the maximum size the queue should reach. -1 means no limit
        """
        self.queue_by_lock_id = defaultdict(deque)
        self.lock_ids_by_queue_id = defaultdict(list)
        self.queue_objs_by_queue_id = dict()
        self.currently_locked = set()
        self.max_size = max_size

        def get_queue_obj_id(queue_obj):
            return getattr(queue_obj, queue_id_param)
        self.get_queue_obj_id = get_queue_obj_id

        def get_cached_list_key():
            return "partial_queues.queued_or_processing.%s" % run_timestamp
        self.get_cached_list_key = get_cached_list_key
        client = get_redis_connection()
        client.rpush(get_cached_list_key(), '')  # hack to make key exist
        client.expire(get_cached_list_key(), 60 * 60 * 24 * 30)  # 30 days

    def add_processing_doc_id(self, doc_id):
        client = get_redis_connection()
        client.rpush(self.get_cached_list_key(), doc_id)

    def remove_processing_doc_id(self, doc_id):
        client = get_redis_connection()
        gevent.spawn(client.lrem, self.get_cached_list_key(), 1, doc_id)

    def get_ids_from_run_timestamp(self):
        client = get_redis_connection()
        return client.lrange(self.get_cached_list_key(), 0, -1) or []

    def try_obj(self, lock_ids, queue_obj):
        """ Checks if the object can acquire some locks. If not, adds item to queue

        :lock_ids list<string>: list of ids that this object needs to wait on
        :queue_obj object: whatever kind of object is being queued

        First checks the current locks, then makes sure this object would be the first in each
        queue it would sit in

        Returns :boolean: True if it acquired the lock, False if it was added to queue
        """
        if not lock_ids:
            self._add_item(lock_ids, queue_obj, to_queue=False)
            return True
        if self._check_lock(lock_ids):  # if it's currently locked, it can't acquire the lock
            self._add_item(lock_ids, queue_obj)
            return False
        for lock_id in lock_ids:  # if other objs are waiting for the same locks, it has to wait
            queue = self.queue_by_lock_id[lock_id]
            if queue:
                self._add_item(lock_ids, queue_obj)
                return False
        self._add_item(lock_ids, queue_obj, to_queue=False)
        self._set_lock(lock_ids)
        return True

    def get_next(self):
        """ Returns the next object that can be processed

        Iterates through the first object in each queue, then checks that that object is the
        first in every lock queue it is in

        Returns :obj: of whatever is being queued or None if nothing can acquire the lock currently
        """
        for lock_id, queue in six.iteritems(self.queue_by_lock_id):
            if not queue:
                continue
            peeked_obj_id = queue[0]

            lock_ids = self.lock_ids_by_queue_id[peeked_obj_id]
            first_in_all_queues = True
            for lock_id in lock_ids:
                first_in_queue = self.queue_by_lock_id[lock_id][0]  # can assume there always will be one
                if not first_in_queue == peeked_obj_id:
                    first_in_all_queues = False
                    break
            if not first_in_all_queues:
                continue

            if self._set_lock(lock_ids):
                return self._remove_item(peeked_obj_id)
        return None

    def has_next(self):
        """ Makes sure there are still objects in the queue

        Returns :boolean: True if there are objs left, False if not
        """
        for _, queue in six.iteritems(self.queue_by_lock_id):
            if queue:
                return True
        return False

    def release_lock_for_queue_obj(self, queue_obj):
        """ Releases all locks for an object in the queue

        :queue_obj obj: An object of the type in the queues

        At some point in the future it might raise an exception if it trys
        releasing a lock that isn't held
        """
        queue_obj_id = self.get_queue_obj_id(queue_obj)
        lock_ids = self.lock_ids_by_queue_id.get(queue_obj_id)
        self.remove_processing_doc_id(queue_obj_id)
        if lock_ids:
            self._release_lock(lock_ids)
            del self.lock_ids_by_queue_id[queue_obj_id]
            return True
        return False

    @property
    def remaining_items(self):
        return len(self.queue_objs_by_queue_id)

    @property
    def full(self):
        if self.max_size == -1:
            return False
        return self.remaining_items >= self.max_size

    def _add_item(self, lock_ids, queue_obj, to_queue=True):
        """
        :to_queue boolean: adds object to queues if True, just to lock tracking if not
        """
        queue_obj_id = self.get_queue_obj_id(queue_obj)
        if to_queue:
            for lock_id in lock_ids:
                self.queue_by_lock_id[lock_id].append(queue_obj_id)
            self.queue_objs_by_queue_id[queue_obj_id] = queue_obj
        self.lock_ids_by_queue_id[queue_obj_id] = lock_ids
        self.add_processing_doc_id(queue_obj_id)

    def _remove_item(self, queued_obj_id):
        """ Removes a queued obj from data model

        :queue_obj_id string: An id of an object of the type in the queues

        Assumes the obj is the first in every queue it inhabits. This seems reasonable
        for the intended use case, as this function should only be used by `.get_next`.

        Raises UnexpectedObjectException if this assumption doesn't hold
        """
        lock_ids = self.lock_ids_by_queue_id.get(queued_obj_id)
        for lock_id in lock_ids:
            queue = self.queue_by_lock_id[lock_id]
            if queue[0] != queued_obj_id:
                raise UnexpectedObjectException("This object shouldn't be removed")
        for lock_id in lock_ids:
            queue = self.queue_by_lock_id[lock_id]
            queue.popleft()
        return self.queue_objs_by_queue_id.pop(queued_obj_id)

    def _check_lock(self, lock_ids):
        return any(lock_id in self.currently_locked for lock_id in lock_ids)

    def _set_lock(self, lock_ids):
        """ Trys to set locks for given lock ids

        If already locked, returns false. If acquired, returns True
        """
        if self._check_lock(lock_ids):
            return False
        self.currently_locked.update(lock_ids)
        return True

    def _release_lock(self, lock_ids):
        self.currently_locked.difference_update(lock_ids)


class UnexpectedObjectException(Exception):
    pass


class MigrationRestricted(Exception):
    pass
