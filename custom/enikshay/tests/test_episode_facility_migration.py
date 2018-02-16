from __future__ import absolute_import
from django.test import TestCase, override_settings
from casexml.apps.case.mock import CaseStructure

from custom.enikshay.tests.utils import ENikshayCaseStructureMixin

from custom.enikshay.model_migration_sets.episode_facility_id_migration import EpisodeFacilityIDMigration


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestEpisodeFacilityIDMigration(ENikshayCaseStructureMixin, TestCase):

    def _create_cases(self, episode_type='confirmed_tb',
                      treatment_initiated=None,
                      episode_pending_registration='yes'):
        self.person.attrs['update']['current_episode_type'] = episode_type
        self.episode.attrs['update']['episode_type'] = episode_type

        self.episode.attrs['update']['treatment_initiated'] = treatment_initiated
        self.episode.attrs['update']['episode_pending_registration'] = episode_pending_registration

        self.cases = self.create_case_structure()
        self.episode_case = self.cases[self.episode_id]
        self.person_case = self.cases[self.person_id]
        self.updater = EpisodeFacilityIDMigration(self.domain, self.episode_case)

    def _update_person(self, update):
        self.person_case = self._update_case(self.person_id, update)

    def _update_episode(self, update):
        self.episode_case = self._update_case(self.episode_id, update)
        self.updater = EpisodeFacilityIDMigration(self.domain, self.episode_case)

    def _update_case(self, case_id, update):
        return self.factory.create_or_update_case(
            CaseStructure(
                case_id=case_id,
                attrs={
                    'create': False,
                    "update": update
                }
            )
        )[0]

    def test_get_diagnosing_facility_id_simple(self):
        self._create_cases()
        self.assertEqual(self.updater.diagnosing_facility_id, self.person_case.owner_id)

    def test_get_diagnosing_facility_id_many_updates(self):
        self._create_cases(episode_type='presumptive_tb')
        self._update_person({'owner_id': 'old_owner'})

        self._update_person({'boop': 'barp'})
        self._update_person({'owner_id': 'new_owner'})
        self._update_person({'current_episode_type': 'confirmed_tb'})
        self._update_person({'owner_id': 'newer_owner'})

        self.assertEqual(self.updater.diagnosing_facility_id, 'new_owner')

    def test_get_treatment_initiating_facility_id(self):
        self._create_cases(treatment_initiated='yes_phi', episode_pending_registration='yes')

        self._update_person({'owner_id': "new_owner"})
        self._update_episode({'episode_pending_registration': "no"})
        self._update_person({'owner_id': "newer_owner"})

        self.assertEqual(self.updater.treatment_initiating_facility_id, 'new_owner')

    def test_get_json(self):
        self._create_cases(episode_type='presumptive_tb')
        self.assertDictEqual(
            self.updater.update_json(), {}
        )

        self._update_person({'owner_id': "new_owner"})
        self._update_episode({'episode_pending_registration': "no"})
        self._update_episode({'treatment_initiated': "yes_phi"})
        self._update_person({'owner_id': "newer_owner"})
        self._update_person({'current_episode_type': 'confirmed_tb'})
        self._update_episode({'episode_type': 'confirmed_tb'})

        self.assertDictEqual(
            self.updater.update_json(),
            {
                'diagnosing_facility_id': 'newer_owner',
                'treatment_initiating_facility_id': 'new_owner',
                'facility_id_migration_v2_complete': 'true',
            }
        )

    def test_should_update(self):
        self._create_cases(episode_type='presumptive_tb')
        self.assertFalse(self.updater.should_update)

        self._update_episode({'episode_pending_registration': "no"})
        self._update_episode({'episode_type': "confirmed_tb"})
        self.assertTrue(self.updater.should_update)

        self._update_episode({'treatment_initiating_facility_id': "abc"})
        self._update_episode({'diagnosing_facility_id': ""})
        self.assertTrue(self.updater.should_update)

        self._update_episode({'treatment_initiating_facility_id': "abc"})
        self._update_episode({'diagnosing_facility_id': "abc"})
        self.assertFalse(self.updater.should_update)

        self._update_episode({'treatment_initiating_facility_id': ""})
        self._update_episode({'diagnosing_facility_id': ""})
        self._update_episode({'facility_id_migration_v2_complete': "true"})
        self.assertFalse(self.updater.should_update)
