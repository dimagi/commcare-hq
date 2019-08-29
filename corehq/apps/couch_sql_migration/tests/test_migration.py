import json
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import TestCase, override_settings

import attr
import mock
import six
from couchdbkit.exceptions import ResourceNotFound
from nose.tools import nottest
from six.moves import zip
from testil import tempdir

from casexml.apps.case.mock import CaseBlock
from couchforms.models import XFormInstance
from dimagi.utils.parsing import ISO_DATETIME_FORMAT
from pillowtop.reindexer.change_providers.couch import (
    CouchDomainDocTypeChangeProvider,
)

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    BAD_FORM_PROBLEM_TEMPLATE,
    FIXED_FORM_PROBLEM_TEMPLATE,
)
from corehq.apps.commtrack.helpers import make_product
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
    FormEditNotAllowed,
    MissingFormXml,
)
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
    LedgerAccessors,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
)
from corehq.toggles import COUCH_SQL_MIGRATION_BLACKLIST, NAMESPACE_DOMAIN
from corehq.util.test_utils import (
    TestFileMixin,
    create_and_save_a_case,
    create_and_save_a_form,
    flag_enabled,
    patch_datadog,
    set_parent_case,
    softer_assert,
    trap_extra_setup,
)

from ..asyncforms import get_case_ids
from ..couchsqlmigration import MigrationRestricted, sql_form_to_json
from ..diffrule import ANY
from ..management.commands.migrate_domain_from_couch_to_sql import (
    COMMIT,
    MIGRATE,
    RESET,
)
from ..statedb import open_state_db

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
        # patch to workaround django call_command() bug with required options
        # which causes error when passing `state_dir=...`
        cls.state_dir_patch = mock.patch.dict(
            os.environ, CCHQ_MIGRATION_STATE_DIR=cls.state_dir)
        cls.state_dir_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.s3db.close()
        cls.tmp.__exit__(None, None, None)
        cls.state_dir_patch.stop()
        super(BaseMigrationTestCase, cls).tearDownClass()

    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()

        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain_name = uuid.uuid4().hex
        self.domain = create_domain(self.domain_name)
        # all new domains are set complete when they are created
        DomainMigrationProgress.objects.filter(domain=self.domain_name).delete()
        self.assert_backend("couch")
        self.migration_success = None

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain.delete()

    def _do_migration(self, domain=None, action=MIGRATE, **options):
        if domain is None:
            domain = self.domain_name
        self.assert_backend("couch", domain)
        options.setdefault("no_input", True)
        options.setdefault("diff_process", False)
        with mock.patch(
            "corehq.form_processor.backends.sql.dbaccessors.transaction.atomic",
            atomic_savepoint,
        ):
            try:
                call_command('migrate_domain_from_couch_to_sql', domain, action, **options)
                success = True
            except SystemExit:
                success = False
        self.migration_success = success

    def _do_migration_and_assert_flags(self, domain, **options):
        self._do_migration(domain, **options)
        self.assert_backend("sql", domain)

    def _compare_diffs(self, expected_diffs=None, missing=None):
        def diff_key(diff):
            return diff.kind, diff.json_diff.diff_type, diff.json_diff.path

        state = open_state_db(self.domain_name, self.state_dir)
        diffs = sorted(state.get_diffs(), key=diff_key)
        json_diffs = [(diff.kind, diff.json_diff) for diff in diffs]
        self.assertEqual(json_diffs, expected_diffs or [])
        self.assertEqual({
            kind: counts.missing
            for kind, counts in six.iteritems(state.get_doc_counts())
            if counts.missing
        }, missing or {})
        if not expected_diffs and not self.migration_success:
            self.fail("migration failed")

    def _get_form_ids(self, doc_type='XFormInstance'):
        return set(
            FormAccessors(domain=self.domain_name)
            .get_all_form_ids_in_domain(doc_type=doc_type)
        )

    def _iter_forms(self, form_ids):
        db = FormAccessors(domain=self.domain_name)
        for form_id in form_ids:
            yield db.get_form(form_id)

    def _get_case_ids(self, doc_type=None):
        if doc_type is None:
            return set(CaseAccessors(domain=self.domain_name).get_case_ids_in_domain())
        db = XFormInstance.get_db()
        return set(get_doc_ids_in_domain_by_type(self.domain_name, doc_type, db))

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

    def submit_form(self, xml, received_on=None):
        # NOTE freezegun.freeze_time does not work with the blob db
        # boto3 and/or minio -> HeadBucket 403 Forbidden
        form = submit_form_locally(xml, self.domain_name).xform
        if received_on is not None:
            if isinstance(received_on, timedelta):
                received_on = datetime.utcnow() + received_on
            form.received_on = received_on
            form.save()
        log.debug("form %s received on %s", form.form_id, form.received_on)
        return form

    @contextmanager
    def patch_migration_chunk_size(self, chunk_size):
        path = "corehq.apps.couch_sql_migration.couchsqlmigration._iter_docs.chunk_size"
        with mock.patch(path, chunk_size):
            yield


