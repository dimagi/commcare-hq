import csv
import io
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from itertools import chain

from django.conf import settings
from django.db.utils import IntegrityError

import attr
import gevent
from gevent.pool import Pool
from lxml import etree

from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.xform import (
    CaseProcessingResult,
    extract_case_blocks,
    get_all_extensions_to_close,
    get_case_updates,
)
from casexml.apps.case.xml.parser import CaseNoopAction
from couchforms.const import ATTACHMENT_NAME
from couchforms.models import XFormInstance, all_known_formlike_doc_types
from couchforms.models import doc_types as form_doc_types
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.parsing import ISO_DATETIME_FORMAT
from corehq.apps.couch_sql_migration.diff import (
    ignore_rules,
)
from corehq.apps.couch_sql_migration.diffrule import Ignore
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.tzmigration.api import (
    force_phone_timezones_should_be_processed,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.models import BlobMeta
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
from corehq.form_processor.utils import (
    adjust_datetimes,
    extract_meta_user_id,
    should_use_sql_backend,
)
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
    set_local_domain_sql_backend_override,
)
from corehq.toggles import COUCH_SQL_MIGRATION_BLACKLIST, NAMESPACE_DOMAIN
from corehq.util import cache_utils
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

from .asyncforms import AsyncFormProcessor
from .casediff import CaseDiffProcess, CaseDiffQueue
from .statedb import init_state_db

log = logging.getLogger(__name__)

CASE_DOC_TYPES = ['CommCareCase', 'CommCareCase-Deleted', ]

UNPROCESSED_DOC_TYPES = list(all_known_formlike_doc_types() - {'XFormInstance'})

UNDO_CSV = os.path.join(settings.BASE_DIR, 'corehq', 'apps', 'couch_sql_migration', 'undo_{domain}.csv')
UNDO_SET_DOMAIN = 'set_domain'
UNDO_CREATE = 'create'

ID_MAP_FILE = os.path.join(settings.BASE_DIR, 'corehq', 'apps', 'couch_sql_migration', 'id_map_{domain}.txt')


class MissingValueError(ValueError):
    pass


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
    handler.setLevel(logging.DEBUG)
    logging.root.addHandler(handler)
    log.info("command: %s", " ".join(sys.argv))


def do_couch_to_sql_migration(src_domain, state_dir, dst_domain=None, **kw):
    if dst_domain is None:
        dst_domain = src_domain

    if src_domain == dst_domain:
        # When src_domain is being migrated to a different dst_domain,
        # src_domain stays on Couch and dst_domain is always on SQL;
        # nothing changes.
        set_local_domain_sql_backend_override(src_domain)
    CouchSqlDomainMigrator(src_domain, state_dir, dst_domain, **kw).migrate()


def map_form_ids(form_json, form_root, id_map, ignore_paths):
    id_properties = (
        'activista_responsavel',
        'activista_responsavel_casa',
        'activista_responsavel_paciente',
        'location_id',
        'owner_id',
        'user_location_id',
    )

    for caseblock, path in extract_case_blocks(form_json, include_path=True):
        # Example caseblock:
        #     {u'@case_id': u'9fab567d-8c28-4cf0-acf2-dd3df04f95ca',
        #      u'@date_modified': datetime.datetime(2019, 2, 7, 9, 15, 48, 575000),
        #      u'@user_id': u'7ea59f550f35758447400937f800f78c',
        #      u'@xmlns': u'http://commcarehq.org/case/transaction/v2',
        #      u'create': {u'case_name': u'Abigail',
        #                  u'case_type': u'case',
        #                  u'owner_id': u'7ea59f550f35758447400937f800f78c'}}
        case_path = ['form'] + path + ['case']
        update_id(id_map, caseblock, '@userid', form_root,
                  base_path=case_path + ['@userid'], changed_id_paths=ignore_paths)

        if 'create' in caseblock:
            create_path = case_path + ['create']
            for prop in id_properties:
                update_id(id_map, caseblock['create'], prop, form_root,
                          base_path=create_path, changed_id_paths=ignore_paths,
                          case_id=caseblock.get('@case_id'))

        if 'update' in caseblock:
            update_path = case_path + ['update']
            for prop in id_properties:
                update_id(id_map, caseblock['update'], prop, form_root,
                          base_path=update_path, changed_id_paths=ignore_paths,
                          case_id=caseblock.get('@case_id'))

    update_id(id_map, form_json['meta'], 'userID', form_root,
              base_path=['form', 'meta'], changed_id_paths=ignore_paths)


