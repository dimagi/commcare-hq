from django.core.management import call_command
from django.test import TestCase, override_settings

from custom.enikshay.nikshay_datamigration.tests.utils import NikshayMigrationMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestDeleteMigratedCases(NikshayMigrationMixin, TestCase):

    def test_deletion(self):
        self.outcome.HIVStatus = None
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain)
        assert len(self.case_accessor.get_case_ids_in_domain(type='person')) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='occurrence')) == 1
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        assert len(episode_case_ids) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')) == 1

        call_command('delete_migrated_cases', self.domain, *episode_case_ids)

        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='person'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='occurrence'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='episode'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral'), [])
