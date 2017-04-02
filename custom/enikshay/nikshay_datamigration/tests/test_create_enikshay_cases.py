from collections import OrderedDict
from datetime import datetime

from django.core.management import call_command
from django.test import TestCase, override_settings

from mock import patch

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from casexml.apps.case.sharedmodels import CommCareCaseIndex

from custom.enikshay.nikshay_datamigration.tests.utils import NikshayMigrationMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestCreateEnikshayCases(NikshayMigrationMixin, TestCase):

    @patch('custom.enikshay.nikshay_datamigration.factory.datetime')
    def test_case_creation(self, mock_datetime):
        mock_datetime.utcnow.return_value = datetime(2016, 9, 8, 1, 2, 3, 4123)
        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(
            OrderedDict([
                ('aadhaar_number', '867386000000'),
                ('age', '18'),
                ('age_entered', '18'),
                ('current_address', 'Cambridge MA'),
                ('current_episode_type', 'confirmed_tb'),
                ('current_patient_type_choice', 'treatment_after_lfu'),
                ('dataset', 'real'),
                ('dob', '{}-07-01'.format(datetime.utcnow().year - 18)),
                ('dob_known', 'no'),
                ('first_name', 'A B'),
                ('has_open_tests', 'no'),
                ('hiv_status', 'non_reactive'),
                ('is_active', 'yes'),
                ('last_name', 'C'),
                ('migration_created_case', 'true'),
                ('migration_created_from_record', 'MH-ABD-05-16-0001'),
                ('person_id', 'NIK-MH-ABD-05-16-0001'),
                ('phi', 'PHI'),
                ('phi_assigned_to', self.phi.location_id),
                ('phone_number', '5432109876'),
                ('secondary_contact_name_address', 'Secondary name, Secondary address'),
                ('secondary_contact_phone_number', '1234567890'),
                ('sex', 'male'),
                ('tu_choice', self.tu.location_id),
            ]),
            person_case.dynamic_case_properties()
        )
        self.assertEqual('MH-ABD-05-16-0001', person_case.external_id)
        self.assertEqual('A B C', person_case.name)
        self.assertEqual(self.phi.location_id, person_case.owner_id)
        self.assertFalse(person_case.closed)
        # make sure the case is only created/modified by a single form
        self.assertEqual(1, len(person_case.xform_ids))

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertEqual(
            OrderedDict([
                ('current_episode_type', 'confirmed_tb'),
                ('ihv_date', '2016-12-25'),
                ('initial_home_visit_status', 'completed'),
                ('migration_created_case', 'true'),
                ('migration_created_from_record', 'MH-ABD-05-16-0001'),
                ('occurrence_episode_count', '1'),
                ('occurrence_id', '20160908010203004'),
            ]),
            occurrence_case.dynamic_case_properties()
        )
        self.assertEqual('Occurrence #1', occurrence_case.name)
        self.assertEqual(len(occurrence_case.indices), 1)
        self._assertIndexEqual(
            CommCareCaseIndex(
                identifier='host',
                referenced_type='person',
                referenced_id=person_case.get_id,
                relationship='extension',
            ),
            occurrence_case.indices[0]
        )
        self.assertEqual('-', occurrence_case.owner_id)
        self.assertFalse(occurrence_case.closed)
        # make sure the case is only created/modified by a single form
        self.assertEqual(1, len(occurrence_case.xform_ids))

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(
            OrderedDict([
                ('adherence_schedule_date_start', '2016-12-22'),
                ('adherence_schedule_id', 'schedule_mwf'),
                ('date_of_diagnosis', '2016-12-13'),
                ('date_of_mo_signature', '2016-12-23'),
                ('disease_classification', 'extra_pulmonary'),
                ('dots_99_enabled', 'false'),
                ('episode_id', '20160908010203004'),
                ('episode_pending_registration', 'no'),
                ('episode_type', 'confirmed_tb'),
                ('migration_created_case', 'true'),
                ('migration_created_from_record', 'MH-ABD-05-16-0001'),
                ('nikshay_id', 'MH-ABD-05-16-0001'),
                ('occupation', 'physical_mathematical_and_engineering'),
                ('patient_type_choice', 'treatment_after_lfu'),
                ('site_choice', 'abdominal'),
                ('transfer_in', ''),
                ('treatment_card_completed_date', '2016-12-13'),
                ('treatment_initiated', 'yes_phi'),
                ('treatment_initiation_date', '2016-12-22'),
                ('treatment_supporter_designation', 'health_worker'),
                ('treatment_supporter_first_name', 'Bubble'),
                ('treatment_supporter_last_name', 'Bubbles'),
                ('treatment_supporter_mobile_number', '9876543210'),
            ]),
            episode_case.dynamic_case_properties()
        )
        self.assertEqual('Episode #1: Confirmed TB (Patient)', episode_case.name)
        self.assertEqual(datetime(2016, 12, 13), episode_case.opened_on)
        self.assertEqual('-', episode_case.owner_id)
        self.assertFalse(episode_case.closed)
        self.assertEqual(len(episode_case.indices), 1)
        self._assertIndexEqual(
            CommCareCaseIndex(
                identifier='host',
                referenced_type='occurrence',
                referenced_id=occurrence_case.get_id,
                relationship='extension',
            ),
            episode_case.indices[0]
        )
        # make sure the case is only created/modified by a single form
        self.assertEqual(1, len(episode_case.xform_ids))

        drtb_hiv_referral_case_ids = self.case_accessor.get_case_ids_in_domain(type='drtb_hiv_referral')
        self.assertEqual(0, len(drtb_hiv_referral_case_ids))

    def test_drtb_hiv_referral(self):
        self.outcome.HIVStatus = None
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))

        drtb_hiv_referral_case_ids = self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')
        self.assertEqual(1, len(drtb_hiv_referral_case_ids))
        drtb_hiv_referral_case = self.case_accessor.get_case(drtb_hiv_referral_case_ids[0])
        self.assertEqual('A B C', drtb_hiv_referral_case.name)
        self.assertEqual(self.drtb_hiv.location_id, drtb_hiv_referral_case.owner_id)
        self.assertEqual(
            OrderedDict([
                ('migration_created_case', 'true'),
                ('migration_created_from_record', 'MH-ABD-05-16-0001'),
            ]),
            drtb_hiv_referral_case.dynamic_case_properties()
        )

    def test_case_update(self):
        self.outcome.HIVStatus = None
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain)

        new_addhaar_number = 867386000001
        new_pname = 'Bubbles'
        self.patient_detail.paadharno = new_addhaar_number
        self.patient_detail.pname = new_pname
        self.patient_detail.cvisitedDate1 = '2016-12-31 00:00:00.000'
        self.patient_detail.dcpulmunory = 'N'
        self.patient_detail.save()
        self.outcome.HIVStatus = 'Pos'
        self.outcome.save()

        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.name, new_pname)
        self.assertEqual(person_case.dynamic_case_properties()['aadhaar_number'], str(new_addhaar_number))
        self.assertEqual(person_case.dynamic_case_properties()['hiv_status'], 'reactive')

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertEqual(occurrence_case.dynamic_case_properties()['ihv_date'], '2016-12-31')

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(episode_case.dynamic_case_properties()['disease_classification'], 'extra_pulmonary')

        drtb_hiv_referral_case_ids = self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')
        self.assertEqual(1, len(drtb_hiv_referral_case_ids))
        drtb_hiv_referral_case = self.case_accessor.get_case(drtb_hiv_referral_case_ids[0])
        self.assertEqual(drtb_hiv_referral_case.name, new_pname)

    def test_location_not_found(self):
        self.phi.delete()
        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertEqual(person_case.dynamic_case_properties()['archive_reason'], 'migration_location_not_found')
        self.assertEqual(person_case.dynamic_case_properties()['migration_error'], 'location_not_found')
        self.assertEqual(person_case.dynamic_case_properties()['migration_error_details'], 'MH-ABD-1-2')

    def test_outcome_cured(self):
        self.outcome.HIVStatus = 'Unknown'
        self.outcome.Outcome = '1'
        self.outcome.OutcomeDate = '2/01/2017'
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertFalse(person_case.closed)
        self.assertEqual(person_case.dynamic_case_properties()['is_active'], 'no')

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertTrue(occurrence_case.closed)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertTrue(episode_case.closed)
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome'], 'cured')
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome_date'], '2017-01-02')

        drtb_hiv_referral_case_ids = self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')
        self.assertEqual(0, len(drtb_hiv_referral_case_ids))

    def test_outcome_died(self):
        self.outcome.HIVStatus = 'Unknown'
        self.outcome.Outcome = '3'
        self.outcome.OutcomeDate = '2-01-2017'
        self.outcome.save()
        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertTrue(person_case.closed)
        self.assertEqual(person_case.dynamic_case_properties()['is_active'], 'no')

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertTrue(occurrence_case.closed)

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertTrue(episode_case.closed)
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome'], 'died')
        self.assertEqual(episode_case.dynamic_case_properties()['treatment_outcome_date'], '2017-01-02')

        drtb_hiv_referral_case_ids = self.case_accessor.get_case_ids_in_domain(type='drtb-hiv-referral')
        self.assertEqual(0, len(drtb_hiv_referral_case_ids))

    def _assertIndexEqual(self, index_1, index_2):
        self.assertEqual(index_1.identifier, index_2.identifier)
        self.assertEqual(index_1.referenced_type, index_2.referenced_type)
        self.assertEqual(index_1.referenced_id, index_2.referenced_id)
        self.assertEqual(index_1.relationship, index_2.relationship)