def update_id(id_map, caseblock_or_meta, prop, form_root, base_path,
              changed_id_paths, case_id=None):
    """
    Maps the ID stored at `caseblock_or_meta`[`prop`] using `id_map`.
    Finds the same property under `form_root` Element, and maps it there
    too.

    Updates a list of paths of changed IDs.
    """
    if prop not in caseblock_or_meta or caseblock_or_meta[prop] not in id_map:
        return

    # The easy part: Update the caseblock
    old_id = caseblock_or_meta[prop]
    if not old_id:
        # Property has no value. Nothing to map.
        return
    new_id = id_map[old_id]
    caseblock_or_meta[prop] = new_id

    item_path = base_path + [prop]
    changed_id_paths.append(tuple(item_path))

    # The hard part: Update form.xml
    root_tag = get_localname(form_root)
    # Root node is "form" in form JSON, "data" in normal form XML, and
    # "system" in case imports.
    assert root_tag in ('data', 'system'), \
        'Unexpected Form XML root node "{}"'.format(root_tag)
    form_xml_path = [root_tag] + item_path[1:]

    case_create_path = ['system', 'case', 'create']
    case_update_path = ['system', 'case', 'update']
    if form_xml_path[:3] in [case_create_path, case_update_path] and case_id:
        _update_case_import(form_root, form_xml_path, prop, old_id, new_id, case_id)
    else:
        # This is a normal property create/update
        update_xml(form_root, form_xml_path, old_id, new_id)


def _update_case_import(form_root, form_xml_path, prop, old_id, new_id, case_id):
    create_or_update = form_xml_path[2]
    nsmap = {'c': "http://commcarehq.org/case/transaction/v2"}
    formxml_ids = form_root.xpath(
        './c:case[@case_id="{case_id}"]/c:{cu}/c:{prop}'.format(
            case_id=case_id,
            cu=create_or_update,
            prop=prop,
        ),
        namespaces=nsmap
    )
    assert formxml_ids, 'case {} for @case_id="{}" not found'.format(create_or_update, case_id)
    for formxml_id in formxml_ids:
        if formxml_id.text != old_id:
            # TODO: Find out why HQ returns a different form.xml
            # ID in form.xml != ID in couch form -- This case import was cancelled(?) and updated
            if formxml_id.text == new_id:
                # Nothing to do
                return

        formxml_id.text = new_id


def get_localname(elem):
    """
    Returns the tag name of `elem` without the namespace

    >>> xml = '<data xmlns="http://openrosa.org/formdesigner/C5AEC5A2-FF7D-4C00-9C7E-6B5AE23D735A"></data>'
    >>> root = etree.XML(xml)
    >>> get_localname(root) == 'data'
    True

    """
    tag = elem.tag
    if tag.startswith('{'):
        tag = tag.split('}')[1]
    return tag


