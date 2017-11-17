from __future__ import absolute_import
from django.core.management import call_command
from django.test import TestCase, override_settings

from custom.enikshay.nikshay_datamigration.tests.utils import NikshayMigrationMixin
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestDeleteMigratedCases(ENikshayCaseStructureMixin, NikshayMigrationMixin, TestCase):

    def test_deletion_open_cases(self):
        self.outcome.HIVStatus = None
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain, 'test_migration')
        assert len(self.case_accessor.get_case_ids_in_domain(type='person')) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='occurrence')) == 1
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        assert len(episode_case_ids) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')) == 1

        call_command('delete_migrated_cases', self.domain, 'episode', episode_case_ids[0], noinput=True)

        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='person'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='occurrence'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='episode'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral'), [])

    def test_deletion_closed_cases(self):
        self.outcome.Outcome = '1'
        self.outcome.OutcomeDate = '2/01/2017'
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain, 'test_migration')
        assert len(self.case_accessor.get_case_ids_in_domain(type='person')) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='occurrence')) == 1
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        assert len(episode_case_ids) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')) == 0

        call_command('delete_migrated_cases', self.domain, 'episode', episode_case_ids[0], noinput=True)

        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='person'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='occurrence'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='episode'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral'), [])

    def test_deletion_by_person_case_id(self):
        self.outcome.HIVStatus = None
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain, 'test_migration')
        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        assert len(person_case_ids) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='occurrence')) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='episode')) == 1
        assert len(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')) == 1

        call_command('delete_migrated_cases', self.domain, 'person', person_case_ids[0], noinput=True)

        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='person'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='occurrence'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='episode'), [])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral'), [])

    def test_other_cases_not_deleted(self):
        self.outcome.HIVStatus = None
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain, 'test_migration')
        self.create_case_structure()
        assert len(self.case_accessor.get_case_ids_in_domain(type='person')) == 2
        assert len(self.case_accessor.get_case_ids_in_domain(type='occurrence')) == 2
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        assert len(episode_case_ids) == 2
        assert len(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')) == 1

        call_command(
            'delete_migrated_cases',
            self.domain, 'episode',
            [episode_id for episode_id in episode_case_ids if episode_id != self.episode_id][0],
            noinput=True
        )

        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='person'), [self.person_id])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='occurrence'), [self.occurrence_id])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='episode'), [self.episode_id])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral'), [])

    def test_nonmigrated_case_not_deleted(self):
        self.create_case_structure()

        with self.assertRaises(AssertionError):
            call_command('delete_migrated_cases', self.domain, 'episode', self.episode_id, noinput=True)

        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='person'), [self.person_id])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='occurrence'), [self.occurrence_id])
        self.assertListEqual(self.case_accessor.get_case_ids_in_domain(type='episode'), [self.episode_id])
