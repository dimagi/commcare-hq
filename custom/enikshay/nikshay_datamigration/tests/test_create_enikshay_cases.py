from collections import OrderedDict
from datetime import date, datetime

from django.core.management import call_command
from django.test import TestCase

from mock import patch

from casexml.apps.case.const import ARCHIVED_CASE_OWNER_ID
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from custom.enikshay.nikshay_datamigration.models import Outcome, PatientDetail
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin


class TestCreateEnikshayCases(ENikshayLocationStructureMixin, TestCase):
    def setUp(self):
        self.domain = "enikshay-test-domain"
        super(TestCreateEnikshayCases, self).setUp()
        self.patient_detail = PatientDetail.objects.create(
            PregId='MH-ABD-05-16-0001',
            Tbunitcode=1,
            pname='A B C',
            pgender='M',
            page=18,
            poccupation='4',
            paadharno=867386000000,
            paddress='Cambridge MA',
            pmob='5432109876',
            pregdate1=date(2016, 12, 13),
            cname='Secondary name',
            caddress='Secondary address',
            cmob='1234567890',
            dcpulmunory='N',
            dcexpulmunory='3',
            dotname='Bubble Bubbles',
            dotmob='9876543210',
            dotpType=1,
            PHI=2,
            atbtreatment='',
            Ptype=4,
            pcategory=4,
            cvisitedDate1='2016-12-25 00:00:00.000',
            InitiationDate1='2016-12-22 16:06:47.726',
            dotmosignDate1='2016-12-23 00:00:00.000',
        )
        self.outcome = Outcome.objects.create(
            PatientId=self.patient_detail,
            HIVStatus='Neg',
            loginDate=datetime(2016, 1, 2),
        )
        # Household.objects.create(
        #     PatientID=patient_detail,
        # )
        self.case_accessor = CaseAccessors(self.domain)

    def tearDown(self):
        Outcome.objects.all().delete()
        # Household.objects.all().delete()
        PatientDetail.objects.all().delete()

        super(TestCreateEnikshayCases, self).tearDown()

    @run_with_all_backends
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
                ('contact_phone_number', '5432109876'),
                ('current_address', 'Cambridge MA'),
                ('current_address_district_choice', self.dto.location_id),
                ('current_address_state_choice', self.sto.location_id),
                ('dob', '{}-07-01'.format(datetime.utcnow().year - 18)),
                ('dob_known', 'no'),
                ('first_name', 'A B'),
                ('hiv_status', 'non_reactive'),
                ('last_name', 'C'),
                ('migration_created_case', 'true'),
                ('person_id', 'N-MH-ABD-05-16-0001'),
                ('phi', 'PHI'),
                ('secondary_contact_name_address', 'Secondary name, Secondary address'),
                ('secondary_contact_phone_number', '1234567890'),
                ('sex', 'male'),
                ('tu_choice', 'TU'),
            ]),
            person_case.dynamic_case_properties()
        )
        self.assertEqual('MH-ABD-05-16-0001', person_case.external_id)
        self.assertEqual('A B C', person_case.name)
        self.assertEqual(self.phi.location_id, person_case.owner_id)
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
        # make sure the case is only created/modified by a single form
        self.assertEqual(1, len(occurrence_case.xform_ids))

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(
            OrderedDict([
                ('adherence_schedule_date_start', '2016-12-22'),
                ('date_of_diagnosis', '2016-12-13'),
                ('date_of_mo_signature', '2016-12-23'),
                ('disease_classification', 'extra_pulmonary'),
                ('dots_99_enabled', 'false'),
                ('episode_pending_registration', 'no'),
                ('episode_type', 'confirmed_tb'),
                ('migration_created_case', 'true'),
                ('nikshay_id', 'MH-ABD-05-16-0001'),
                ('occupation', 'physical_mathematical_and_engineering'),
                ('patient_type_choice', 'treatment_after_lfu'),
                ('site_choice', 'abdominal'),
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

    @run_with_all_backends
    def test_case_update(self):
        call_command('create_enikshay_cases', self.domain)

        new_addhaar_number = 867386000001
        self.patient_detail.paadharno = new_addhaar_number
        self.patient_detail.cvisitedDate1 = '2016-12-31 00:00:00.000'
        self.patient_detail.dcpulmunory = 'N'
        self.patient_detail.save()
        self.outcome.HIVStatus = 'Pos'
        self.outcome.save()

        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
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

    @run_with_all_backends
    def test_location_not_found(self):
        self.phi.delete()
        call_command('create_enikshay_cases', self.domain)

        person_case_ids = self.case_accessor.get_case_ids_in_domain(type='person')
        self.assertEqual(1, len(person_case_ids))
        person_case = self.case_accessor.get_case(person_case_ids[0])
        self.assertEqual(person_case.owner_id, ARCHIVED_CASE_OWNER_ID)
        self.assertEqual(person_case.dynamic_case_properties()['archive_reason'], 'migration_location_not_found')
        self.assertEqual(person_case.dynamic_case_properties()['migration_error'], 'location_not_found')
        self.assertEqual(person_case.dynamic_case_properties()['migration_error_details'], 'MH-ABD-05-16')

    def _assertIndexEqual(self, index_1, index_2):
        self.assertEqual(index_1.identifier, index_2.identifier)
        self.assertEqual(index_1.referenced_type, index_2.referenced_type)
        self.assertEqual(index_1.referenced_id, index_2.referenced_id)
        self.assertEqual(index_1.relationship, index_2.relationship)
