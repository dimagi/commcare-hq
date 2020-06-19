import json
import logging
import os
import sys
import uuid
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta
from functools import wraps
from signal import SIGINT

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.management import call_command as django_call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import TestCase, override_settings

import attr
import mock
from couchdbkit.exceptions import ResourceNotFound
from gevent.pool import Pool
from nose.tools import nottest
from testil import tempdir

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xform import CaseProcessingResult
from corehq.apps.domain.models import Domain
from corehq.util.metrics.tests.utils import capture_metrics
from couchforms.models import XFormInstance
from dimagi.utils.parsing import ISO_DATETIME_FORMAT

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    BAD_FORM_PROBLEM_TEMPLATE,
    FIXED_FORM_PROBLEM_TEMPLATE,
)
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.processing import StockProcessingResult
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain_migration_flags.models import DomainMigrationProgress
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.tzmigration.timezonemigration import MISSING, FormJsonDiff
from corehq.blobs import get_blob_db
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
    LedgerAccessorSQL,
)
from corehq.form_processor.exceptions import (
    CaseNotFound,
    MissingFormXml,
    NotAllowed,
)
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
    LedgerAccessors,
)
from corehq.form_processor.submission_post import (
    CaseStockProcessingResult,
    SubmissionPost,
)
from corehq.form_processor.system_action import SYSTEM_ACTION_XMLNS
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import convert_xform_to_json, should_use_sql_backend
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
)
from corehq.toggles import COUCH_SQL_MIGRATION_BLACKLIST, NAMESPACE_DOMAIN
from corehq.util.test_utils import (
    TestFileMixin,
    create_and_save_a_case,
    create_and_save_a_form,
    flag_enabled,
    set_parent_case,
    softer_assert,
    trap_extra_setup,
)

from .. import casedifftool
from .. import couchsqlmigration as mod
from ..asyncforms import get_case_ids
from ..diffrule import ANY
from ..management.commands.migrate_domain_from_couch_to_sql import (
    CACHED,
    COMMIT,
    MIGRATE,
    REBUILD,
    RECHECK,
    RESET,
    STATS,
)
from ..statedb import init_state_db, open_state_db
from ..util import UnhandledError


log = logging.getLogger(__name__)


class BaseMigrationTestCase(TestCase, TestFileMixin):
    file_path = 'data',
    root = os.path.dirname(__file__)
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(BaseMigrationTestCase, cls).setUpClass()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
            cls.s3db = TemporaryS3BlobDB(config)
            assert get_blob_db() is cls.s3db, (get_blob_db(), cls.s3db)
        cls.tmp = tempdir()
        cls.state_dir = cls.tmp.__enter__()
        cls.pool_mock = mock.patch.object(casedifftool, "Pool", MockPool)
        cls.patches = [
            # patch to workaround django call_command() bug with required options
            # which causes error when passing `state_dir=...`
            mock.patch.dict(os.environ, CCHQ_MIGRATION_STATE_DIR=cls.state_dir),
            mock.patch.object(casedifftool, "load_and_diff_cases", log_and_diff_cases()),
            cls.pool_mock,
        ]
        for patch in cls.patches:
            patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.s3db.close()
        cls.tmp.__exit__(None, None, None)
        for patch in cls.patches:
            patch.stop()
        super(BaseMigrationTestCase, cls).tearDownClass()

    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()

        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain_name = uuid.uuid4().hex[:7]
        self.domain = create_domain(self.domain_name)
        # all new domains are set complete when they are created
        DomainMigrationProgress.objects.filter(domain=self.domain_name).delete()
        self.assert_backend("couch")
        self.migration_success = None

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain.delete()

    def do_migration(self, action=MIGRATE, domain=None, chunk_size=0, **options):
        if domain is None:
            domain = self.domain_name
        if chunk_size:
            patch_chunk_size = self.patch_migration_chunk_size(chunk_size)
        else:
            patch_chunk_size = suppress()  # until nullcontext with py3.7
        diffs = options.pop("diffs", None)
        ignore_fail = options.pop("ignore_fail", False)
        if "missing_docs" not in options:
            patch_find_missing_docs = mock.patch(
                "corehq.apps.couch_sql_migration.management.commands"
                ".migrate_domain_from_couch_to_sql.find_missing_docs"
            )
        else:
            patch_find_missing_docs = suppress()
        if action != STATS and should_use_sql_backend(self.domain_name):
            clear_local_domain_sql_backend_override(self.domain_name)
            self.assert_backend("couch", domain)
        self.migration_success = None
        options.setdefault("no_input", True)
        assert "diff_process" not in options, options  # old/invalid option
        with mock.patch(
            "corehq.form_processor.backends.sql.dbaccessors.transaction.atomic",
            atomic_savepoint,
        ), patch_chunk_size, patch_find_missing_docs:
            try:
                call_command('migrate_domain_from_couch_to_sql', domain, action, **options)
                success = True
            except UnhandledError:
                raise
            except SystemExit:
                success = False
        self.assert_backend(("couch" if action == RESET else "sql"), domain)
        self.migration_success = success
        if action == MIGRATE and diffs is not IGNORE:
            self.compare_diffs(diffs=diffs, ignore_fail=ignore_fail)

    def compare_diffs(self, diffs=None, changes=None, missing=None, ignore_fail=False):
        statedb = open_state_db(self.domain_name, self.state_dir)
        self.assertEqual(Diff.getlist(statedb.iter_diffs()), diffs or [])
        self.assertEqual(Diff.getlist(statedb.iter_changes()), changes or [])
        self.assertEqual({
            kind: counts.missing
            for kind, counts in statedb.get_doc_counts().items()
            if counts.missing
        }, missing or {})
        if not (diffs or changes or missing or ignore_fail):
            if not self.migration_success:
                self.fail("migration failed")
            assert not self.is_live_migration(), "live migration not finished"

    def is_live_migration(self):
        from corehq.apps.couch_sql_migration.progress import (
            MigrationStatus,
            get_couch_sql_migration_status,
        )
        status = get_couch_sql_migration_status(self.domain_name)
        return status == MigrationStatus.DRY_RUN

    def _get_form_ids(self, doc_type='XFormInstance'):
        domain = self.domain_name
        if doc_type == "XFormInstance-Deleted" and should_use_sql_backend(domain):
            ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain)
        elif doc_type == "XFormInstance-Deleted" or doc_type == "HQSubmission":
            db = XFormInstance.get_db()
            ids = get_doc_ids_in_domain_by_type(domain, doc_type, db)
        else:
            ids = (FormAccessors(domain=self.domain_name)
                .get_all_form_ids_in_domain(doc_type=doc_type))
        return set(ids)

    def _iter_forms(self, doc_type='XFormInstance'):
        db = FormAccessors(domain=self.domain_name)
        for form_id in self._get_form_ids(doc_type):
            yield db.get_form(form_id)

    def _get_form(self, form_id):
        return FormAccessors(domain=self.domain_name).get_form(form_id)

    def _get_case_ids(self, doc_type="CommCareCase"):
        domain = self.domain_name
        if doc_type == "CommCareCase":
            return set(CaseAccessors(domain=domain).get_case_ids_in_domain())
        if doc_type == "CommCareCase-Deleted" and should_use_sql_backend(domain):
            return set(CaseAccessorSQL.get_deleted_case_ids_in_domain(domain))
        assert not should_use_sql_backend(domain)
        db = XFormInstance.get_db()
        return set(get_doc_ids_in_domain_by_type(domain, doc_type, db))

    def _get_case(self, case_id):
        return CaseAccessors(domain=self.domain_name).get_case(case_id)

    def assert_backend(self, backend, domain=None):
        if domain is None:
            domain = self.domain_name
        is_sql = should_use_sql_backend(domain)
        if backend == "sql":
            self.assertTrue(is_sql, "couch backend is active")
        else:
            assert backend == "couch", "typo? unknown backend: %s" % backend
            self.assertFalse(is_sql, "sql backend is active")

    def submit_form(self, xml, received_on=None, domain=None):
        # NOTE freezegun.freeze_time does not work with the blob db
        # boto3 and/or minio -> HeadBucket 403 Forbidden
        kw = self._submit_kwargs(received_on)
        return submit_form_locally(xml, domain or self.domain_name, **kw).xform

    def _submit_kwargs(self, received_on):
        if received_on is not None:
            if isinstance(received_on, timedelta):
                received_on = datetime.utcnow() + received_on
            return {"received_on": received_on}
        return {}

    @contextmanager
    def patch_migration_chunk_size(self, chunk_size):
        path = "corehq.apps.couch_sql_migration.couchsqlmigration._iter_docs.chunk_size"
        with mock.patch(path, chunk_size):
            yield

    def stop_on_doc(self, doc_type, doc_id):
        def stop():
            log.debug("stopping on %s", doc_id)
            raise KeyboardInterrupt
        return self.on_doc(doc_type, doc_id, stop)

    @contextmanager
    def on_doc(self, doc_type, doc_id, handler, raises=KeyboardInterrupt):
        from ..couchsqlmigration import _iter_docs

        @wraps(_iter_docs)
        def iter_docs(domain, iter_doc_type, **kw):
            itr = _iter_docs(domain, iter_doc_type, **kw)
            if doc_type == iter_doc_type:
                for doc in itr:
                    if doc["_id"] == doc_id:
                        handler()
                    log.debug("yielding %(_id)s", doc)
                    yield doc
            else:
                yield from itr

        if raises is not None:
            raise_context = self.assertRaises(KeyboardInterrupt)
        else:
            raise_context = null_context()
        path = "corehq.apps.couch_sql_migration.couchsqlmigration._iter_docs"
        with raise_context, mock.patch(path, iter_docs):
            yield

    @contextmanager
    def skip_case_and_ledger_updates(self, form_id):
        def maybe_get_result(self_, sql_form, couch_form):
            if couch_form.form_id == form_id:
                return None
            return get_result(self_, sql_form, couch_form)

        @staticmethod
        def maybe_process_xforms_for_cases(xforms, casedb):
            if any(f.form_id == form_id for f in xforms):
                assert len(xforms) == 1, xforms
                stock = StockProcessingResult(xforms[0])
                stock.populate_models()
                return CaseStockProcessingResult(
                    case_result=CaseProcessingResult(self.domain_name, [], []),
                    case_models=[],
                    stock_result=stock,
                )
            return process_forms(xforms, casedb)

        get_result = mod.CouchSqlDomainMigrator._get_case_stock_result
        process_forms = SubmissionPost.process_xforms_for_cases
        with mock.patch.object(
            mod.CouchSqlDomainMigrator,
            "_get_case_stock_result",
            maybe_get_result,
        ), mock.patch.object(
            SubmissionPost,
            "process_xforms_for_cases",
            maybe_process_xforms_for_cases,
        ):
            yield

    @contextmanager
    def diff_without_rebuild(self):
        couch_func = ("corehq.form_processor.backends.couch.processor"
                      ".FormProcessorCouch.hard_rebuild_case")
        sql_func = "corehq.apps.couch_sql_migration.casediff.rebuild_and_diff_cases"
        with mock.patch(couch_func) as couch_mock, mock.patch(sql_func) as sql_mock:
            couch_mock.side_effect = sql_mock.side_effect = Exception("fail!")
            yield