def update_xml(xml, path, old_value, new_value):
    """
    Change a value in an XML document at path, where path is a list of
    node names.

    >>> decl = b"<?xml version='1.0' encoding='utf-8'?>\\n"
    >>> xml = '<foo><bar>BAZ</bar></foo>'
    >>> xml = update_xml(xml, ['foo', 'bar'], 'BAZ', 'QUUX')
    >>> xml == decl + b'<foo><bar>QUUX</bar></foo>'
    True

    """
    found = False

    def elem_has_attr(elem, string):
        return string.startswith('@') and string[1:] in elem.attrib

    def recurse_elements(elem, next_steps):
        nonlocal found

        assert next_steps, 'path is empty'
        step, next_steps = next_steps[0], next_steps[1:]
        if not next_steps:
            if get_localname(elem) == step:
                if elem.text == old_value:
                    found = True
                    elem.text = new_value
                elif elem.text is None and not old_value:
                    found = True
                    elem.text = new_value
            elif elem_has_attr(elem, step) and elem.attrib[step[1:]] == old_value:
                found = True
                elem.attrib[step[1:]] = new_value
            return
        for child in elem:
            if get_localname(child) == next_steps[0]:
                recurse_elements(child, next_steps)
        if len(next_steps) == 1 and elem_has_attr(elem, next_steps[0]):
            recurse_elements(elem, next_steps)

    if isinstance(xml, str) or isinstance(xml, bytes):
        root = etree.XML(xml)
        return_as_bytestring = True
    else:
        root = xml
        return_as_bytestring = False
    assert get_localname(root) == path[0], 'root "{}" not found in path {}'.format(root.tag, path)
    recurse_elements(root, path)
    if not found:
        raise MissingValueError('Unable to find "{value}" at path "{path}" in "{xml}".'.format(
            value=old_value,
            xml=xml if isinstance(xml, str) else etree.tostring(xml),
            path=path,
        ))
    if return_as_bytestring:
        return etree.tostring(root, encoding='utf-8', xml_declaration=True)


