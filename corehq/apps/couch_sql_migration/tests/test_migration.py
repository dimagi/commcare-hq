import uuid
from django.core.management import call_command
from django.test import TestCase
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.test_utils import create_and_save_a_form, create_and_save_a_case


class MigrationTestCase(TestCase):

    def setUp(self):
        super(MigrationTestCase, self).setUp()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        self.domain = uuid.uuid4().hex

    def test_basic_form_migration(self):
        create_and_save_a_form(self.domain)
        self.assertFalse(should_use_sql_backend(self.domain))
        self.assertEqual(1, len(FormAccessors(domain=self.domain).get_all_form_ids_in_domain()))
        self._do_migration_and_assert_flags(self.domain)
        self.assertEqual(1, len(FormAccessors(domain=self.domain).get_all_form_ids_in_domain()))
        # todo: verify form properties?

    def test_basic_case_migration(self):
        create_and_save_a_case(self.domain, case_id=uuid.uuid4().hex, case_name='test case')
        self.assertEqual(1, len(CaseAccessors(domain=self.domain).get_case_ids_in_domain()))
        self._do_migration_and_assert_flags(self.domain)
        self.assertEqual(1, len(CaseAccessors(domain=self.domain).get_case_ids_in_domain()))
        # todo: verify properties?

    def _do_migration_and_assert_flags(self, domain):
        self.assertFalse(should_use_sql_backend(domain))
        call_command('migrate_domain_from_couch_to_sql', domain, MIGRATE=True)
        self.assertTrue(should_use_sql_backend(domain))
