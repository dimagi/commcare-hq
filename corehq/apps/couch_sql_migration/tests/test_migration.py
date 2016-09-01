import uuid

from django.core.management import call_command
from django.test import TestCase

from corehq.apps.couch_sql_migration.couchsqlmigration import get_diff_db
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.apps.tzmigration import TimezoneMigrationProgress
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import clear_local_domain_sql_backend_override
from corehq.util.test_utils import create_and_save_a_form, create_and_save_a_case


class MigrationTestCase(TestCase):

    def setUp(self):
        super(MigrationTestCase, self).setUp()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain_name = uuid.uuid4().hex
        self.domain = create_domain(self.domain_name)
        # all new domains are set complete when they are created
        TimezoneMigrationProgress.objects.filter(domain=self.domain_name).delete()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain.delete()

    def test_basic_form_migration(self):
        create_and_save_a_form(self.domain_name)
        self.assertFalse(should_use_sql_backend(self.domain_name))
        self.assertEqual(1, len(self._get_form_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self._compare_diffs([])

    def test_archived_form_migration(self):
        form = create_and_save_a_form(self.domain_name)
        form.archive('user1')
        self.assertFalse(should_use_sql_backend(self.domain_name))
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
        self.assertFalse(should_use_sql_backend(self.domain_name))
        self.assertEqual(1, len(self._get_form_ids('XFormError')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids('XFormError')))
        self._compare_diffs([])

    def test_duplicate_form_migration(self):
        with open('corehq/ex-submodules/couchforms/tests/data/posts/duplicate.xml') as f:
            duplicate_form_xml = f.read()

        submit_form_locally(duplicate_form_xml, self.domain_name)
        submit_form_locally(duplicate_form_xml, self.domain_name)

        self.assertFalse(should_use_sql_backend(self.domain_name))
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_form_ids()))
        self.assertEqual(1, len(self._get_form_ids('XFormDuplicate')))
        self._compare_diffs([])

    def test_basic_case_migration(self):
        create_and_save_a_case(self.domain_name, case_id=uuid.uuid4().hex, case_name='test case')
        self.assertEqual(1, len(self._get_case_ids()))
        self._do_migration_and_assert_flags(self.domain_name)
        self.assertEqual(1, len(self._get_case_ids()))
        self._compare_diffs([])

    def test_commit(self):
        self._do_migration_and_assert_flags(self.domain_name)
        clear_local_domain_sql_backend_override(self.domain_name)
        call_command('migrate_domain_from_couch_to_sql', self.domain_name, COMMIT=True, no_input=True)
        self.assertTrue(Domain.get_by_name(self.domain_name).use_sql_backend)

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