class CouchSqlDomainMigrator(object):

    def __init__(
        self,
        src_domain,
        state_dir,
        dst_domain,
        with_progress=True,
        debug=False,
        dry_run=False,
        live_migrate=False,
        diff_process=True,
    ):
        self.src_domain = src_domain
        self.dst_domain = dst_domain
        if self.same_domain():
            self._check_for_migration_restrictions(self.src_domain)
        self.with_progress = with_progress
        self.debug = debug
        self.dry_run = dry_run
        self.live_migrate = live_migrate
        self.live_stopper = LiveStopper(live_migrate)
        self.statedb = init_state_db(src_domain, state_dir)
        diff_queue = CaseDiffProcess if diff_process else CaseDiffQueue
        self.case_diff_queue = diff_queue(self.statedb)
        # exit immediately on uncaught greenlet error
        gevent.get_hub().SYSTEM_ERROR = BaseException

        if debug:
            assert log.level <= logging.DEBUG, log.level
            logging.root.setLevel(logging.DEBUG)
            for handler in logging.root.handlers:
                if handler.name in ["file", "console"]:
                    handler.setLevel(logging.DEBUG)

        self.errors_with_normal_doc_type = []
        self.forms_that_touch_cases_without_actions = set()
        self._id_map = {}
        self._id_map_filename = os.path.join(state_dir, f'id_map_{src_domain}-{dst_domain}.txt')

    def same_domain(self):
        """
        Are we migrating data from Couch to SQL in the same domain, or
        are we migrating from a Couch domain to a different SQL domain?
        """
        return self.src_domain == self.dst_domain

    def migrate(self):
        if self.same_domain():
            log.info('{live}migrating domain {domain} ({state})'.format(
                live=("live " if self.live_migrate else ""),
                domain=self.src_domain,
                state=self.statedb.unique_id,
            ))
        else:
            log.info('{live}migrating domain {src_domain} to {dst_domain} ({state})'.format(
                live=("live " if self.live_migrate else ""),
                src_domain=self.src_domain,
                dst_domain=self.dst_domain,
                state=self.statedb.unique_id,
            ))
            self._build_id_map()
            # Add expected diffs to `diff.ignore_rules`. This must be
            # done before `self._process_main_forms()` is called,
            # because it will memoize the value of `ignore_rules`.
            self._extend_ignore_rules()

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
        log.info('migrated domain {}'.format(self.src_domain))

    def _process_main_forms(self):
        """process main forms (including cases and ledgers)"""
        with AsyncFormProcessor(self.statedb, self._migrate_form) as pool:
            docs = self._get_resumable_iterator(['XFormInstance'])
            for doc in self._with_progress(['XFormInstance'], docs):
                pool.process_xform(doc)

        self._log_main_forms_processed_count()

    def _migrate_form(self, couch_form, case_ids):
        if self.same_domain():
            set_local_domain_sql_backend_override(self.src_domain)
        form_id = couch_form.form_id
        self._migrate_form_and_associated_models(couch_form)
        self.processed_docs += 1
        self.case_diff_queue.update(case_ids, form_id)
        self._log_main_forms_processed_count(throttled=True)

    def _migrate_form_and_associated_models(self, couch_form, form_is_processed=True):
        """
        Copies `couch_form` into a new sql form
        """
        sql_form = None
        couch_form, form_xml = self._map_form_ids(couch_form)
        # Get a new form ID when migrating to a different domain so that
        # form.xml attachments can be uniquely identified with parent_id
        form_id = couch_form.form_id if self.same_domain() else str(uuid.uuid4())
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
            sql_form = XFormInstanceSQL(
                form_id=form_id,
                domain=self.dst_domain,
                xmlns=xmlns,
                user_id=user_id,
            )
            _copy_form_properties(sql_form, couch_form)
            if not self.dry_run:
                _migrate_form_attachments(sql_form, couch_form, form_xml)
            _migrate_form_operations(sql_form, couch_form)

            if couch_form.doc_type != 'SubmissionErrorLog':
                self._save_diffs(couch_form, sql_form)

            if form_is_processed and self._is_formxml_avail():
                case_stock_result = self._get_case_stock_result(sql_form, couch_form)
            else:
                case_stock_result = None
            _save_migrated_models(sql_form, case_stock_result)
        except IntegrityError:
            exc_info = sys.exc_info()
            try:
                sql_form = FormAccessorSQL.get_form(form_id)
            except XFormNotFound:
                sql_form = None
                proc = "" if form_is_processed else " unprocessed"
                log.error("Error migrating%s form %s",
                    proc, couch_form.form_id, exc_info=exc_info)
        except Exception:
            proc = "" if form_is_processed else " unprocessed"
            log.exception("Error migrating%s form %s", proc, couch_form.form_id)
            try:
                sql_form = FormAccessorSQL.get_form(form_id)
            except XFormNotFound:
                sql_form = None
        finally:
            if couch_form.doc_type != 'SubmissionErrorLog':
                self._save_diffs(couch_form, sql_form)

    def _is_formxml_avail(self):
        # form.xml attachments are not available when doing a dry run of
        # a migration to a different domain
        return self.same_domain() or not self.dry_run

    def _build_id_map(self):
        """
        Iterate locations and mobile workers to map IDs in the source
        domain to IDs in the destination domain.

        These will be used to update forms as they are migrated.

        Apps and app builds are not mapped because they are not all in
        the destination domain.
        """
        all_users = chain(
            (u for u in CommCareUser.by_domain(self.dst_domain)),
            (u for u in CommCareUser.by_domain(self.dst_domain, is_active=False)),
            (u for u in WebUser.by_domain(self.dst_domain)),
            (u for u in WebUser.by_domain(self.dst_domain, is_active=False)),
        )
        self._id_map = {}
        for location in SQLLocation.objects.filter(domain=self.dst_domain):
            if 'orig_id' in location.metadata and location.metadata['orig_id']:
                self._id_map[location.metadata['orig_id']] = location.location_id
        for group in Group.by_domain(self.dst_domain):
            if group.metadata and 'orig_id' in group.metadata and group.metadata['orig_id']:
                self._id_map[group.metadata['orig_id']] = group._id
        for user in all_users:
            if 'orig_id' in user.user_data and user.user_data['orig_id']:
                self._id_map[user.user_data['orig_id']] = user.get_id
        self._dump_id_map()

    def _dump_id_map(self):
        with open(self._id_map_filename, 'w') as f:
            f.write('ID Map\n'
                    '------\n')
            for src, dst in self._id_map.items():
                f.write(' -> '.join((src, dst)))
                f.write('\n')
            f.write('\n')

    def _extend_ignore_rules(self):
        ignore_rules['CommCareCase*'].append(
            Ignore('diff', 'domain', old=self.src_domain, new=self.dst_domain)
        )
        ignore_rules['CommCareCase*'].extend([
            Ignore('diff', 'owner_id', old=src, new=dst)
            for src, dst in self._id_map.items()
        ])
        ignore_rules['CommCareCase'].append(
            # New xform attachments (with new IDs) are created when
            # migrating to a different domain
            Ignore(path=('xform_ids', '[*]'))
        )

    def _map_form_ids(self, couch_form):
        """
        The destination domain will have new IDs for locations, mobile
        workers, apps and app builds. Return the given form with source
        domain IDs mapped to the corresponding IDs in the destination
        domain.

        Leaves app IDs and build IDs unchanged.
        """
        if self.same_domain():
            return couch_form, None

        form_json = couch_form.form
        form_xml = couch_form.get_xml()
        form_root = etree.XML(form_xml)
        ignore_paths = []
        try:
            map_form_ids(form_json, form_root, self._id_map, ignore_paths)
        except MissingValueError as err:
            if couch_form.external_blobs and ATTACHMENT_NAME in couch_form.external_blobs:
                key = couch_form.external_blobs[ATTACHMENT_NAME].key
            else:
                key = None
            message = 'couch form ID {!r}. Attachment key {!r}.'.format(couch_form.form_id, key)
            raise MissingValueError('{} {}'.format(err, message))
        self.statedb.add_ignore_paths(couch_form.get_id, ignore_paths)
        form_xml = etree.tostring(form_root, encoding='utf-8', xml_declaration=True)
        return couch_form, form_xml

    def _map_case_ids(self, couch_case):
        if self.same_domain():
            return couch_case

        couch_case.owner_id = self._id_map.get(couch_case.owner_id, couch_case.owner_id)
        couch_case.user_id = self._id_map.get(couch_case.user_id, couch_case.user_id)
        couch_case.opened_by = self._id_map.get(couch_case.opened_by, couch_case.opened_by)
        couch_case.closed_by = self._id_map.get(couch_case.closed_by, couch_case.closed_by)
        return couch_case

    def _save_diffs(self, couch_form, sql_form):
        couch_json = couch_form.to_json()
        sql_json = {} if sql_form is None else sql_form_to_json(sql_form)
        if self.same_domain():
            ignore_paths = None
        else:
            ignore_paths = self.statedb.get_ignore_paths(couch_form.get_id) + [('domain',), ('_id',)]
        self.statedb.save_form_diffs(couch_json, sql_json, ignore_paths)

    def _get_case_stock_result(self, sql_form, couch_form):
        case_stock_result = None
        if sql_form.initial_processing_complete:
            case_stock_result = _get_case_and_ledger_updates(self.dst_domain, sql_form)
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

        doc_types = sorted(UNPROCESSED_DOC_TYPES)
        docs = self._get_resumable_iterator(doc_types)
        for couch_form_json in self._with_progress(doc_types, docs):
            pool.spawn(self._migrate_unprocessed_form, couch_form_json)

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        self._log_unprocessed_forms_processed_count()

    def _migrate_unprocessed_form(self, couch_form_json):
        log.debug('Processing doc: {}({})'.format(couch_form_json['doc_type'], couch_form_json['_id']))
        couch_form = _wrap_form(couch_form_json)
        self._migrate_form_and_associated_models(couch_form, form_is_processed=False)
        self.processed_docs += 1
        self._log_unprocessed_forms_processed_count(throttled=True)

    def _copy_unprocessed_cases(self):
        doc_types = ['CommCareCase-Deleted']
        pool = Pool(10)
        docs = self._get_resumable_iterator(doc_types)
        for doc in self._with_progress(doc_types, docs):
            pool.spawn(self._copy_unprocessed_case, doc)

        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))

        self._log_unprocessed_cases_processed_count()

    def _copy_unprocessed_case(self, doc):
        couch_case = CommCareCase.wrap(doc)
        log.debug('Processing doc: %(doc_type)s(%(_id)s)', doc)
        try:
            first_action = couch_case.actions[0]
        except IndexError:
            first_action = CommCareCaseAction()

        dst_couch_case = self._map_case_ids(couch_case)
        opened_on = couch_case.opened_on or first_action.date
        sql_case = CommCareCaseSQL(
            case_id=dst_couch_case.case_id,
            domain=self.dst_domain,
            type=dst_couch_case.type or '',
            name=dst_couch_case.name,
            owner_id=dst_couch_case.owner_id or dst_couch_case.user_id or '',
            opened_on=dst_couch_case.opened_on or first_action.date,
            opened_by=dst_couch_case.opened_by or first_action.user_id,
            modified_on=dst_couch_case.modified_on or opened_on,
            modified_by=dst_couch_case.modified_by or dst_couch_case.user_id or '',
            server_modified_on=dst_couch_case.server_modified_on,
            closed=dst_couch_case.closed,
            closed_on=dst_couch_case.closed_on,
            closed_by=dst_couch_case.closed_by,
            deleted=True,
            deletion_id=dst_couch_case.deletion_id,
            deleted_on=dst_couch_case.deletion_date,
            external_id=dst_couch_case.external_id,
            case_json=dst_couch_case.dynamic_case_properties()
        )
        _migrate_case_actions(dst_couch_case, sql_case)
        _migrate_case_indices(dst_couch_case, sql_case)
        _migrate_case_attachments(dst_couch_case, sql_case)
        try:
            CaseAccessorSQL.save_case(sql_case)
        except IntegrityError:
            # case re-created by form processing so just mark the case as deleted
            CaseAccessorSQL.soft_delete_cases(
                self.dst_domain,
                [sql_case.case_id],
                sql_case.deleted_on,
                sql_case.deletion_id
            )
        finally:
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
            get_doc_count_in_domain_by_type(self.src_domain, doc_type, XFormInstance.get_db())
            for doc_type in doc_types
        ])
        if self.timing_context:
            current_timer = self.timing_context.peek()
            current_timer.normalize_denominator = doc_count

        if self.with_progress:
            prefix = "{} ({})".format(progress_name, ', '.join(doc_types))
            return with_progress_bar(iterable, doc_count, prefix=prefix, oneline=False)
        else:
            log.info("{} {} ({})".format(progress_name, doc_count, ', '.join(doc_types)))
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

    def _get_resumable_iterator(self, doc_types):
        # resumable iteration state is associated with statedb.unique_id,
        # so it will be reset (orphaned in couch) if that changes
        migration_id = self.statedb.unique_id
        for doc_type in doc_types:
            yield from _iter_docs(
                self.src_domain,
                doc_type,
                resume_key="%s.%s.%s" % (self.src_domain, doc_type, migration_id),
                should_stop=self.live_stopper.get_stopper(),
            )

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


