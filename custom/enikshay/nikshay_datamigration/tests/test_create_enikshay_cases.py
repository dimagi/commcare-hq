from collections import OrderedDict
from datetime import date

from django.core.management import call_command
from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.nikshay_datamigration.models import Followup, Household, Outcome, PatientDetail


class TestCreateEnikshayCases(TestCase):

    def setUp(self):
        super(TestCreateEnikshayCases, self).setUp()

        patient_detail = PatientDetail.objects.create(
            PregId='MH-ABD-05-16-0001',
            pname='A B C',
            pgender='M',
            page=18,
            paadharno=867386000000,
            paddress='Cambridge MA',
            pmob='9987328695',
            pregdate1=date.today(),
            cmob='123',
            dcpulmunory='',
            dotpType=1,
            PHI=2,
            atbtreatment='',
            Ptype=3,
            pcategory=4,

        )
        Outcome.objects.create(
            PatientId=patient_detail,
            HIVStatus='negative',
        )
        Household.objects.create(
            PatientID=patient_detail,
        )
        for i in range(5):
            Followup.objects.create(
                id=i+1,
                PatientID=patient_detail,
            )

        self.domain = Domain(name='enikshay-test-domain')
        self.domain.save()

        loc_type = LocationType.objects.create(
            domain=self.domain.name,
            name='nik'
        )

        SQLLocation.objects.create(
            domain=self.domain.name,
            location_type=loc_type,
            metadata={
                'nikshay_code': 'MH-ABD-05-16',
            },
        )

        self.case_accessor = CaseAccessors(self.domain.name)

    def tearDown(self):
        Outcome.objects.all().delete()
        Followup.objects.all().delete()
        Household.objects.all().delete()
        PatientDetail.objects.all().delete()

        self.domain.delete()

        SQLLocation.objects.all().delete()
        LocationType.objects.all().delete()

        super(TestCreateEnikshayCases, self).tearDown()

    def test_case_properties(self):
        call_command('create_enikshay_cases', self.domain.name)

        self.assertEqual(
            ['MH-ABD-05-16-0001'],
            self.case_accessor.get_case_ids_in_domain(
                type='person'
            )
        )

        person_case = self.case_accessor.get_case('MH-ABD-05-16-0001')
        self.assertEqual(
            OrderedDict([
                ('aadhaar_number', '867386000000'),
                ('age', '18'),
                ('current_address', 'Cambridge MA'),
                ('first_name', 'A'),
                ('last_name', 'C'),
                ('middle_name', 'B'),
                ('migration_created_case', 'True'),
                ('mobile_number', '9987328695'),
                ('phi', '2'),
                ('sex', 'male'),
            ]),
            person_case.dynamic_case_properties()
        )

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        self.assertEqual(
            OrderedDict([
                ('hiv_status', 'negative'),
                ('migration_created_case', 'True'),
                ('nikshay_id', 'MH-ABD-05-16-0001'),
            ]),
            self.case_accessor.get_case(occurrence_case_ids[0]).dynamic_case_properties()
        )

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        self.assertEqual(
            OrderedDict([
                ('migration_created_case', 'True'),
                ('treatment_supporter_mobile_number', '123'),
            ]),
            self.case_accessor.get_case(episode_case_ids[0]).dynamic_case_properties()
        )

        test_case_ids = set(self.case_accessor.get_case_ids_in_domain(type='test'))
        self.assertEqual(5, len(test_case_ids))
        # for test_case_id in test_case_ids:
        self.assertSetEqual(
            set([
                self.case_accessor.get_case(test_case_id).dynamic_case_properties()
                for test_case_id in test_case_ids
            ]),
            set([
                OrderedDict([
                    ('date_tested', ''),
                    ('migration_created_case', 'True'),
                    ('migration_followup_id', str(1)),
                ]),
                OrderedDict([
                    ('date_tested', ''),
                    ('migration_created_case', 'True'),
                    ('migration_followup_id', str(2)),
                ]),
                OrderedDict([
                    ('date_tested', ''),
                    ('migration_created_case', 'True'),
                    ('migration_followup_id', str(3)),
                ]),
                OrderedDict([
                    ('date_tested', ''),
                    ('migration_created_case', 'True'),
                    ('migration_followup_id', str(4)),
                ]),
                OrderedDict([
                    ('date_tested', ''),
                    ('migration_created_case', 'True'),
                    ('migration_followup_id', str(5)),
                ]),
            ])
        )
