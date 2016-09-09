import uuid

from datetime import datetime

from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from casexml.apps.case.mock import CaseBlock
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.couch_sql_migration.couchsqlmigration import get_diff_db
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.receiverwrapper.exceptions import LocalSubmissionError
from corehq.apps.tzmigration.models import TimezoneMigrationProgress
from corehq.blobs import get_blob_db
from corehq.blobs.mixin import BlobMixin
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors, LedgerAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import clear_local_domain_sql_backend_override
from corehq.util.test_utils import create_and_save_a_form, create_and_save_a_case, set_parent_case, trap_extra_setup
from couchforms.models import XFormInstance


class BaseMigrationTestCase(TestCase):
    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
            self.s3db = TemporaryS3BlobDB(config)
            assert get_blob_db() is self.s3db, (get_blob_db(), self.s3db)

        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain_name = uuid.uuid4().hex
        self.domain = create_domain(self.domain_name)
        # all new domains are set complete when they are created
        TimezoneMigrationProgress.objects.filter(domain=self.domain_name).delete()
        self.assertFalse(should_use_sql_backend(self.domain_name))

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain.delete()

    def _do_migration_and_assert_flags(self, domain):
        self.assertFalse(should_use_sql_backend(domain))
        call_command('migrate_domain_from_couch_to_sql', domain, MIGRATE=True, no_input=True)
        self.assertTrue(should_use_sql_backend(domain))

    def _compare_diffs(self, expected):
        diffs = get_diff_db(self.domain_name).get_diffs()
        json_diffs = [(diff.kind, diff.json_diff) for diff in diffs]
        self.assertEqual(expected, json_diffs)

    def _get_form_ids(self, doc_type='XFormInstance'):
        return FormAccessors(domain=self.domain_name).get_all_form_ids_in_domain(doc_type=doc_type)

    def _get_case_ids(self):
        return CaseAccessors(domain=self.domain_name).get_case_ids_in_domain()


class MigrationTestCase(BaseMigrationTestCase):
    def test_basic_form_migration(self):
        create_and_save_a_form(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._compare_diffs([])

    def test_basic_form_migration_with_timezones(self):
        with open('corehq/apps/tzmigration/tests/data/form.xml') as f:
            duplicate_form_xml = f.read()

        with override_settings(PHONE_TIMEZONES_HAVE_BEEN_PROCESSED=False,
                               PHONE_TIMEZONES_SHOULD_BE_PROCESSED=False):
            submit_form_locally(duplicate_form_xml, self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
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

    def test_duplicate_form_migration(self):
        with open('corehq/ex-submodules/couchforms/tests/data/posts/duplicate.xml') as f:
            duplicate_form_xml = f.read()

        submit_form_locally(duplicate_form_xml, self.domain_name)
        submit_form_locally(duplicate_form_xml, self.domain_name)

        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self._compare_diffs([])

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
        ).as_string()
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
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain_name, form_id=form_id)

        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDeprecated')))
        self.assertEqual(1, len(self._get_case_ids()))

        self._do_migration_and_assert_flags(self.domain_name)

        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDeprecated')))
        self.assertEqual(1, len(self._get_case_ids()))
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

    def test_submission_error_log_migration(self):
        try:
            submit_form_locally("To be an XForm or NOT to be an xform/>", self.domain_name)
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
            <n0:case case_id="case-123" user_id="user-abc" date_modified="{date}" xmlns:n0="http://commcarehq.org/case/transaction/v2">
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
            ).as_string(),
            self.domain_name
        )

        submit_case_blocks(
            CaseBlock(
                case_id,
                update={'name': 'test21'},
            ).as_string(),
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

    def test_commit(self):
        self._do_migration_and_assert_flags(self.domain_name)
        clear_local_domain_sql_backend_override(self.domain_name)
        call_command('migrate_domain_from_couch_to_sql', self.domain_name, COMMIT=True, no_input=True)
        self.assertTrue(Domain.get_by_name(self.domain_name).use_sql_backend)


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

    def _set_balance(self, balance, case_id, product_id):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        return self._submit_ledgers([
            get_single_balance_block(case_id, product_id, balance)
        ])

    def test_migrate_ledgers(self):
        case_id = uuid.uuid4().hex
        create_and_save_a_case(self.domain_name, case_id=case_id, case_name="Simon's sweet shop")
        self._set_balance(100, case_id, self.liquorice._id)
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