def append_undo(src_domain, meta, operation):
    filename = UNDO_CSV.format(domain=src_domain)
    with io.open(filename, 'a') as undo_csv:
        writer = csv.writer(undo_csv)
        row = (meta.parent_id, meta.key, operation)
        writer.writerow(row)


def _migrate_form_attachments(sql_form, couch_form, form_xml=None):
    """Copy over attachment meta"""
    attachments = []
    metadb = get_blob_db().metadb

    def try_to_get_blob_meta(parent_id, type_code, name):
        try:
            return metadb.get(
                parent_id=parent_id,
                type_code=type_code,
                name=name
            )
        except BlobMeta.DoesNotExist:
            return None

    if couch_form._attachments and any(
        name not in couch_form.blobs for name in couch_form._attachments
    ):
        _migrate_couch_attachments_to_blob_db(couch_form)

    for name, blob in couch_form.blobs.items():
        if name == "form.xml" and form_xml:
            # form_xml is None if we are migrating to the same domain
            attachment = Attachment(name='form.xml', raw_content=form_xml, content_type='text/xml')
            sql_form.attachments_list.append(attachment)
            continue

        type_code = CODES.form_xml if name == "form.xml" else CODES.form_attachment
        meta = try_to_get_blob_meta(couch_form.form_id, type_code, name)

        if meta and meta.domain != sql_form.domain:
            # meta domain is couch_form.domain; form is being migrated to sql_form.domain
            append_undo(couch_form.domain, meta, UNDO_SET_DOMAIN)
            meta.domain = sql_form.domain
            meta.save()

        # there was a bug in a migration causing the type code for many form attachments to be set as form_xml
        # this checks the db for a meta resembling this and fixes it for postgres
        # https://github.com/dimagi/commcare-hq/blob/3788966119d1c63300279418a5bf2fc31ad37f6f/corehq/blobs/migrate.py#L371
        if not meta and name != "form.xml":
            meta = try_to_get_blob_meta(couch_form.form_id, CODES.form_xml, name)
            if meta:
                append_undo(couch_form.domain, meta, UNDO_SET_DOMAIN)
                meta.domain = sql_form.domain
                meta.type_code = CODES.form_attachment
                meta.save()

        if not meta:
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
            append_undo(couch_form.domain, meta, UNDO_CREATE)

        attachments.append(meta)
    sql_form.attachments_list.extend(attachments)


