from __future__ import absolute_import
from __future__ import unicode_literals

import os
import uuid
from datetime import datetime, timedelta
from io import open

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

import attr
import mock
import six
from couchdbkit.exceptions import ResourceNotFound
from six.moves import zip

from casexml.apps.case.mock import CaseBlock
from couchforms.models import XFormInstance
from dimagi.utils.parsing import ISO_DATETIME_FORMAT

from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import (
    BAD_FORM_PROBLEM_TEMPLATE,
    FIXED_FORM_PROBLEM_TEMPLATE,
)
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain_migration_flags.models import DomainMigrationProgress
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.tzmigration.timezonemigration import FormJsonDiff, MISSING
from corehq.blobs import get_blob_db, NotFound as BlobNotFound
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
    LedgerAccessorSQL,
)
from corehq.form_processor.exceptions import CaseNotFound
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

from ..couchsqlmigration import (
    MigrationRestricted,
    PartiallyLockingQueue,
    get_case_ids,
    sql_form_to_json,
)
from ..diffrule import ANY
from ..management.commands.migrate_domain_from_couch_to_sql import (
    COMMIT,
    MIGRATE,
    RESET,
)
from ..statedb import open_state_db


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

    @classmethod
    def tearDownClass(cls):
        cls.s3db.close()
        super(BaseMigrationTestCase, cls).tearDownClass()

    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()

        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain_name = uuid.uuid4().hex
        self.domain = create_domain(self.domain_name)
        # all new domains are set complete when they are created
        DomainMigrationProgress.objects.filter(domain=self.domain_name).delete()
        self.assertFalse(should_use_sql_backend(self.domain_name))

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain.delete()

    def _do_migration(self, domain):
        self.assertFalse(should_use_sql_backend(domain))
        call_command('migrate_domain_from_couch_to_sql', domain, MIGRATE, no_input=True)

    def _do_migration_and_assert_flags(self, domain):
        self._do_migration(domain)
        self.assertTrue(should_use_sql_backend(domain))

    def _compare_diffs(self, expected_diffs=None, missing=None):
        def diff_key(diff):
            return diff.kind, diff.json_diff.diff_type, diff.json_diff.path

        state = open_state_db(self.domain_name)
        diffs = sorted(state.get_diffs(), key=diff_key)
        json_diffs = [(diff.kind, diff.json_diff) for diff in diffs]
        self.assertEqual(json_diffs, expected_diffs or [])
        self.assertEqual({
            kind: counts.missing
            for kind, counts in six.iteritems(state.get_doc_counts())
            if counts.missing
        }, missing or {})

    def _get_form_ids(self, doc_type='XFormInstance'):
        return FormAccessors(domain=self.domain_name).get_all_form_ids_in_domain(doc_type=doc_type)

    def _get_case_ids(self):
        return CaseAccessors(domain=self.domain_name).get_case_ids_in_domain()

    def _get_case(self, case_id):
        return CaseAccessors(domain=self.domain_name).get_case(case_id)


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
        xml = """<?xml version="1.0" ?>
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
        submit_form_locally(xml, self.domain_name)
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
        self.assertEqual(1, len(self._get_form_ids('XFormArchived')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids('XFormArchived')))
        self._compare_diffs([])

    def test_error_form_migration(self):
        submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>abc-easy-as-123</instanceID>
                </meta>
            <case case_id="" xmlns="http://commcarehq.org/case/transaction/v2">
                <update><foo>bar</foo></update>
            </case>
            </data>""",
            self.domain_name,
        )
        self.assertEqual(1, len(self._get_form_ids('XFormError')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids('XFormError')))
        self._compare_diffs([])

    def test_error_with_normal_doc_type_migration(self):
        submit_form_locally(
            """<data xmlns="example.com/foo">
                <meta>
                    <instanceID>im-a-bad-form</instanceID>
                </meta>
            <case case_id="" xmlns="http://commcarehq.org/case/transaction/v2">
                <update><foo>bar</foo></update>
            </case>
            </data>""",
            self.domain_name,
        )
        form = FormAccessors(self.domain_name).get_form('im-a-bad-form')
        form_json = form.to_json()
        form_json['doc_type'] = 'XFormInstance'
        XFormInstance.wrap(form_json).save()
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids('XFormError')))
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
            self.assertEqual(self._get_form_ids(), [form_id])
            self.assertEqual(self._get_form_ids('XFormDeprecated'), [deprecated_id])
            self.assertEqual(self._get_case_ids(), [case_id])

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

        self.assertEqual(1, len(get_doc_ids_in_domain_by_type(
            self.domain_name, "HQSubmission", XFormInstance.get_db())
        ))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
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
        call_command('migrate_domain_from_couch_to_sql', self.domain_name, COMMIT, no_input=True)
        self.assertTrue(Domain.get_by_name(self.domain_name).use_sql_backend)

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
            'commcare.couch_sql_migration.case_diffs.count.duration:',
            'commcare.couch_sql_migration.count.duration:',
        ]
        for t_stat in tracked_stats:
            self.assertTrue(
                any(r_stat.startswith(t_stat) for r_stat in received_stats),
                "missing stat %r" % t_stat,
            )

    def test_dry_run(self):
        self.assertFalse(should_use_sql_backend(self.domain_name))
        call_command(
            'migrate_domain_from_couch_to_sql',
            self.domain_name,
            MIGRATE,
            no_input=True,
            dry_run=True
        )
        clear_local_domain_sql_backend_override(self.domain_name)
        with self.assertRaises(CommandError):
            call_command('migrate_domain_from_couch_to_sql', self.domain_name, COMMIT, no_input=True)
        self.assertFalse(Domain.get_by_name(self.domain_name).use_sql_backend)

        xml = """<?xml version="1.0" ?>
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
        submit_form_locally(xml, self.domain_name)
        couch_form_ids = self._get_form_ids()
        self.assertEqual(1, len(couch_form_ids))

        call_command('migrate_domain_from_couch_to_sql', self.domain_name, RESET, no_input=True)
        self.assertFalse(Domain.get_by_name(self.domain_name).use_sql_backend)

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
        self._do_migration_and_assert_flags(self.domain_name)

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


class TestLockingQueues(TestCase):
    def setUp(self):
        self.queues = PartiallyLockingQueue("id", max_size=-1)

    def _add_to_queues(self, queue_obj_id, lock_ids):
        self.queues._add_item(lock_ids, DummyObject(queue_obj_id))
        self._check_queue_dicts(queue_obj_id, lock_ids, -1)

    def _check_queue_dicts(self, queue_obj_id, lock_ids, location=None, present=True):
        """
        if location is None, it looks anywhere. If it is an int, it'll look in that spot
        present determines whether it's expected to be in the queue_by_lock_id or not
        """
        for lock_id in lock_ids:
            if location is not None:
                self.assertEqual(
                    present,
                    (len(self.queues.queue_by_lock_id[lock_id]) > (location - 1) and
                        queue_obj_id == self.queues.queue_by_lock_id[lock_id][location]))
            else:
                self.assertEqual(present, queue_obj_id in self.queues.queue_by_lock_id[lock_id])

        self.assertItemsEqual(lock_ids, self.queues.lock_ids_by_queue_id[queue_obj_id])

    def _check_locks(self, lock_ids, lock_set=True):
        self.assertEqual(lock_set, self.queues._check_lock(lock_ids))

    def test_has_next(self):
        self.assertFalse(self.queues.has_next())
        self._add_to_queues('monadnock', ['heady_topper', 'sip_of_sunshine', 'focal_banger'])
        self.assertTrue(self.queues.has_next())

    def test_try_obj(self):
        # first object is fine
        lock_ids = ['grapefruit_sculpin', '60_minute', 'boom_sauce']
        queue_obj = DummyObject('little_haystack')
        self.assertTrue(self.queues.try_obj(lock_ids, queue_obj))
        self._check_locks(lock_ids, lock_set=True)
        self._check_queue_dicts('little_haystack', lock_ids, present=False)

        # following objects without overlapping locks are fine
        new_lock_ids = ['brew_free', 'steal_this_can']
        new_queue_obj = DummyObject('lincoln')
        self.assertTrue(self.queues.try_obj(new_lock_ids, new_queue_obj))
        self._check_locks(new_lock_ids, lock_set=True)
        self._check_queue_dicts('lincoln', new_lock_ids, present=False)

        # following ojbects with overlapping locks add to queue
        final_lock_ids = ['grapefruit_sculpin', 'wrought_iron']
        final_queue_obj = DummyObject('lafayette')
        self.assertFalse(self.queues.try_obj(final_lock_ids, final_queue_obj))
        self._check_queue_dicts('lafayette', final_lock_ids, -1)
        self._check_locks(['grapefruit_sculpin'], lock_set=True)
        self._check_locks(['wrought_iron'], lock_set=False)

    def test_get_next(self):
        # nothing returned if nothing in queues
        self.assertEqual(None, self.queues.get_next())

        # first obj in queues will be returned if nothing blocking
        lock_ids = ['old_chub', 'dales_pale', 'little_yella']
        queue_obj_id = 'moosilauke'
        self._add_to_queues(queue_obj_id, lock_ids)
        self.assertEqual(queue_obj_id, self.queues.get_next().id)
        self._check_locks(lock_ids, lock_set=True)

        # next object will not be returned if anything locks are held
        new_lock_ids = ['old_chub', 'ten_fidy']
        new_queue_obj_id = 'flume'
        self._add_to_queues(new_queue_obj_id, new_lock_ids)
        self.assertEqual(None, self.queues.get_next())
        self._check_locks(['ten_fidy'], lock_set=False)

        # next object will not be returned if not first in all queues
        next_lock_ids = ['ten_fidy', 'death_by_coconut']
        next_queue_obj_id = 'liberty'
        self._add_to_queues(next_queue_obj_id, next_lock_ids)
        self.assertEqual(None, self.queues.get_next())
        self._check_locks(next_lock_ids, lock_set=False)

        # will return something totally orthogonal though
        final_lock_ids = ['fugli', 'pinner']
        final_queue_obj_id = 'sandwich'
        self._add_to_queues(final_queue_obj_id, final_lock_ids)
        self.assertEqual(final_queue_obj_id, self.queues.get_next().id)
        self._check_locks(final_lock_ids)

    def test_release_locks(self):
        lock_ids = ['rubaeus', 'dirty_bastard', 'red\'s_rye']
        self._check_locks(lock_ids, lock_set=False)
        self.queues._set_lock(lock_ids)
        self._check_locks(lock_ids, lock_set=True)
        self.queues._release_lock(lock_ids)
        self._check_locks(lock_ids, lock_set=False)

        queue_obj = DummyObject('kancamagus')
        self.queues._add_item(lock_ids, queue_obj, to_queue=False)
        self.queues._set_lock(lock_ids)
        self._check_locks(lock_ids, lock_set=True)
        self.queues.release_lock_for_queue_obj(queue_obj)
        self._check_locks(lock_ids, lock_set=False)

    def test_max_size(self):
        self.assertEqual(-1, self.queues.max_size)
        self.assertFalse(self.queues.full)  # not full when no max size set
        self.queues.max_size = 2  # set max_size
        lock_ids = ['dali', 'manet', 'monet']
        queue_obj = DummyObject('osceola')
        self.queues._add_item(lock_ids, queue_obj)
        self.assertFalse(self.queues.full)  # not full when not full
        queue_obj = DummyObject('east osceola')
        self.queues._add_item(lock_ids, queue_obj)
        self.assertTrue(self.queues.full)  # full when full
        queue_obj = DummyObject('west osceola')
        self.queues._add_item(lock_ids, queue_obj)
        self.assertTrue(self.queues.full)  # full when over full


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
        self.assertEqual(get_case_ids(form), ["test-case"])


def create_form_with_missing_xml(domain_name):
    form = submit_form_locally(TEST_FORM, domain_name).xform
    form = FormAccessors(domain_name).get_form(form.form_id)
    blobs = get_blob_db()
    with mock.patch.object(blobs.metadb, "delete"):
        if isinstance(form, XFormInstance):
            # couch
            form.delete_attachment("form.xml")
            assert form.get_xml() is None, form.get_xml()
        else:
            # sql
            blobs.delete(form.get_attachment_meta("form.xml").key)
            try:
                form.get_xml()
                assert False, "expected BlobNotFound exception"
            except BlobNotFound:
                pass
    return form


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

    def __ne__(self, other):
        return not (self == other)

    __hash__ = None


class DummyObject(object):
    def __init__(self, id=None):
        self.id = id or uuid.uuid4().hex

    def __repr__(self):
        return "DummyObject<id={}>".format(self.id)


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
