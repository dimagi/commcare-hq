from collections import OrderedDict
from datetime import date

from django.core.management import call_command
from django.test import TestCase

from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.nikshay_datamigration.models import Followup, Outcome, PatientDetail


class TestCreateEnikshayCases(TestCase):

    def setUp(self):
        super(TestCreateEnikshayCases, self).setUp()

        patient_detail = PatientDetail.objects.create(
            Tbunitcode=1,
            PregId='MH-ABD-05-16-0001',
            scode='MA',
            Dtocode='Middlesex',
            pname='A B C',
            pgender='M',
            page=18,
            paadharno=867386000000,
            paddress='Cambridge MA',
            pmob='9987328695',
            pregdate1=date(2016, 12, 13),
            cmob='123',
            dcpulmunory='',
            dotpType=1,
            PHI=2,
            atbtreatment='',
            Ptype=3,
            pcategory=4,
            cname='Secondary name',
            caddress='Secondary address',

        )
        Outcome.objects.create(
            PatientId=patient_detail,
            HIVStatus='negative',
        )
        # Household.objects.create(
        #     PatientID=patient_detail,
        # )
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
        # Household.objects.all().delete()
        PatientDetail.objects.all().delete()

        self.domain.delete()

        SQLLocation.objects.all().delete()
        LocationType.objects.all().delete()

        super(TestCreateEnikshayCases, self).tearDown()

    def test_case_properties(self):
        call_command('create_enikshay_cases', self.domain.name)

        # self.assertEqual(
        #     ['MH-ABD-05-16-0001'],
        #     self.case_accessor.get_case_ids_in_domain(
        #         type='person'
        #     )
        # )

        person_case = self.case_accessor.get_case(self.case_accessor.get_case_ids_in_domain(type='person')[0])
        self.assertEqual(
            OrderedDict([
                ('aadhaar_number', '867386000000'),
                ('age_entered', '18'),
                ('current_address', 'Cambridge MA'),
                ('current_address_district_choice', 'Middlesex'),
                ('current_address_state_choice', 'MA'),
                ('first_name', 'A'),
                ('last_name', 'C'),
                ('middle_name', 'B'),
                ('migration_created_case', 'True'),
                ('nikshay_id', 'MH-ABD-05-16-0001'),
                ('permanent_address_district_choice', 'Middlesex'),
                ('permanent_address_state_choice', 'MA'),
                ('phi', '2'),
                ('secondary_contact_name_address', 'Secondary name, Secondary address'),
                ('sex', 'male'),
                ('tu_choice', '1'),
            ]),
            person_case.dynamic_case_properties()
        )
        self.assertEqual('A B C', person_case.name)

        occurrence_case_ids = self.case_accessor.get_case_ids_in_domain(type='occurrence')
        self.assertEqual(1, len(occurrence_case_ids))
        occurrence_case = self.case_accessor.get_case(occurrence_case_ids[0])
        self.assertEqual(
            OrderedDict([
                ('hiv_status', 'negative'),
                ('migration_created_case', 'True'),
                ('nikshay_id', 'MH-ABD-05-16-0001'),
            ]),
            occurrence_case.dynamic_case_properties()
        )
        self.assertItemsEqual(
            [CommCareCaseIndex(
                identifier='host',
                referenced_type='person',
                referenced_id=person_case.get_id,
                relationship='extension',
            )],
            occurrence_case.indices
        )

        episode_case_ids = self.case_accessor.get_case_ids_in_domain(type='episode')
        self.assertEqual(1, len(episode_case_ids))
        episode_case = self.case_accessor.get_case(episode_case_ids[0])
        self.assertEqual(
            OrderedDict([
                ('date_reported', '2016-12-13'),
                ('disease_classification', ''),
                ('migration_created_case', 'True'),
                ('treatment_supporter_mobile_number', '123'),
            ]),
            episode_case.dynamic_case_properties()
        )
        self.assertItemsEqual(
            [CommCareCaseIndex(
                identifier='host',
                referenced_type='occurrence',
                referenced_id=occurrence_case.get_id,
                relationship='extension',
            )],
            episode_case.indices
        )

        test_case_ids = set(self.case_accessor.get_case_ids_in_domain(type='test'))
        self.assertEqual(5, len(test_case_ids))
        test_cases = [
            self.case_accessor.get_case(test_case_id)
            for test_case_id in test_case_ids
        ]
        self.assertItemsEqual(
            [
                test_case.dynamic_case_properties()
                for test_case in test_cases
            ],
            [
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
            ]
        )
        for test_case in test_cases:
            self.assertItemsEqual(
                [CommCareCaseIndex(
                    identifier='host',
                    referenced_type='occurrence',
                    referenced_id=occurrence_case.get_id,
                    relationship='extension',
                )],
                test_case.indices
            )