def revert_form_attachment_meta_domain(src_domain):
    """
    Change form attachment meta.domain from dst_domain back to src_domain
    """
    filename = UNDO_CSV.format(domain=src_domain)
    try:
        csv_file = io.open(filename, 'r')
    except IOError as err:
        if 'No such file or directory' in str(err):
            # Nothing to undo
            return
        raise
    blob_db = get_blob_db()
    with csv_file as undo_csv:
        reader = csv.reader(undo_csv)
        for row in reader:
            parent_id, key, operation = row
            meta = blob_db.metadb.get(
                parent_id=parent_id,
                key=key,
            )
            if operation == UNDO_SET_DOMAIN:
                meta.domain = src_domain
                meta.save()
            elif operation == UNDO_CREATE:
                blob_db.delete(key=meta.key)
                meta.delete()

    os.unlink(filename)


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


@attr.s
class LiveStopper(object):
    live_migrate = attr.ib()

    # Minimum age of forms processed during live migration. This
    # prevents newly submitted forms from being skipped by the
    # migration.
    MIN_AGE = timedelta(hours=1)

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
    RETRIES = 5

    def __init__(self, domain, should_stop):
        self.domain = domain
        self.should_stop = should_stop
        self.retries = self.RETRIES

    def page_exception(self, e):
        if self.retries <= 0:
            return False
        self.retries -= 1
        gevent.sleep(1)
        return True

    def page(self, results):
        if self.should_stop is None or not results:
            return
        # this is tightly coupled to by_domain_doc_type_date/view in couch:
        # the last key element is expected to be a datetime string
        key_date = results[-1]['key'][-1]
        if key_date is None:
            return  # ...except when it isn't :(
        key_date = self._convert_date(key_date)
        if self.should_stop(key_date):
            raise StopToResume

    def page_end(self, total_emitted, duration, *args, **kwargs):
        self.retries = self.RETRIES
        cache_utils.clear_limit(self._cache_key())

    def _cache_key(self):
        return f"couchsqlmigration.{self.domain}"

    @staticmethod
    def _convert_date(value):
        try:
            return datetime.strptime(value, ISO_DATETIME_FORMAT)
        except ValueError:
            sans_micros = ISO_DATETIME_FORMAT.replace(".%f", "")
            return datetime.strptime(value, sans_micros)

    def stop(self):
        if self.should_stop is not None:
            # always stop to preserve resume state if we reach the end
            # of the iteration while in "live" mode
            raise StopToResume


def _iter_docs(domain, doc_type, resume_key, should_stop):
    def data_function(**view_kwargs):
        return couch_db.view('by_domain_doc_type_date/view', **view_kwargs)

    couch_db = XFormInstance.get_db()
    args_provider = NoSkipArgsProvider({
        'startkey': [domain, doc_type],
        'endkey': [domain, doc_type, {}],
        'limit': _iter_docs.chunk_size,
        'include_docs': True,
        'reduce': False,
    })
    rows = ResumableFunctionIterator(
        resume_key,
        data_function,
        args_provider,
        item_getter=None,
        event_handler=MigrationPaginationEventHandler(domain, should_stop)
    )
    return (row["doc"] for row in rows)


_iter_docs.chunk_size = 1000


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