class MigrationTestCase(BaseMigrationTestCase):
    def test_migration_blacklist(self):
        COUCH_SQL_MIGRATION_BLACKLIST.set(self.domain_name, True, NAMESPACE_DOMAIN)
        with self.assertRaises(MigrationRestricted):
            self._do_migration(self.domain_name)
        COUCH_SQL_MIGRATION_BLACKLIST.set(self.domain_name, False, NAMESPACE_DOMAIN)

    def test_migration_custom_report(self):
        with self.assertRaises(MigrationRestricted):
            self._do_migration("up-nrhm")

    def test_basic_form_migration(self):
        create_and_save_a_form(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._compare_diffs([])

    def test_basic_form_migration_with_timezones(self):
        form_xml = self.get_xml('tz_form')
        with override_settings(PHONE_TIMEZONES_HAVE_BEEN_PROCESSED=False,
                               PHONE_TIMEZONES_SHOULD_BE_PROCESSED=False):
            submit_form_locally(form_xml, self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_case_ids()))
        self.assertEqual(1, len(self._get_form_ids()))
        self._compare_diffs([])

    def test_form_with_not_meta_migration(self):
        submit_form_locally(SIMPLE_FORM_XML, self.domain_name)
        couch_form_ids = self._get_form_ids()
        self.assertEqual(1, len(couch_form_ids))
        self._do_migration_and_assert_flags(self.domain_name)
        sql_form_ids = self._get_form_ids()
        self.assertEqual(couch_form_ids, sql_form_ids)
        self._compare_diffs([])

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
        form = FormAccessors(self.domain_name).get_form(form_id)
        form.xmlns = None
        del form.form_data['@xmlns']
        xml_no_xmlns = form_template.format(form_id=form_id, xmlns="")
        form.delete_attachment('form.xml')
        form.put_attachment(xml_no_xmlns, 'form.xml')

        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._compare_diffs([])

    def test_archived_form_migration(self):
        form = create_and_save_a_form(self.domain_name)
        form.archive('user1')
        self.assertEqual(self._get_form_ids('XFormArchived'), {form.form_id})
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(self._get_form_ids('XFormArchived'), {form.form_id})
        self._compare_diffs([])

    def test_archived_form_with_case_migration(self):
        self.submit_form(make_test_form("archived")).archive()
        self.assertEqual(self._get_form_ids('XFormArchived'), {'archived'})
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(self._get_form_ids('XFormArchived'), {'archived'})
        self.assertEqual(self._get_case_ids('CommCareCase-Deleted'), {'test-case'})
        self._compare_diffs([])

    def test_error_form_migration(self):
        submit_form_locally(ERROR_FORM, self.domain_name)
        self.assertEqual(self._get_form_ids('XFormError'), {"im-a-bad-form"})
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(self._get_form_ids('XFormError'), {"im-a-bad-form"})
        self._compare_diffs([])

    def test_error_with_normal_doc_type_migration(self):
        submit_form_locally(ERROR_FORM, self.domain_name)
        form = FormAccessors(self.domain_name).get_form('im-a-bad-form')
        form_json = form.to_json()
        form_json['doc_type'] = 'XFormInstance'
        XFormInstance.wrap(form_json).save()
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(self._get_form_ids('XFormError'), {'im-a-bad-form'})
        self._compare_diffs([])

    def test_duplicate_form_migration(self):
        with open('corehq/ex-submodules/couchforms/tests/data/posts/duplicate.xml', encoding='utf-8') as f:
            duplicate_form_xml = f.read()

        submit_form_locally(duplicate_form_xml, self.domain_name)
        submit_form_locally(duplicate_form_xml, self.domain_name)

        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self._compare_diffs([])

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
        self._do_migration_and_assert_flags(self.domain_name)
        assertState()
        self._compare_diffs([])

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
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._compare_diffs([])

    def test_deleted_form_migration(self):
        form = create_and_save_a_form(self.domain_name)
        FormAccessors(self.domain.name).soft_delete_forms(
            [form.form_id], datetime.utcnow(), 'test-deletion'
        )

        self.assertEqual(1, len(get_doc_ids_in_domain_by_type(
            self.domain_name, "XFormInstance-Deleted", XFormInstance.get_db())
        ))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(FormAccessorSQL.get_deleted_form_ids_in_domain(self.domain_name)))
        self._compare_diffs([])

    def test_edited_deleted_form(self):
        form = create_and_save_a_form(self.domain_name)
        form.edited_on = datetime.utcnow() - timedelta(days=400)
        form.save()
        FormAccessors(self.domain.name).soft_delete_forms(
            [form.form_id], datetime.utcnow(), 'test-deletion'
        )
        self.assertEqual(
            get_doc_ids_in_domain_by_type(
                form.domain, "XFormInstance-Deleted", XFormInstance.get_db()
            ),
            [form.form_id],
        )
        self._do_migration_and_assert_flags(form.domain)
        self.assertEqual(
            FormAccessorSQL.get_deleted_form_ids_in_domain(form.domain),
            [form.form_id],
        )
        self._compare_diffs([])

    def test_submission_error_log_migration(self):
        try:
            submit_form_locally(b"To be an XForm or NOT to be an xform/>", self.domain_name)
        except LocalSubmissionError:
            pass

        self.assertEqual(1, len(self._get_form_ids(doc_type='SubmissionErrorLog')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids(doc_type='SubmissionErrorLog')))
        self._compare_diffs([])

    def test_hqsubmission_migration(self):
        form = create_and_save_a_form(self.domain_name)
        form.doc_type = 'HQSubmission'
        form.save()

        self.assertEqual(get_doc_ids_in_domain_by_type(
            self.domain_name, "HQSubmission", XFormInstance.get_db()
        ), [form.form_id])
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(self._get_form_ids(), {form.form_id})
        self._compare_diffs([])

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
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))
        self._compare_diffs([])

    def test_basic_case_migration(self):
        create_and_save_a_case(self.domain_name, case_id=uuid.uuid4().hex, case_name='test case')
        self.assertEqual(1, len(self._get_case_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_case_ids()))
        self._compare_diffs([])

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
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_case_ids()))
        self._compare_diffs([])

    def test_case_with_indices_migration(self):
        parent_case_id = uuid.uuid4().hex
        child_case_id = uuid.uuid4().hex
        parent_case = create_and_save_a_case(self.domain_name, case_id=parent_case_id, case_name='test parent')
        child_case = create_and_save_a_case(self.domain_name, case_id=child_case_id, case_name='test child')
        set_parent_case(self.domain_name, child_case, parent_case)

        self.assertEqual(2, len(self._get_case_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(2, len(self._get_case_ids()))
        self._compare_diffs([])

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
        self.assertEqual(2, len(get_doc_ids_in_domain_by_type(
            self.domain_name, "CommCareCase-Deleted", XFormInstance.get_db())
        ))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(2, len(CaseAccessorSQL.get_deleted_case_ids_in_domain(self.domain_name)))
        self._compare_diffs([])
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
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(2, len(self._get_form_ids()))
        self.assertEqual(2, len(self._get_case_ids()))
        self._compare_diffs([])

    def test_commit(self):
        self._do_migration_and_assert_flags(self.domain_name)
        clear_local_domain_sql_backend_override(self.domain_name)
        self._do_migration(action=COMMIT)
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
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(2, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_case_ids()))
        self._compare_diffs([])

    def test_timings(self):
        with patch_datadog() as received_stats:
            self._do_migration_and_assert_flags(self.domain_name)
        tracked_stats = [
            'commcare.couch_sql_migration.unprocessed_cases.count.duration:',
            'commcare.couch_sql_migration.main_forms.count.duration:',
            'commcare.couch_sql_migration.unprocessed_forms.count.duration:',
            'commcare.couch_sql_migration.count.duration:',
        ]
        for t_stat in tracked_stats:
            self.assertTrue(
                any(r_stat.startswith(t_stat) for r_stat in received_stats),
                "missing stat %r" % t_stat,
            )

    def test_live_migrate(self):
        self.submit_form(make_test_form("test-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("test-2"), timedelta(minutes=-90))
        self.submit_form(make_test_form("test-3"), timedelta(minutes=-85))
        self.submit_form(make_test_form("test-4"))
        self.assert_backend("couch")

        with self.patch_migration_chunk_size(2):
            self._do_migration(live=True)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        with self.assertRaises(CommandError):
            self._do_migration(action=COMMIT)

        self.submit_form(make_test_form("test-5"))
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2", "test-3", "test-4", "test-5"})

        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(self._get_form_ids(), {"test-1", "test-2", "test-3", "test-4", "test-5"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

    def test_migrate_archived_form_after_live_migration_of_error_forms(self):
        # The theory of this test is that XFormArchived comes earlier in
        # the "unprocessed_forms" iteration than XFormError. It ensures
        # that an archived form added after an error form that was not
        # processed by the previous live migration will be migrated.
        self.submit_form(ERROR_FORM)
        self._do_migration(live=True)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids('XFormError'), set())

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        self.submit_form(make_test_form("archived")).archive(trigger_signals=False)

        self._do_migration_and_assert_flags(self.domain_name)
        self._compare_diffs([])
        self.assertEqual(self._get_form_ids("XFormError"), {"im-a-bad-form"})
        self.assertEqual(self._get_form_ids("XFormArchived"), {"archived"})

    def test_edit_form_after_live_migration(self):
        self.assert_backend("couch")
        self.submit_form(make_test_form("test-1"), timedelta(minutes=-90))

        self._do_migration(live=True)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        with self.assertRaises(FormEditNotAllowed):
            self.submit_form(make_test_form("test-1", age=30))

        self._do_migration_and_assert_flags(self.domain_name)
        self._compare_diffs([])
        self.assertEqual(self._get_form_ids(), {"test-1"})
        self.assertEqual(self._get_form_ids("XFormDeprecated"), set())
        form = FormAccessorSQL.get_form("test-1")
        self.assertIsNone(form.edited_on)
        self.assertEqual(form.form_data["age"], '27')
        case = self._get_case("test-case")
        self.assertEqual(case.dynamic_case_properties()["age"], '27')

    def test_migrate_archived_form_after_live_migration(self):
        def describe(form):
            try:
                arg0 = json.loads(form.form_data.get("args"))[0]
            except Exception:
                arg0 = repr(form)
            return "%s %s" % (form.form_data.get("name", form.form_id), arg0)

        self.submit_form(make_test_form("arch-1"), timedelta(minutes=-95))
        self.submit_form(make_test_form("arch-2"), timedelta(minutes=-90)).archive()
        with self.patch_migration_chunk_size(1):
            self._do_migration(live=True)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"arch-1"})
        self.assertEqual(self._get_form_ids("XFormArchived"), {"arch-2"})
        self.assertEqual(self._get_case_ids(), {"test-case"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self.assert_backend("couch")
        FormAccessors(self.domain_name).get_form("arch-1").archive()

        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(
            {describe(f) for f in self._iter_forms(self._get_form_ids())},
            {"archive_form arch-1"},
        )
        self.assertEqual(self._get_form_ids("XFormArchived"), {"arch-1", "arch-2"})
        self.assertEqual(self._get_case_ids("CommCareCase-Deleted"), {"test-case"})
        self._compare_diffs([])

    def test_reset_migration(self):
        now = datetime.utcnow()
        self.submit_form(make_test_form("test-1"), now - timedelta(minutes=95))
        self.assert_backend("couch")

        self._do_migration(live=True)
        self.assert_backend("sql")
        self.assertEqual(self._get_form_ids(), {"test-1"})

        clear_local_domain_sql_backend_override(self.domain_name)
        self._do_migration(action=RESET)
        self.assert_backend("couch")
        self.assertEqual(self._get_form_ids(), {"test-1"})
        form_ids = FormAccessorSQL \
            .get_form_ids_in_domain_by_type(self.domain_name, "XFormInstance")
        self.assertEqual(form_ids, [])

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

        self._do_migration_and_assert_flags(self.domain_name)

        case = self._get_case("89da")
        self.assertEqual(set(case.xform_ids), {"f1-9017", "f2-b1ce", "f3-7c38", "f4-3226"})
        self._compare_diffs([])

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

        self._do_migration_and_assert_flags(self.domain_name)

        case = self._get_case("test-case")
        self.assertEqual(case.xform_ids, ["new-form"])
        self._compare_diffs([])
        form = FormAccessors(self.domain_name).get_form('new-form')
        self.assertEqual(form.deprecated_form_id, "test-form")
        self.assertIsNone(form.problem)

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
        self.assertEqual(self._get_case("test-case").xform_ids, ["test-form"])
        self.assertEqual(self._get_case("other-case").xform_ids, ["test-form"])

        self._do_migration_and_assert_flags(self.domain_name)

        self.assertEqual(self._get_case("other-case").xform_ids, ["test-form"])
        with self.assertRaises(CaseNotFound):
            self._get_case("test-case")
        self._compare_diffs([])

    def test_form_with_missing_xml(self):
        create_form_with_missing_xml(self.domain_name)
        self._do_migration_and_assert_flags(self.domain_name, diff_process=True)

        # This may change in the future: it may be possible to rebuild the
        # XML using parsed form JSON from couch.
        with self.assertRaises(CaseNotFound):
            self._get_case("test-case")
        self._compare_diffs([
            ('XFormInstance', Diff('missing', ['form', '#type'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', '@name'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', '@uiVersion'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', '@version'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', '@xmlns'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', 'age'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', 'case'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', 'first_name'], new=MISSING)),
            ('XFormInstance', Diff('missing', ['form', 'meta'], new=MISSING)),
        ], missing={'CommCareCase': 1})


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

    def _submit_ledgers(self, ledger_blocks):
        return submit_case_blocks(ledger_blocks, self.domain_name)[0].form_id

    def _set_balance(self, balance, case_id, product_id, type=None):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        return self._submit_ledgers([
            get_single_balance_block(case_id, product_id, balance, type=type)
        ])

    def test_migrate_ledgers(self):
        case_id = uuid.uuid4().hex
        create_and_save_a_case(self.domain_name, case_id=case_id, case_name="Simon's sweet shop")
        self._set_balance(100, case_id, self.liquorice._id, type="set_the_liquorice_balance")
        self._set_balance(50, case_id, self.sherbert._id)
        self._set_balance(175, case_id, self.jelly_babies._id)

        expected_stock_state = {'stock': {
            self.liquorice._id: 100,
            self.sherbert._id: 50,
            self.jelly_babies._id: 175
        }}
        self._validate_ledger_data(self._get_ledger_state(case_id), expected_stock_state)
        self._do_migration_and_assert_flags(self.domain_name)
        self._validate_ledger_data(self._get_ledger_state(case_id), expected_stock_state)

        transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id)
        self.assertEqual(3, len(transactions))

        self._compare_diffs([])

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

    def get_form_with_missing_xml(self):
        return create_form_with_missing_xml(self.domain_name)

    def test_sql_form_to_json_with_missing_xml(self):
        self.domain.use_sql_backend = True
        self.domain.save()
        form = self.get_form_with_missing_xml()
        data = sql_form_to_json(form)
        self.assertEqual(data["form"], {})

    def test_get_case_ids_with_missing_xml(self):
        form = self.get_form_with_missing_xml()
        self.assertEqual(get_case_ids(form), {"test-case"})


def create_form_with_missing_xml(domain_name):
    form = submit_form_locally(TEST_FORM, domain_name).xform
    form = FormAccessors(domain_name).get_form(form.form_id)
    blobs = get_blob_db()
    with mock.patch.object(blobs.metadb, "delete"):
        if isinstance(form, XFormInstance):
            # couch
            form.delete_attachment("form.xml")
        else:
            # sql
            blobs.delete(form.get_attachment_meta("form.xml").key)
        try:
            form.get_xml()
            assert False, "expected MissingFormXml exception"
        except MissingFormXml:
            pass
    return form


@nottest
def make_test_form(form_id, age=27):
    form = TEST_FORM
    assert form.count(">test-form<") == 1
    assert form.count(">27<") == 2
    form = form.replace(">27<", ">%s<" % age)
    return form.replace(">test-form<", ">%s<" % form_id)


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


@attr.s(cmp=False)
class Diff(object):

    type = attr.ib(default=ANY)
    path = attr.ib(default=ANY)
    old = attr.ib(default=ANY)
    new = attr.ib(default=ANY)

    def __eq__(self, other):
        if type(other) == FormJsonDiff:
            return (
                self.type == other.diff_type
                and self.path == other.path
                and self.old == other.old_value
                and self.new == other.new_value
            )
        return NotImplemented

    __hash__ = None


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