IGNORE = ANY


@contextmanager
def null_context():
    yield


@contextmanager
def get_report_domain():
    domain = Domain(
        name="up-nrhm",
        is_active=True,
        date_created=datetime.utcnow(),
        secure_submissions=True,
        use_sql_backend=False,
    )
    domain.save()
    try:
        yield domain
    finally:
        domain.delete()


class MigrationTestCase(BaseMigrationTestCase):

    def test_migration_blacklist(self):
        COUCH_SQL_MIGRATION_BLACKLIST.set(self.domain_name, True, NAMESPACE_DOMAIN)
        with self.assertRaises(mod.MigrationRestricted):
            self.do_migration()
        COUCH_SQL_MIGRATION_BLACKLIST.set(self.domain_name, False, NAMESPACE_DOMAIN)

    def test_migration_custom_report(self):
        with get_report_domain() as domain:
            with self.assertRaises(mod.MigrationRestricted):
                self.do_migration(domain=domain.name)

    def test_basic_form_migration(self):
        create_and_save_a_form(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.do_migration()
        self.assertEqual(1, len(self._get_form_ids()))

    def test_basic_form_migration_with_timezones(self):
        form_xml = self.get_xml('tz_form')
        with override_settings(PHONE_TIMEZONES_HAVE_BEEN_PROCESSED=False,
                               PHONE_TIMEZONES_SHOULD_BE_PROCESSED=False):
            submit_form_locally(form_xml, self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(1, len(self._get_case_ids()))
        self.assertEqual(1, len(self._get_form_ids()))

    def test_form_with_not_meta_migration(self):
        submit_form_locally(SIMPLE_FORM_XML, self.domain_name)
        couch_form_ids = self._get_form_ids()
        self.assertEqual(1, len(couch_form_ids))
        self.do_migration()
        sql_form_ids = self._get_form_ids()
        self.assertEqual(couch_form_ids, sql_form_ids)

    def test_form_with_missing_xmlns(self):
        form_id = uuid.uuid4().hex
        form_template = """<?xml version='1.0' ?>
        <data uiVersion="1" version="1" name=""{xmlns}>
            <name>fgg</name>
            <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
                <n1:deviceID>354957031935664</n1:deviceID>
                <n1:timeStart>2016-03-01T12:04:16Z</n1:timeStart>
                <n1:timeEnd>2016-03-01T12:04:16Z</n1:timeEnd>
                <n1:username>bcdemo</n1:username>
                <n1:userID>user-abc</n1:userID>
                <n1:instanceID>{form_id}</n1:instanceID>
            </n1:meta>
        </data>"""
        xml = form_template.format(
            form_id=form_id,
            xmlns=' xmlns="http://openrosa.org/formdesigner/456"'
        )
        submit_form_locally(xml, self.domain_name)

        # hack the form to remove XMLNS since it's now validated during form submission
        form = self._get_form(form_id)
        form.xmlns = None
        del form.form_data['@xmlns']
        xml_no_xmlns = form_template.format(form_id=form_id, xmlns="")
        form.delete_attachment('form.xml')
        form.put_attachment(xml_no_xmlns, 'form.xml')

        self.do_migration()
        self.assertEqual(1, len(self._get_form_ids()))

    def test_form_with_null_xmlns(self):
        form = submit_form_locally(ERROR_FORM, self.domain_name).xform
        form.xmlns = None
        form.save()
        self.do_migration()
        self.assertEqual(self._get_form_ids('XFormError'), {"im-a-bad-form"})

    def test_archived_form_migration(self):
        form = create_and_save_a_form(self.domain_name)
        form.archive('user1')
        self.assertEqual(self._get_form_ids('XFormArchived'), {form.form_id})
        self.do_migration()
        self.assertEqual(self._get_form_ids('XFormArchived'), {form.form_id})

    def test_archived_form_with_case_migration(self):
        self.submit_form(make_test_form("archived")).archive()
        self.assertEqual(self._get_form_ids('XFormArchived'), {'archived'})
        self.do_migration()
        self.assertEqual(self._get_form_ids('XFormArchived'), {'archived'})
        self.assertEqual(self._get_case_ids('CommCareCase-Deleted'), {'test-case'})

    def test_error_form_migration(self):
        submit_form_locally(ERROR_FORM, self.domain_name)
        self.assertEqual(self._get_form_ids('XFormError'), {"im-a-bad-form"})
        self.do_migration()
        self.assertEqual(self._get_form_ids('XFormError'), {"im-a-bad-form"})

    def test_error_with_normal_doc_type_migration(self):
        submit_form_locally(ERROR_FORM, self.domain_name)
        form = self._get_form('im-a-bad-form')
        form_json = form.to_json()
        form_json['doc_type'] = 'XFormInstance'
        XFormInstance.wrap(form_json).save()
        self.do_migration()
        self.assertEqual(self._get_form_ids('XFormError'), {'im-a-bad-form'})

    def test_duplicate_form_migration(self):
        with open('corehq/ex-submodules/couchforms/tests/data/posts/duplicate.xml', encoding='utf-8') as f:
            duplicate_form_xml = f.read()

        submit_form_locally(duplicate_form_xml, self.domain_name)
        submit_form_locally(duplicate_form_xml, self.domain_name)

        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self.do_migration()
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))

    @softer_assert()
    def test_deprecated_form_migration(self):
        form_id = uuid.uuid4().hex
        case_id = uuid.uuid4().hex
        owner_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            owner_id=owner_id,
            update={
                'property': 'original value'
            }
        ).as_text()
        submit_case_blocks(case_block, domain=self.domain_name, form_id=form_id)

        # submit a new form with a different case update
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='newtype',
            owner_id=owner_id,
            update={
                'property': 'edited value'
            }
        ).as_text()
        new_form = submit_case_blocks(case_block, domain=self.domain_name, form_id=form_id)[0]
        deprecated_id = new_form.deprecated_form_id

        def assertState():
            self.assertEqual(self._get_form_ids(), {form_id})
            self.assertEqual(self._get_form_ids('XFormDeprecated'), {deprecated_id})
            self.assertEqual(self._get_case_ids(), {case_id})

        assertState()
        self.do_migration()
        assertState()

    def test_old_form_metadata_migration(self):
        form_with_old_meta = """<?xml version="1.0" ?>
            <system uiVersion="1" version="1" xmlns="http://commcarehq.org/case">
                <meta xmlns="http://openrosa.org/jr/xforms">
                    <deviceID/>
                    <timeStart>2013-09-18T11:41:17Z</timeStart>
                    <timeEnd>2013-09-18T11:41:17Z</timeEnd>
                    <username>nnestle@dimagi.com</username>
                    <userID>06d75f978d3370f5b277b2685626b653</userID>
                    <uid>efe8d4306a7b426681daf33df41da46c</uid>
                </meta>
                <data>
                    <p1>123</p1>
                </data>
            </system>
        """
        submit_form_locally(form_with_old_meta, self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.do_migration()
        self.assertEqual(1, len(self._get_form_ids()))

    def test_deleted_form_migration(self):
        form = create_and_save_a_form(self.domain_name)
        FormAccessors(self.domain.name).soft_delete_forms(
            [form.form_id], datetime.utcnow(), 'test-deletion'
        )

        self.assertEqual(1, len(self._get_form_ids("XFormInstance-Deleted")))
        self.do_migration()
        self.assertEqual(1, len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain_name)))

    def test_edited_deleted_form(self):
        form = create_and_save_a_form(self.domain_name)
        form.edited_on = datetime.utcnow() - timedelta(days=400)
        form.save()
        FormAccessors(self.domain.name).soft_delete_forms(
            [form.form_id], datetime.utcnow(), 'test-deletion'
        )
        self.assertEqual(self._get_form_ids("XFormInstance-Deleted"), {form.form_id})
        self.do_migration()
        self.assertEqual(
            FormAccessorSQL.get_deleted_form_ids_in_domain(form.domain),
            [form.form_id],
        )

    def test_submission_error_log_migration(self):
        try:
            submit_form_locally(b"To be an XForm or NOT to be an xform/>", self.domain_name)
        except LocalSubmissionError:
            pass

        self.assertEqual(1, len(self._get_form_ids(doc_type='SubmissionErrorLog')))
        self.do_migration()
        self.assertEqual(1, len(self._get_form_ids(doc_type='SubmissionErrorLog')))

    def test_hqsubmission_migration(self):
        form = create_and_save_a_form(self.domain_name)
        form.doc_type = 'HQSubmission'
        form.save()

        self.assertEqual(self._get_form_ids("HQSubmission"), {form.form_id})
        self.do_migration()
        self.assertEqual(self._get_form_ids(), {form.form_id})

    @flag_enabled('MM_CASE_PROPERTIES')
    def test_migrate_attachments(self):
        attachment_source = './corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg'
        attachment_file = open(attachment_source, 'rb')
        attachments = {
            'fruity_file': UploadedFile(attachment_file, 'fruity_file', content_type='image/jpeg')
        }
        xml = """<?xml version='1.0' ?>
        <data uiVersion="1" version="1" name="" xmlns="http://openrosa.org/formdesigner/123">
            <name>fgg</name>
            <date>2011-06-07</date>
            <n0:case case_id="case-123" user_id="user-abc" date_modified="{date}"
                xmlns:n0="http://commcarehq.org/case/transaction/v2">
                <n0:create>
                    <n0:case_type_id>cc_bc_demo</n0:case_type_id>
                    <n0:case_name>fgg</n0:case_name>
                </n0:create>
                <n0:attachment>
                    <n0:fruity_file src="fruity_file" from="local"/>
                </n0:attachment>
            </n0:case>
            <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
                <n1:deviceID>354957031935664</n1:deviceID>
                <n1:timeStart>{date}</n1:timeStart>
                <n1:timeEnd>{date}</n1:timeEnd>
                <n1:username>bcdemo</n1:username>
                <n1:userID>user-abc</n1:userID>
                <n1:instanceID>{form_id}</n1:instanceID>
            </n1:meta>
        </data>""".format(
            date='2016-03-01T12:04:16Z',
            attachment_source=attachment_source,
            form_id=uuid.uuid4().hex
        )
        submit_form_locally(
            xml,
            self.domain_name,
            attachments=attachments,
        )

        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))

    def test_basic_case_migration(self):
        create_and_save_a_case(self.domain_name, case_id=uuid.uuid4().hex, case_name='test case')
        self.assertEqual(1, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(1, len(self._get_case_ids()))

    def test_basic_case_migration_case_name(self):
        case_id = uuid.uuid4().hex
        submit_case_blocks(
            CaseBlock(
                case_id,
                case_type='migrate',
                create=True,
                update={'p1': 1},
            ).as_text(),
            self.domain_name
        )

        submit_case_blocks(
            CaseBlock(
                case_id,
                update={'name': 'test21'},
            ).as_text(),
            self.domain_name
        )

        self.assertEqual(1, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(1, len(self._get_case_ids()))

    def test_case_with_indices_migration(self):
        parent_case_id = uuid.uuid4().hex
        child_case_id = uuid.uuid4().hex
        parent_case = create_and_save_a_case(self.domain_name, case_id=parent_case_id, case_name='test parent')
        child_case = create_and_save_a_case(self.domain_name, case_id=child_case_id, case_name='test child')
        set_parent_case(self.domain_name, child_case, parent_case)

        self.assertEqual(2, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(2, len(self._get_case_ids()))

        indices = CaseAccessorSQL.get_indices(self.domain_name, child_case_id)
        self.assertEqual(1, len(indices))
        self.assertEqual(parent_case_id, indices[0].referenced_id)

    def test_deleted_case_migration(self):
        parent_case_id = uuid.uuid4().hex
        child_case_id = uuid.uuid4().hex
        parent_case = create_and_save_a_case(self.domain_name, case_id=parent_case_id, case_name='test parent')
        child_case = create_and_save_a_case(self.domain_name, case_id=child_case_id, case_name='test child')
        set_parent_case(self.domain_name, child_case, parent_case)

        form_ids = self._get_form_ids()
        self.assertEqual(3, len(form_ids))
        FormAccessors(self.domain.name).soft_delete_forms(
            form_ids, datetime.utcnow(), 'test-deletion-with-cases'
        )
        CaseAccessors(self.domain.name).soft_delete_cases(
            [parent_case_id, child_case_id], datetime.utcnow(), 'test-deletion-with-cases'
        )
        self.assertEqual(2, len(self._get_case_ids("CommCareCase-Deleted")))
        self.do_migration()
        self.assertEqual(2, len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain_name)))
        parent_transactions = CaseAccessorSQL.get_transactions(parent_case_id)
        self.assertEqual(2, len(parent_transactions))
        self.assertTrue(parent_transactions[0].is_case_create)
        self.assertTrue(parent_transactions[1].is_form_transaction)
        child_transactions = CaseAccessorSQL.get_transactions(child_case_id)
        self.assertEqual(2, len(child_transactions))
        self.assertTrue(child_transactions[0].is_case_create)
        self.assertTrue(child_transactions[1].is_case_index)

    def test_form_touches_case_without_updates(self):
        case_id = uuid.uuid4().hex
        create_and_save_a_case(self.domain_name, case_id=case_id, case_name='touched by a form', user_id='user1')

        form_id = uuid.uuid4().hex
        xml = """<?xml version='1.0' ?>
                <data uiVersion="1" version="1" name="" xmlns="http://openrosa.org/formdesigner/123">
                    <name>fgg</name>
                    <date>2011-06-07</date>
                    <n0:case case_id="{case_id}" user_id="user1" date_modified="{date}"
                        xmlns:n0="http://commcarehq.org/case/transaction/v2">
                    </n0:case>
                    <n0:case case_id="case-123" user_id="user-abc" date_modified="{date}"
                        xmlns:n0="http://commcarehq.org/case/transaction/v2">
                        <n0:create>
                            <n0:case_type_id>cc_bc_demo</n0:case_type_id>
                            <n0:case_name>fgg</n0:case_name>
                        </n0:create>
                    </n0:case>
                    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
                        <n1:deviceID>354957031935664</n1:deviceID>
                        <n1:timeStart>{date}</n1:timeStart>
                        <n1:timeEnd>{date}</n1:timeEnd>
                        <n1:username>bcdemo</n1:username>
                        <n1:userID>user1</n1:userID>
                        <n1:instanceID>{form_id}</n1:instanceID>
                    </n1:meta>
                </data>""".format(
            date=datetime.utcnow(),
            form_id=form_id,
            case_id=case_id
        )
        result = submit_form_locally(xml, self.domain_name)
        case = [case for case in result.cases if case.case_id == case_id][0]
        case.xform_ids.remove(form_id)  # legacy bug that didn't include these form IDs in the case
        case.save()

        self.assertEqual(2, len(self._get_form_ids()))
        self.assertEqual(2, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(2, len(self._get_form_ids()))
        self.assertEqual(2, len(self._get_case_ids()))

    def test_commit(self):
        self.do_migration()
        self.do_migration(COMMIT)
        self.assert_backend("sql")

    def test_v1_case(self):
        xml = """<?xml version="1.0" ?>
            <data name="pregnancy checklist" uiVersion="1" version="1"
                  xmlns="http://openrosa.org/formdesigner/42461CD4-06D8-4FE5-BCEC-006130F7764F1"
                  xmlns:jrm="http://dev.commcarehq.org/jr/xforms">
                <name>RITA</name>
                <age>26</age>
                <number>918</number>
                <case>
                    <case_id>P0YJ</case_id>
                    <date_modified>2011-05-20T12:27:34.823+05:30</date_modified>
                    <create>
                        <case_type_id>pregnant_mother</case_type_id>
                        <case_name>RITA</case_name>
                        <user_id>XT3XPMS</user_id>
                        <external_id>RITA</external_id>
                    </create>
                    <update>
                        <name>RITA</name>
                    </update>
                </case>
                <meta>
                <deviceID>8D24OUKK3AR4ZG7NF9CYSQFAT</deviceID>
                <timeStart>2011-05-20T12:25:17.882+05:30</timeStart>
                <timeEnd>2011-05-20T12:27:34.831+05:30</timeEnd>
                <username>adevi</username>
                <userID>XT3XPMS</userID>
                <uid>WXJYZ</uid>
                </meta>
            </data>"""
        submit_form_locally(xml, self.domain_name)

        update_xml = """<?xml version="1.0" ?>
            <data name="pregnancy checklist" uiVersion="1" version="1"
                xmlns="http://openrosa.org/formdesigner/42461CD4-06D8-4FE5-BCEC-006130F7764F"
                xmlns:jrm="http://dev.commcarehq.org/jr/xforms">
                <case>
                    <case_id>P0YJ</case_id>
                    <date_modified>2012-02-24T00:51:07.836+05:30</date_modified>
                    <close/>
                </case>
                <meta>
                    <deviceID>44AV</deviceID>
                    <timeStart>2012-02-24T00:46:43.007+05:30</timeStart>
                    <timeEnd>2012-02-24T00:51:07.841+05:30</timeEnd>
                    <username>rek</username>
                    <userID>L53SD</userID>
                    <uid>Z75H7</uid>
                </meta>
            </data>"""
        submit_form_locally(update_xml, self.domain_name)

        self.assertEqual(2, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))
        self.do_migration()
        self.assertEqual(2, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))

    def test_timings(self):
        with capture_metrics() as received_stats:
            self.do_migration()
        tracked_stats = [
            'commcare.couch_sql_migration.unprocessed_cases.count',
            'commcare.couch_sql_migration.main_forms.count',
            'commcare.couch_sql_migration.unprocessed_forms.count',
            'commcare.couch_sql_migration.count',
        ]
        for t_stat in tracked_stats:
            self.assertIn(t_stat, received_stats, "missing stat %r" % t_stat)

    def test_live_migrate(self):
        self.submit_form(make_test_form("test-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("test-2"), timedelta(minutes=-90))
        self.submit_form(make_test_form("test-3"), timedelta(minutes=-85))
        self.submit_form(make_test_form("test-4"))
        self.assert_backend("couch")

        with self.patch_migration_chunk_size(2):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        with self.assertRaises(CommandError):
            self.do_migration(COMMIT)

        self.submit_form(make_test_form("test-5"))
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2", "test-3", "test-4", "test-5"})

        self.do_migration(finish=True)
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2", "test-3", "test-4", "test-5"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

    def test_migrate_form_twice(self):
        @contextmanager
        def interrupted_migration():
            from ..asyncforms import AsyncFormProcessor

            @wraps(AsyncFormProcessor.__exit__)
            def process_form1(self, *exc_info):
                self._finish_processing_queues()
                real_exit(self, *exc_info)

            real_exit = AsyncFormProcessor.__exit__
            with self.stop_on_doc("XFormInstance", "form-2"), \
                    mock.patch.object(AsyncFormProcessor, "__exit__", process_form1):
                yield

        self.submit_form(make_test_form("form-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("form-2"), timedelta(minutes=-90))

        with interrupted_migration():
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"form-1"})
        self.assertEqual(self._get_case_ids(), {"test-case"})
        self.compare_diffs(ignore_fail=True)

        clear_local_domain_sql_backend_override(self.domain_name)
        # change couch form, which has already been migrated, to create a diff
        form = self._get_form("form-1")
        form.form_data["first_name"] = "Zeena"
        form.save()

        # migration should re-diff previously migrated form-1
        self.do_migration(finish=True, diffs=[
            Diff('form-1', 'diff', ['form', 'first_name'], old="Zeena", new="Xeenax"),
        ])
        self.assertEqual(self._get_form_ids(), {"form-1", "form-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

    def test_migrate_unprocessed_form_twice(self):
        self.submit_form(make_test_form("form-1"), timedelta(minutes=-95)).archive()
        self.submit_form(make_test_form("form-2"), timedelta(minutes=-90)).archive()

        with self.stop_on_doc("XFormArchived", "form-2"):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids("XFormArchived"), {"form-1"})
        self.assertEqual(self._get_case_ids(), set())
        self.assertEqual(self._get_case_ids("CommCareCase-Deleted"), set())
        self.compare_diffs(ignore_fail=True)

        clear_local_domain_sql_backend_override(self.domain_name)
        # change couch form, which has already been migrated, to create a diff
        form = self._get_form("form-1")
        form.form_data["first_name"] = "Zeena"
        form.save()

        # migration should re-diff previously migrated form-1
        self.do_migration(finish=True, diffs=[
            Diff('form-1', 'diff', ['form', 'first_name'], old="Zeena", new="Xeenax"),
        ])
        self.assertEqual(self._get_form_ids("XFormArchived"), {"form-1", "form-2"})
        self.assertEqual(self._get_case_ids("CommCareCase-Deleted"), {"test-case"})

    def test_migrate_deleted_case_twice(self):
        form1 = make_test_form("form-1", case_id="case-1")
        form2 = make_test_form("form-2", case_id="case-2")
        self.submit_form(form1, timedelta(minutes=-95))
        self.submit_form(form2, timedelta(minutes=-90))
        now = datetime.utcnow()
        CaseAccessors(self.domain.name).soft_delete_cases(["case-1", "case-2"], now)

        with self.stop_on_doc("CommCareCase-Deleted", "case-2"):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"form-1", "form-2"})
        self.assertEqual(self._get_case_ids("CommCareCase-Deleted"), {"case-1"})
        self.assertEqual(self._get_case_ids(), {"case-2"})
        self.compare_diffs(ignore_fail=True)

        clear_local_domain_sql_backend_override(self.domain_name)
        # change couch case, which has already been migrated, to create a diff
        case = self._get_case("case-1")
        case.age = '35'
        case.save()

        # migration should re-diff previously migrated form-1
        with self.diff_without_rebuild():
            self.do_migration(finish=True, diffs=[
                Diff("case-1", 'diff', ['age'], old='35', new='27', kind="CommCareCase-Deleted"),
            ])
        self.assertEqual(self._get_case_ids("CommCareCase-Deleted"), {"case-1", "case-2"})

    def test_migrate_archived_form_after_live_migration_of_error_forms(self):
        # The theory of this test is that XFormArchived comes earlier in
        # the "unprocessed_forms" iteration than XFormError. It ensures
        # that an archived form added after an error form that was not
        # processed by the previous live migration will be migrated.
        self.submit_form(ERROR_FORM)
        self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids('XFormError'), set())

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        self.submit_form(make_test_form("archived")).archive()

        self.do_migration(finish=True)
        self.assertEqual(self._get_form_ids("XFormError"), {"im-a-bad-form"})
        self.assertEqual(
            {self._describe(f) for f in self._iter_forms("XFormArchived")},
            {"archived", "archive_form archived"}
        )

    def test_edit_form_after_live_migration(self):
        self.submit_form(make_test_form("test-1"), timedelta(minutes=-90))
        self.do_migration(live=True, diffs=IGNORE)
        self.assertEqual(self._get_form_ids(), {"test-1"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        with self.assertRaises(NotAllowed):
            self.submit_form(make_test_form("test-1", age=30))

        self.do_migration(finish=True)
        self.assertEqual(self._get_form_ids(), {"test-1"})
        self.assertEqual(self._get_form_ids("XFormDeprecated"), set())
        form = FormAccessorSQL.get_form("test-1")
        self.assertIsNone(form.edited_on)
        self.assertEqual(form.form_data["age"], '27')
        case = self._get_case("test-case")
        self.assertEqual(case.dynamic_case_properties()["age"], '27')

    def test_migrate_archived_form_after_live_migration(self):
        self.submit_form(make_test_form("arch-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("arch-2"), timedelta(minutes=-90)).archive()
        with self.patch_migration_chunk_size(1):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"arch-1"})
        self.assertEqual(self._get_form_ids("XFormArchived"), {"arch-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        self._get_form("arch-1").archive()

        self.do_migration(finish=True)
        self.assertFalse(self._get_form_ids())
        self.assertEqual(
            {self._describe(f) for f in self._iter_forms("XFormArchived")},
            {"arch-1", "arch-2", "archive_form arch-1"}
        )
        self.assertEqual(self._get_case_ids("CommCareCase-Deleted"), {"test-case"})

    def test_migrate_unarchived_form_after_live_migration(self):
        self.submit_form(make_test_form("form"), timedelta(minutes=-90))
        self.submit_form(make_test_form("arch"), timedelta(minutes=-95)).archive()
        with self.patch_migration_chunk_size(1):
            self.do_migration(live=True, diffs=IGNORE)
        self.assertEqual(self._get_form_ids("XFormArchived"), {"arch"})
        self.assertEqual(self._get_form_ids(), {"form"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        self._get_form("arch").unarchive()

        self.do_migration(finish=True, diffs=[
            # diff because "arch" was originally migrated as an "unprocessed_form"
            Diff('test-case', 'set_mismatch', ['xform_ids', '[*]'], old='arch', new=''),
        ])
        self.assertEqual(
            {self._describe(f) for f in self._iter_forms()},
            {"form", "arch"},
        )
        self.assertEqual(
            {self._describe(f) for f in self._iter_forms("XFormArchived")},
            {"archive_form arch"}
        )
        self.assertEqual(self._get_case_ids(), {"test-case"})

        self.do_migration(forms="missing", case_diff="patch")

    @staticmethod
    def _describe(form):
        data = form.form_data
        if data.get("@xmlns", "") == SYSTEM_ACTION_XMLNS:
            return f"{data['name']} {json.loads(data['args'])[0]}"
        return form.form_id

    def test_migrate_hard_deleted_entities_after_live_migration(self):
        from casexml.apps.case.cleanup import safe_hard_delete
        self.submit_form(make_test_form("form-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("form-2"), timedelta(minutes=-90)).soft_delete()
        with self.patch_migration_chunk_size(1):
            self.do_migration(live=True, diffs=IGNORE)
        self.compare_diffs(changes=[
            Diff("test-case", path=["xform_ids", "[*]"], old="form-2", new="", reason='rebuild case'),
        ])

        clear_local_domain_sql_backend_override(self.domain_name)
        safe_hard_delete(self._get_case("test-case"))

        self.do_migration(finish=True)
        deleted = FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain_name)
        self.assertEqual(set(deleted), {"form-2"})
        self.assertEqual(self._get_form_ids(), set())
        self.assertEqual(self._get_case_ids(), set())
        self.assertEqual(
            {self._describe(f) for f in self._iter_forms("XFormArchived")},
            {"hard_delete_case_and_forms test-case"}
        )

    def test_migrate_deleted_form_after_live_migration(self):
        self.submit_form(make_test_form("form-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("form-2"), timedelta(minutes=-90)).soft_delete()
        with self.patch_migration_chunk_size(1):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        with self.assertRaises(NotAllowed):
            self._get_form("form-1").soft_delete()
        with self.assertRaises(NotAllowed):
            FormAccessors(self.domain_name).soft_undelete_forms(["form-2"])
        self.assertEqual(self._get_form_ids(), {"form-1"})
        deleted = FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain_name)
        self.assertEqual(set(deleted), {"form-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        with self.assertRaises(NotAllowed):
            self._get_form("form-1").soft_delete()
        with self.assertRaises(NotAllowed):
            FormAccessors(self.domain_name).soft_undelete_forms(["form-2"])

        self.do_migration(finish=True, diffs=IGNORE)
        deleted = FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain_name)
        self.assertEqual(set(deleted), {"form-2"})
        self.assertEqual(self._get_form_ids(), {"form-1"})
        self.assertEqual(self._get_case_ids(), {"test-case"})
        self.compare_diffs(changes=[
            Diff("test-case", path=["xform_ids", "[*]"], old="form-2", new="", reason="rebuild case")
        ])

        self.do_migration(forms="missing", case_diff="patch")
        self.assertEqual(self._get_case("test-case").xform_ids, ["form-1", ANY])

    def test_delete_user_during_migration(self):
        from corehq.apps.users.models import CommCareUser
        user = CommCareUser.create(self.domain_name, "mobile-user", "123", None, None)
        # NOTE user is deleted when domain is deleted in tearDown
        with self.patch_migration_chunk_size(1):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        with self.assertRaises(NotAllowed):
            user.retire()
        with self.assertRaises(NotAllowed):
            user.unretire()

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        with self.assertRaises(NotAllowed):
            user.retire()
        with self.assertRaises(NotAllowed):
            user.unretire()

        self.do_migration(finish=True)
        self.do_migration(COMMIT)
        user.retire()
        user.unretire()

    def test_delete_cases_during_migration(self):
        from corehq.apps.hqcase.tasks import delete_exploded_cases
        self.submit_form(make_test_form("form-1"), timedelta(minutes=-95))
        with self.patch_migration_chunk_size(1):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        with self.assertRaises(NotAllowed):
            CaseAccessors(self.domain_name).soft_undelete_cases(["test-case"])

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        with self.assertRaises(NotAllowed):
            call_command("delete_related_cases", self.domain_name, "test-case")
        with self.assertRaises(NotAllowed):
            call_command("purge_forms_and_cases", self.domain_name, "app", "1", "nope")
        with self.assertRaises(NotAllowed):
            call_command("hard_delete_forms_and_cases_in_domain", self.domain_name)
        with self.assertRaises(NotAllowed):
            delete_exploded_cases(self.domain_name, "boom")
        with self.assertRaises(NotAllowed):
            CaseAccessors(self.domain_name).soft_undelete_cases(["test-case"])

        self.do_migration(finish=True)

    def test_migrate_skipped_forms(self):
        self.submit_form(make_test_form("test-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("test-2"), timedelta(minutes=-90))
        self.submit_form(make_test_form("test-3"), timedelta(minutes=-85))
        self.submit_form(make_test_form("test-4"))
        self.assert_backend("couch")

        with self.patch_migration_chunk_size(1), self.skip_forms({"test-1", "test-2"}):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-3"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        with self.patch_migration_chunk_size(1), self.skip_forms({"test-2"}):
            self.do_migration(STATS, missing_docs=REBUILD, diffs=IGNORE)
            self.do_migration(live=True, forms="missing", diffs=IGNORE)
        self.assertEqual(self._get_form_ids(), {"test-1", "test-3"})

        with self.patch_migration_chunk_size(1):
            self.do_migration(STATS, missing_docs=REBUILD, diffs=IGNORE)
        self.do_migration(forms="missing", diffs=IGNORE)
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2", "test-3"})

        self.do_migration(finish=True)
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2", "test-3", "test-4"})

    def test_migrate_missing_problem_form(self):
        with self.missing_problem_form():
            self.do_migration(forms="missing")

    def test_migrate_specific_problem_form(self):
        with self.missing_problem_form():
            self.do_migration(forms="form-2", missing_docs=RECHECK)

    @contextmanager
    def missing_problem_form(self):
        self.submit_form(make_test_form("form-1", age=31))
        with self.skip_case_and_ledger_updates("form-2"):
            form2 = self.submit_form(make_test_form("form-2", age=32))
            form2.problem = "did not process"
            form2.save()
            assert not form2.is_error, form2

        with self.skip_forms({"form-2"}):
            self.do_migration(missing_docs=CACHED, diffs=IGNORE)
        self.compare_diffs(missing={"XFormInstance": 1})
        self.assertEqual(self._get_form_ids(), {"form-1"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        yield
        form = self._get_form('form-2')
        assert form.is_error, form
        case = self._get_case("test-case")
        self.assertEqual(case.dynamic_case_properties()["age"], '31')

    @staticmethod
    def skip_forms(form_ids):
        def maybe_migrate_form(self, form, **kw):
            if form.form_id in form_ids:
                log.info("skipping %s", form.form_id)
            else:
                migrate(self, form, **kw)

        migrate = mod.CouchSqlDomainMigrator._migrate_form_and_associated_models
        return mock.patch.object(
            mod.CouchSqlDomainMigrator,
            "_migrate_form_and_associated_models",
            maybe_migrate_form,
        )

    def test_migrate_partially_migrated_form_with_case(self):
        # form      age     min     max
        # test-1    30      0       --
        # test-2    31      --      9
        self.submit_form(make_test_form("test-1", age=30, min=0), timedelta(days=-90))
        self.submit_form(make_test_form("test-2", age=31, max=9), timedelta(days=-1))
        self.assert_backend("couch")
        with self.skip_case_and_ledger_updates("test-1"):
            self.do_migration(live=True, diffs=[
                Diff("test-case", 'missing', ['min'], old='0', new=MISSING),
                Diff("test-case", 'set_mismatch', ['xform_ids', '[*]'], old='test-1', new=''),
            ])
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})
        self.do_migration(forms="missing", ignore_fail=True)
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

    def test_migrate_should_not_update_case_when_not_missing(self):
        self.submit_form(make_test_form("test-1", age=30, min=0), timedelta(days=-90))
        self.submit_form(make_test_form("test-2", age=31, max=9), timedelta(days=-1))
        self.assert_backend("couch")
        self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})
        diff = FormJsonDiff('set_mismatch', ['xform_ids', '[*]'], 'test-1', '')
        statedb = open_state_db(self.domain_name, self.state_dir, readonly=False)
        statedb.replace_case_diffs([("CommCareCase", "test-case", [diff])])
        with mock.patch.object(CaseAccessorSQL, "save_case") as save_case:
            save_case.side_effect = BaseException("unexpected save")
            self.do_migration(forms="missing", diffs=IGNORE)

    def test_reset_migration(self):
        now = datetime.utcnow()
        self.submit_form(make_test_form("test-1"), now - timedelta(minutes=95))
        self.assert_backend("couch")

        self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1"})

        self.do_migration(RESET)
        self.assert_backend("couch")
        self.assertEqual(self._get_form_ids(), {"test-1"})
        form_ids = FormAccessorSQL \
            .get_form_ids_in_domain_by_type(self.domain_name, "XFormInstance")
        self.assertEqual(form_ids, [])

    def test_migration_clean_break(self):
        def interrupt():
            os.kill(os.getpid(), SIGINT)
        self.migrate_with_interruption(interrupt, raises=None)
        self.assertEqual(self._get_form_ids(), {"one"})
        self.assertEqual(self.get_resume_state("CaseDiffQueue"), {'num_diffed_cases': 1})
        self.resume_after_interruption()

    def test_migration_dirty_break(self):
        def interrupt():
            os.kill(os.getpid(), SIGINT)
            os.kill(os.getpid(), SIGINT)
        self.migrate_with_interruption(interrupt)
        self.assertFalse(self._get_form_ids())
        self.assertEqual(self.get_resume_state("CaseDiffQueue"), {})
        self.resume_after_interruption()

    def migrate_with_interruption(self, interrupt, **kw):
        self.submit_form(make_test_form("one"), timedelta(minutes=-97))
        self.submit_form(make_test_form("two"), timedelta(minutes=-95))
        self.submit_form(make_test_form("arch"), timedelta(minutes=-93)).archive()
        with self.patch_migration_chunk_size(1), \
                self.on_doc("XFormInstance", "one", interrupt, **kw):
            self.do_migration(live=True, case_diff="asap", diffs=IGNORE)
        self.assertFalse(self._get_form_ids("XFormArchived"))

    def get_resume_state(self, key, default=object()):
        statedb = init_state_db(self.domain_name, self.state_dir)
        resume = statedb.pop_resume_state(key, default)
        with self.assertRaises(ValueError), resume as value:
            raise ValueError
        return value

    def resume_after_interruption(self):
        self.do_migration(finish=True)
        self.assertEqual(self._get_form_ids(), {"one", "two"})
        self.assertEqual(self._get_form_ids("XFormArchived"), {"arch"})

    def test_rebuild_state(self):
        def interrupt():
            os.kill(os.getpid(), SIGINT)
        form_ids = [f"form-{n}" for n in range(7)]
        for i, form_id in enumerate(form_ids):
            self.submit_form(make_test_form(form_id), timedelta(minutes=-90))
        with self.patch_migration_chunk_size(2), \
                self.on_doc("XFormInstance", "form-3", interrupt, raises=None):
            self.do_migration(live=True, diffs=IGNORE)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), set(form_ids[:4]))
        statedb = init_state_db(self.domain_name, self.state_dir)
        with statedb.pop_resume_state("CaseDiffQueue", None):
            pass  # simulate failed exit
        self.do_migration(live=True, rebuild_state=True, ignore_fail=True)
        self.assertEqual(self._get_form_ids(), set(form_ids))

    def test_case_forms_list_order(self):
        SERVER_DATES = [
            datetime.strptime("2015-07-13T11:21:00.639795Z", ISO_DATETIME_FORMAT),
            datetime.strptime("2015-07-13T11:24:27.467774Z", ISO_DATETIME_FORMAT),
            datetime.strptime("2015-07-13T11:21:00.639795Z", ISO_DATETIME_FORMAT),
            datetime.strptime("2017-04-27T14:23:14.683602Z", ISO_DATETIME_FORMAT),
        ]
        for xml, server_date in zip(LIST_ORDER_FORMS, SERVER_DATES):
            result = submit_form_locally(xml.strip(), self.domain_name)
            form = result.xform
            form.received_on = server_date
            form.save()

        case = self._get_case("89da")
        self.assertEqual(case.xform_ids, ["f1-9017", "f2-b1ce", "f3-7c38", "f4-3226"])

        self.do_migration()

        case = self._get_case("89da")
        self.assertEqual(set(case.xform_ids), {"f1-9017", "f2-b1ce", "f3-7c38", "f4-3226"})

    def test_normal_form_with_problem_and_case_updates(self):
        bad_form = submit_form_locally(TEST_FORM, self.domain_name).xform
        assert bad_form._id == "test-form", bad_form

        form = XFormInstance.wrap(bad_form.to_json())
        form._id = "new-form"
        form._rev = None
        form.problem = FIXED_FORM_PROBLEM_TEMPLATE.format(
            id_="test-form", datetime_="a day long ago")
        assert len(form.external_blobs) == 1, form.external_blobs
        form.external_blobs.pop("form.xml")
        form.initial_processing_complete = False
        with bad_form.fetch_attachment("form.xml", stream=True) as xml:
            form.put_attachment(xml, "form.xml", content_type="text/xml")
        form.save()

        bad_form.doc_type = "XFormDuplicate"
        bad_form.problem = BAD_FORM_PROBLEM_TEMPLATE.format("new-form", "a day long ago")
        bad_form.save()

        case = self._get_case("test-case")
        self.assertEqual(case.xform_ids, ["test-form"])

        self.do_migration(finish=True, diffs=IGNORE)

        case = self._get_case("test-case")
        self.assertEqual(case.xform_ids, ["new-form"])
        self.compare_diffs(changes=[
            Diff("test-case", path=["xform_ids", "[*]"], old="test-form", new="new-form", reason='rebuild case')
        ])
        form = self._get_form('new-form')
        self.assertEqual(form.deprecated_form_id, "test-form")
        self.assertIsNone(form.problem)

        self.do_migration(forms="missing", case_diff="patch")
        self.assertEqual(self._get_case("test-case").xform_ids, ["new-form", ANY])

    def test_case_with_problem_form(self):
        # form state=error, has problem, normal form in couch
        # move error to Operation, set state to normal, rebuild case
        self.submit_form(make_test_form("one", age=27))
        two = self.submit_form(make_test_form("two", age=30))
        two.problem = "Bad thing that happened"
        two.save()
        self.do_migration(diffs=[
            Diff('test-case', 'diff', ['age'], old='30', new='27'),
            Diff('test-case', 'set_mismatch', ['xform_ids', '[*]'], old='two', new=''),
        ])
        Mig = mod.CouchSqlDomainMigrator
        with mock.patch.object(Mig, "_apply_form_to_case", Mig._get_case_stock_result):
            self.do_migration(forms="missing", diffs=[
                Diff('test-case', 'diff', ['age'], old='30', new='27'),
                Diff('test-case', 'set_mismatch', ['xform_ids', '[*]'], old='two', new=''),
            ])
        self.do_migration(forms="missing")

    def test_case_with_unprocessed_form(self):
        # form state=normal, initial_processing_complete=false
        self.submit_form(make_test_form("one", age=27))
        two = self.submit_form(make_test_form("two", age=30))
        two.initial_processing_complete = False
        two.save()
        self.do_migration(diffs=[
            Diff('test-case', 'diff', ['age'], old='30', new='27'),
            Diff('test-case', 'set_mismatch', ['xform_ids', '[*]'], old='two', new=''),
        ])
        self.do_migration(forms="missing")

    def test_case_with_unprocessed_case_close_form(self):
        # form state=normal, initial_processing_complete=false
        self.submit_form(make_test_form("one", age=28))
        with self.skip_case_and_ledger_updates("two"):
            two = self.submit_form(make_test_form("two", age=30, closed=True))
        two.initial_processing_complete = False
        two.save()
        with self.skip_forms(["one"]):
            self.do_migration(missing_docs=CACHED, diffs=IGNORE)
        self.compare_diffs(
            missing={"XFormInstance": 1, "CommCareCase": 1}, diffs=IGNORE)
        self.do_migration(forms="missing", missing_docs=REBUILD)
        case = self._get_case("test-case")
        self.assertEqual(case.case_json["age"], "28")
        self.assertFalse(case.closed)

    def test_missing_case(self):
        # This can happen when a form is edited, removing the last
        # remaining reference to a case. The case effectively becomes
        # orphaned, and will be ignored by the migration.
        from corehq.apps.cloudcare.const import DEVICE_ID
        # replace device id to avoid edit form soft assert
        test_form = TEST_FORM.replace("cloudcare", DEVICE_ID)
        submit_form_locally(test_form, self.domain_name)
        edited_form = test_form.replace("test-case", "other-case")
        submit_form_locally(edited_form, self.domain_name)
        couch_case = self._get_case("test-case")
        self.assertEqual(couch_case.xform_ids, ["test-form"])
        self.assertEqual(self._get_case("other-case").xform_ids, ["test-form"])

        self.do_migration(finish=True, diffs=IGNORE)

        self.assertEqual(self._get_case("other-case").xform_ids, ["test-form"])
        with self.assertRaises(CaseNotFound):
            self._get_case("test-case")
        self.compare_diffs(changes=[
            Diff('test-case', 'missing', ['*'], old='*', new=MISSING, reason="orphaned case"),
        ])

        self.do_migration(forms="missing", case_diff="patch")
        sql_case = self._get_case("test-case")
        self.assertNotEqual(type(couch_case), type(sql_case))
        self.assertEqual(sql_case.dynamic_case_properties()["age"], '27')
        self.assertEqual(sql_case.modified_on, couch_case.modified_on)

    def test_missing_docs(self):
        self.submit_form(TEST_FORM, timedelta(minutes=-90))
        self.do_migration(live=True, diffs=IGNORE)
        FormAccessorSQL.hard_delete_forms(self.domain_name, ["test-form"])
        CaseAccessorSQL.hard_delete_cases(self.domain_name, ["test-case"])
        self.do_migration(missing_docs=REBUILD, finish=True, diffs=IGNORE)
        self.compare_diffs(
            missing={"XFormInstance": 1, "CommCareCase": 1},
            ignore_fail=True,
        )

    def test_form_with_missing_xml(self):
        create_form_with_missing_xml(self.domain_name)
        self.do_migration(finish=True)
        self.assertEqual(self._get_case_ids(), {"test-case"})

    def test_form_with_extra_xml_blob_metadata(self):
        form = create_form_with_extra_xml_blob_metadata(self.domain_name)
        self.do_migration(finish=True)
        self.assertEqual(
            [m.name for m in get_blob_db().metadb.get_for_parent(form.form_id)],
            ["form.xml"],
        )

    def test_unwrappable_form(self):
        def bad_wrap(doc):
            raise Exception(f"refusing to wrap {doc}")
        form_id = submit_form_locally(SIMPLE_FORM_XML, self.domain_name).xform.form_id
        with mock.patch.object(XFormInstance, "wrap", bad_wrap):
            self.do_migration(finish=True, diffs=[
                Diff(form_id, 'missing', ['_id'], new=MISSING),
                Diff(form_id, 'missing', ['auth_context'], new=MISSING),
                Diff(form_id, 'missing', ['doc_type'], new=MISSING),
                Diff(form_id, 'missing', ['domain'], new=MISSING),
                Diff(form_id, 'missing', ['form'], new=MISSING),
                Diff(form_id, 'missing', ['history'], new=MISSING),
                Diff(form_id, 'missing', ['initial_processing_complete'], new=MISSING),
                Diff(form_id, 'missing', ['openrosa_headers'], new=MISSING),
                Diff(form_id, 'missing', ['partial_submission'], new=MISSING),
                Diff(form_id, 'missing', ['received_on'], new=MISSING),
                Diff(form_id, 'missing', ['server_modified_on'], new=MISSING),
                Diff(form_id, 'missing', ['xmlns'], new=MISSING),
            ])

    def test_case_with_very_long_name(self):
        self.submit_form(make_test_form("naaaame", case_name="ha" * 128))
        self.do_migration(finish=True)

    def test_case_with_malformed_date_modified(self):
        bad_xml = TEST_FORM.replace('"2015-08-04T18:25:56.656Z"', '"2015-08-014"')
        assert bad_xml.count("2015-08-014") == 1, bad_xml
        form = submit_form_locally(TEST_FORM, self.domain_name).xform
        form.form_data["case"]["@date_modified"] = "2015-08-014"
        form.delete_attachment('form.xml')
        form.put_attachment(bad_xml, 'form.xml')
        form.save()
        self.do_migration()
        case = self._get_case("test-case")
        self.assertEqual(case.xform_ids, ["test-form"])
        self.assertEqual(case.modified_on, datetime(2015, 8, 14, 0, 0))


class LedgerMigrationTests(BaseMigrationTestCase):
    def setUp(self):
        super(LedgerMigrationTests, self).setUp()
        self.liquorice = make_product(self.domain_name, 'liquorice', 'liquorice')
        self.sherbert = make_product(self.domain_name, 'sherbert', 'sherbert')
        self.jelly_babies = make_product(self.domain_name, 'jelly babies', 'jbs')

    def tearDown(self):
        try:
            self.liquorice.delete()
            self.sherbert.delete()
            self.jelly_babies.delete()
        except ResourceNotFound:
            pass  # domain.delete() in parent class got there first
        super(LedgerMigrationTests, self).tearDown()

    def _set_balance(self, case_id, balances, received_on=None, type=None):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        ledger_blocks = [
            get_single_balance_block(case_id, product._id, balance, type=type)
            for product, balance in balances.items()
        ]
        kw = {"form_extras": self._submit_kwargs(received_on)}
        return submit_case_blocks(ledger_blocks, self.domain_name, **kw)[0].form_id

    def test_migrate_ledgers(self):
        case_id = uuid.uuid4().hex
        create_and_save_a_case(self.domain_name, case_id=case_id, case_name="Simon's sweet shop")
        self._set_balance(case_id, {self.liquorice: 100}, type="set_the_liquorice_balance")
        self._set_balance(case_id, {self.sherbert: 50})
        self._set_balance(case_id, {self.jelly_babies: 175})

        expected_stock_state = {'stock': {
            self.liquorice._id: 100,
            self.sherbert._id: 50,
            self.jelly_babies._id: 175
        }}
        self._validate_ledger_data(self._get_ledger_state(case_id), expected_stock_state)
        self.do_migration(finish=True)
        self._validate_ledger_data(self._get_ledger_state(case_id), expected_stock_state)

        transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id)
        self.assertEqual(3, len(transactions))

    def test_migrate_partially_migrated_form1_with_ledger(self):
        self.submit_form(TEST_FORM, timedelta(days=-5))  # create test-case
        form1 = self._set_balance("test-case", {
            self.liquorice: 50,
            self.sherbert: 100,
        }, timedelta(days=-3))
        form2 = self._set_balance("test-case", {self.liquorice: 75}, timedelta(days=-1))
        print("ledger forms:", form1, form2)
        with self.skip_case_and_ledger_updates(form1):
            self.do_migration(live=True, diffs=IGNORE)
        self.fix_missing_ledger_diffs(form1, form2, [
            Diff("test-case", "set_mismatch", ["xform_ids", "[*]"], old=form1, new=""),
            Diff(
                doc_id=f"test-case/stock/{self.sherbert._id}",
                kind="stock state",
                type="missing",
                path=["*"],
                old={'form_state': 'present', 'ledger': {
                    '_id': ANY,
                    'entry_id': self.sherbert._id,
                    'location_id': None,
                    'balance': 100,
                    'last_modified': ANY,
                    'domain': self.domain_name,
                    'section_id': 'stock',
                    'case_id': 'test-case',
                    'daily_consumption': None,
                    'last_modified_form_id': form1,
                }},
                new={'form_state': 'present'},
            ),
        ])

    def test_migrate_partially_migrated_form2_with_ledger(self):
        self.submit_form(TEST_FORM, timedelta(days=-5))  # create test-case
        form1 = self._set_balance("test-case", {
            self.liquorice: 50,
            self.sherbert: 100,
        }, timedelta(days=-3))
        form2 = self._set_balance("test-case", {self.liquorice: 75}, timedelta(days=-1))
        print("ledger forms:", form1, form2)
        with self.skip_case_and_ledger_updates(form2):
            self.do_migration(live=True, diffs=IGNORE)
        self.fix_missing_ledger_diffs(form1, form2, [
            Diff("test-case", "set_mismatch", ["xform_ids", "[*]"], old=form2, new=""),
            Diff(kind="stock state", path=["balance"], old=75, new=50),
            Diff(kind="stock state", path=['last_modified'], type="diff"),
            Diff(kind="stock state", path=['last_modified_form_id'], old=form2, new=form1),
        ])

    def fix_missing_ledger_diffs(self, form1, form2, diffs):
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {'test-form', form1, form2})
        self.assertEqual(self._get_case_ids(), {"test-case"})
        self.compare_diffs(diffs)
        self.do_migration(forms="missing", ignore_fail=True)
        self.assertEqual(self._get_form_ids(), {'test-form', form1, form2})
        self.assertEqual(self._get_case_ids(), {"test-case"})

    def _validate_ledger_data(self, state_dict, expected):
        for section, products in state_dict.items():
            for product, state in products.items():
                self.assertEqual(state.stock_on_hand, expected[section][product])

    def _get_ledger_state(self, case_id):
        return LedgerAccessors(self.domain_name).get_case_ledger_state(case_id)


class TestHelperFunctions(TestCase):

    def setUp(self):
        super(TestHelperFunctions, self).setUp()

        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain_name = uuid.uuid4().hex
        self.domain = create_domain(self.domain_name)
        self.assertFalse(should_use_sql_backend(self.domain_name))

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain.delete()

    def get_form_with_missing_xml(self, **kw):
        return create_form_with_missing_xml(self.domain_name, **kw)

    def test_sql_form_to_json_with_missing_xml(self):
        self.domain.use_sql_backend = True
        self.domain.save()
        form = self.get_form_with_missing_xml()
        data = mod.sql_form_to_json(form)
        self.assertEqual(data["form"], {})

    def test_get_case_ids_with_missing_xml(self):
        form = self.get_form_with_missing_xml()
        self.assertEqual(get_case_ids(form), {"test-case"})

    def test_migrate_form_attachments_missing_xml(self, couch_meta=True):
        def delete_blob():
            meta = sql_form.get_attachment_meta('form.xml')
            get_blob_db().delete(meta.key)
        couch_form = self.get_form_with_missing_xml(couch_meta=couch_meta)
        sql_form = mod.XFormInstanceSQL(
            form_id=couch_form.form_id,
            domain=couch_form.domain,
            xmlns=couch_form.xmlns,
            user_id=couch_form.user_id,
        )
        self.addCleanup(delete_blob)
        with mod.patch_XFormInstance_get_xml():
            mod._migrate_form_attachments(sql_form, couch_form)
        self.assertEqual(sql_form.form_data, couch_form.form_data)
        xml = sql_form.get_xml()
        self.assertEqual(convert_xform_to_json(xml), couch_form.form_data)

    def test_migrate_form_attachments_missing_xml_meta(self):
        self.test_migrate_form_attachments_missing_xml(couch_meta=False)


def create_form_with_missing_xml(domain_name, couch_meta=False):
    form = submit_form_locally(TEST_FORM, domain_name).xform
    form = FormAccessors(domain_name).get_form(form.form_id)
    blobs = get_blob_db()
    with mock.patch.object(blobs.metadb, "delete"):
        if isinstance(form, XFormInstance):
            # couch
            metaref = form.blobs["form.xml"]
            form.delete_attachment("form.xml")
            if couch_meta:
                form.blobs["form.xml"] = metaref
        else:
            # sql
            assert not couch_meta, "couch_meta=True not valid with SQL form"
            blobs.delete(form.get_attachment_meta("form.xml").key)
        try:
            form.get_xml()
            assert False, "expected MissingFormXml exception"
        except MissingFormXml:
            pass
    return form


def create_form_with_extra_xml_blob_metadata(domain_name):
    form = submit_form_locally(TEST_FORM, domain_name).xform
    form = FormAccessors(domain_name).get_form(form.form_id)
    meta = get_blob_db().metadb.get(
        parent_id=form.form_id, key=form.blobs["form.xml"].key)
    args = {n: getattr(meta, n) for n in [
        "domain",
        "parent_id",
        "type_code",
        "name",
        "content_length",
        "content_type",
        "properties",
    ]}
    get_blob_db().metadb.new(key=uuid.uuid4().hex, **args).save()
    return form


@nottest
def make_test_form(form_id, *, closed=False, **data):
    def update(form, pairs, ns=""):
        old = f"<{ns}age>27</{ns}age>"
        new = "".join(
            f"<{ns}{key}>{value}</{ns}{key}>"
            for key, value in pairs.items()
            if value is not None
        )
        assert form.count(old) == 1, (old, form.count(old))
        return form.replace(old, new)
    fields = {
        "case_id": ("test-case", '"{}"', 1),
        "case_name": ("Xeenax", ">{}<", 2),
        "date": ("2015-08-04T18:25:56.656Z", "{}", 2),
    }
    form = TEST_FORM
    updates = {}
    for name, value in data.items():
        if name not in fields:
            updates[name] = value
            continue
        default_value, template, occurs = fields[name]
        old = template.format(default_value)
        new = template.format(value)
        assert form.count(old) == occurs, (name, old, new, occurs)
        form = form.replace(old, new)
    if updates:
        form = update(form, updates)
        form = update(form, updates, "n0:")
    if closed:
        form.replace("</n0:update>", "</n0:update><n0:close />")
    return form.replace(">test-form<", f">{form_id}<")


def atomic_savepoint(*args, **kw):
    """Convert `savepoint=False` to `savepoint=True`

    Avoid error in tests, which are automatically wrapped in a transaction.

        An error occurred in the current transaction. You can't execute
        queries until the end of the 'atomic' block.
    """
    if kw.get("savepoint") is False:
        kw["savepoint"] = True
    return _real_atomic(*args, **kw)


_real_atomic = transaction.atomic


@attr.s
class MockPool:
    """Pool that uses greenlets rather than processes"""
    initializer = attr.ib()  # not used
    initargs = attr.ib()
    processes = attr.ib(default=None)
    maxtasksperchild = attr.ib(default=None)
    pool = attr.ib(factory=Pool, init=False)

    def imap_unordered(self, *args, **kw):
        from ..casediff import global_diff_state
        with global_diff_state(*self.initargs):
            yield from self.pool.imap_unordered(*args, **kw)


def log_and_diff_cases():
    """Always log diffed cases in tests"""
    def log_and_diff_cases(*args, **kw):
        kw.setdefault("log_cases", True)
        return load_and_diff_cases(*args, **kw)
    load_and_diff_cases = casedifftool.load_and_diff_cases
    return log_and_diff_cases


def call_command(*args, **kw):
    """call_command with patched sys.argv

    Handy for reading log output of failed tests. Otherwise commands log
    sys.argv of the test process, which is not very useful.
    """
    old = sys.argv
    sys.argv = list(args) + [f"--{k}={v}" for k, v in kw.items()]
    try:
        return django_call_command(*args, **kw)
    finally:
        sys.argv = old


@attr.s
class Diff:

    doc_id = attr.ib(default=ANY)
    type = attr.ib(default=ANY)
    path = attr.ib(default=ANY)
    old = attr.ib(default=ANY)
    new = attr.ib(default=ANY)
    kind = attr.ib(default=ANY)
    reason = attr.ib(default=ANY)
    __hash__ = None

    @classmethod
    def getlist(cls, diffs):
        from ..statedb import Change

        def make_diff(diff):
            json_diff = diff.json_diff
            return cls(
                doc_id=diff.doc_id,
                type=json_diff.diff_type,
                path=json_diff.path,
                old=json_diff.old_value,
                new=json_diff.new_value,
                kind=diff.kind,
                reason=(diff.reason if isinstance(diff, Change) else ''),
            )

        return sorted(make_diff(d) for d in diffs)


SIMPLE_FORM_XML = """<?xml version="1.0" ?>
<n0:registration xmlns:n0="http://openrosa.org/user/registration">
    <username>W4</username>
    <password>2</password>
    <uuid>P8DU7OLHVLZXU21JR10H3W8J2</uuid>
    <date>2013-11-19</date>
    <registering_phone_id>8H1N48EFPF6PA4UOO8YGZ2KFZ</registering_phone_id>
    <user_data>
        <data key="user_type">standard</data>
     </user_data>
</n0:registration>
"""


TEST_FORM = """
<?xml version="1.0" ?>
<data
    name="Registration"
    uiVersion="1"
    version="11"
    xmlns="http://openrosa.org/formdesigner/test-form"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <first_name>Xeenax</first_name>
    <age>27</age>
    <n0:case
        case_id="test-case"
        date_modified="2015-08-04T18:25:56.656Z"
        user_id="3fae4ea4af440efaa53441b5"
        xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:create>
            <n0:case_name>Xeenax</n0:case_name>
            <n0:owner_id>3fae4ea4af440efaa53441b5</n0:owner_id>
            <n0:case_type>testing</n0:case_type>
        </n0:create>
        <n0:update>
            <n0:age>27</n0:age>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2015-07-13T11:20:11.381Z</n1:timeStart>
        <n1:timeEnd>2015-08-04T18:25:56.656Z</n1:timeEnd>
        <n1:username>jeremy</n1:username>
        <n1:userID>3fae4ea4af440efaa53441b5</n1:userID>
        <n1:instanceID>test-form</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""".strip()


LIST_ORDER_FORMS = ["""
<?xml version="1.0" ?>
<data
    name="Visit"
    uiVersion="1" version="9"
    xmlns="http://openrosa.org/formdesigner/185A7E63-0ECD-4D9A-8357-6FD770B6F065"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <cur_num_anc>3</cur_num_anc>
    <health_id>Z1234</health_id>
    <n0:case
       case_id="89da"
       date_modified="2015-07-13T11:23:42.485Z"
       user_id="3fae4ea4af440efaa53441b5"
       xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:update>
            <n0:num_anc>3</n0:num_anc>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2015-07-13T11:22:58.234Z</n1:timeStart>
        <n1:timeEnd>2015-07-13T11:23:42.485Z</n1:timeEnd>
        <n1:username>jeremy</n1:username>
        <n1:userID>3fae4ea4af440efaa53441b5</n1:userID>
        <n1:instanceID>f1-9017</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""", """
<?xml version="1.0" ?>
<data
    name="Close"
    uiVersion="1"
    version="11"
    xmlns="http://openrosa.org/formdesigner/01EB3014-71CE-4EBE-AE34-647EF70A55DE"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <close_reason>pregnancy_ended</close_reason>
    <health_id>Z1234</health_id>
    <n0:case
        case_id="89da"
        date_modified="2015-07-13T11:24:26.614Z"
        user_id="3fae4ea4af440efaa53441b5"
        xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:close/>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2015-07-13T11:24:03.544Z</n1:timeStart>
        <n1:timeEnd>2015-07-13T11:24:26.614Z</n1:timeEnd>
        <n1:username>jeremy</n1:username>
        <n1:userID>3fae4ea4af440efaa53441b5</n1:userID>
        <n1:instanceID>f2-b1ce</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""", """
<?xml version="1.0" ?>
<data
    name="Register
    Pregnancy"
    uiVersion="1"
    version="11"
    xmlns="http://openrosa.org/formdesigner/882FC273-E436-4BA1-B8CC-9CA526FFF8C2"
    xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
>
    <health_id>Z1234</health_id>
    <first_name>Xeenax</first_name>
    <age>27</age>
    <n0:case
        case_id="89da"
        date_modified="2015-08-04T18:25:56.656Z"
        user_id="3fae4ea4af440efaa53441b5"
        xmlns:n0="http://commcarehq.org/case/transaction/v2"
    >
        <n0:create>
            <n0:case_name>Xeenax</n0:case_name>
            <n0:owner_id>3fae4ea4af440efaa53441b5</n0:owner_id>
            <n0:case_type>pregnancy</n0:case_type>
        </n0:create>
        <n0:update>
            <n0:age>27</n0:age>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2015-07-13T11:20:11.381Z</n1:timeStart>
        <n1:timeEnd>2015-08-04T18:25:56.656Z</n1:timeEnd>
        <n1:username>jeremy</n1:username>
        <n1:userID>3fae4ea4af440efaa53441b5</n1:userID>
        <n1:instanceID>f3-7c38</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""", """
<?xml version="1.0" ?>
<system
    uiVersion="1"
    version="1"
    xmlns="http://commcarehq.org/case"
    xmlns:orx="http://openrosa.org/jr/xforms"
>
    <orx:meta xmlns:cc="http://commcarehq.org/xforms">
        <orx:deviceID/>
        <orx:timeStart>2017-04-27T14:23:14.628725Z</orx:timeStart>
        <orx:timeEnd>2017-04-27T14:23:14.628725Z</orx:timeEnd>
        <orx:username>jwacksman@dimagi.com</orx:username>
        <orx:userID>743501c499f5f9e9843ffabc1919cea2</orx:userID>
        <orx:instanceID>f4-3226</orx:instanceID>
        <cc:appVersion/>
    </orx:meta>
    <case
        case_id="89da"
        date_modified="2017-04-27T14:23:14.143507Z"
        xmlns="http://commcarehq.org/case/transaction/v2"
    >
        <update>
            <health_id>Z12340</health_id>
        </update>
    </case>
</system>
"""]


ERROR_FORM = """<data xmlns="example.com/foo">
    <meta>
        <instanceID>im-a-bad-form</instanceID>
    </meta>
<case case_id="" xmlns="http://commcarehq.org/case/transaction/v2">
    <update><foo>bar</foo></update>
</case>
</data>"""
