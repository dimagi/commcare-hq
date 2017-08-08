import random
import uuid
from datetime import datetime, date, timedelta

from django.test import TestCase, override_settings

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from custom.enikshay.const import PERSON_FIRST_NAME, PERSON_LAST_NAME, PRIMARY_PHONE_NUMBER, BACKUP_PHONE_NUMBER, \
    MERM_ID, TREATMENT_START_DATE, TREATMENT_SUPPORTER_FIRST_NAME, TREATMENT_SUPPORTER_LAST_NAME, \
    TREATMENT_SUPPORTER_PHONE, WEIGHT_BAND
from corehq.form_processor.tests.utils import FormProcessorTestUtils


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class MyAwesomeCase(TestCase):
    domain = "enikshay-test"

    @classmethod
    def setUpClass(cls):
        super(MyAwesomeCase, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()

    def setUp(self):
        super(MyAwesomeCase, self).setUp()

        domain = "enikshay-test"
        user_id = "whatever"
        person_id = str(uuid.uuid4())
        occurrence_id = str(uuid.uuid4())
        episode_id = str(uuid.uuid4())
        primary_phone_number = "0123456789"
        secondary_phone_number = "0999999999"
        treatment_supporter_phone = "066000666"

        factory = CaseFactory(domain=domain)

        person = CaseStructure(
            case_id=person_id,
            attrs={
                "case_type": "person",
                "user_id": user_id,
                "create": True,
                "owner_id": user_id,
                "update": {
                    'name': "Peregrine Took",
                    PERSON_FIRST_NAME: "Peregrine",
                    PERSON_LAST_NAME: "Took",
                    'aadhaar_number': "499118665246",
                    PRIMARY_PHONE_NUMBER: primary_phone_number,
                    BACKUP_PHONE_NUMBER: secondary_phone_number,
                    MERM_ID: "123456789",
                    'dob': "1987-08-15",
                    'age': '20',
                    'sex': 'male',
                    'current_address': 'Mr. Everest',
                    'secondary_contact_name_address': 'Mrs. Everestie',
                    'previous_tb_treatment': 'yes',
                    'nikshay_registered': "false",
                }
            },
        )

        occurrence = CaseStructure(
            case_id=occurrence_id,
            attrs={
                'create': True,
                'case_type': 'occurrence',
                "update": dict(
                    name="Occurrence #1",
                )
            },
            indices=[CaseIndex(
                person,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=person.attrs['case_type'],
            )],
        )

        episode = CaseStructure(
            case_id=episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": {
                    'date_of_diagnosis': '2016-01-01',
                    'default_adherence_confidence': 'high',
                    'disease_classification': 'extra_pulmonary',
                    'episode_type': 'confirmed_tb',
                    'hiv_status': 'reactive',
                    'name': 'Episode #1',
                    'occupation': 'engineer',
                    'opened_on': datetime(1989, 6, 11, 0, 0),
                    'patient_type_choice': 'treatment_after_lfu',
                    'person_name': 'Peregrine Took',
                    'site_choice': 'pleural_effusion',
                    'treatment_supporter_designation': 'ngo_volunteer',
                    TREATMENT_START_DATE: "2015-03-03",
                    'adherence_schedule_date_start': "2015-05-02",
                    TREATMENT_SUPPORTER_FIRST_NAME: "Gandalf",
                    TREATMENT_SUPPORTER_LAST_NAME: "The Grey",
                    TREATMENT_SUPPORTER_PHONE: treatment_supporter_phone,
                    WEIGHT_BAND: "adult_55-69"
                }
            },
            indices=[CaseIndex(
                occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=occurrence.attrs['case_type'],
            )],
        )

        # Create structure
        case_structure = {case.case_id: case for case in factory.create_or_update_cases([episode])}

        # Create some adherence dates with random types between start of plan and 6 months:

        day = 1
        start_date = date(2015, 5, 2)
        while day <= 180:
            this_date = start_date + timedelta(days=1)
            has_adherence = random.random() > 0.2
            if has_adherence:
                adherence_source = random.choice(['99DOTS', 'MERM', 'SOMETHING ELSE?'])
                adherence_value = random.choice([
                    "directly_observed_dose",
                    "unobserved_dose",
                    "missed_dose",
                    "self_administered_dose",
                ])

                factory.create_or_update_cases([
                    CaseStructure(
                        case_id=str(uuid.uuid4()),
                        attrs={
                            "case_type": "adherence",
                            "create": True,
                            "update": {
                                "name": str(this_date),
                                "adherence_value": adherence_value,
                                "adherence_source": adherence_source,
                                "adherence_date": str(this_date),
                                "person_name": "Pippin",
                                "adherence_confidence": "medium",
                                "shared_number_99_dots": False,
                            },
                        },
                        indices=[CaseIndex(
                            CaseStructure(case_id=episode_id, attrs={"create": False}),
                            identifier='host',
                            relationship=CASE_INDEX_EXTENSION,
                            related_type='episode',
                        )],
                        walk_related=False,
                    )
                ])
            day += 1

    def tearDown(self):
        super(MyAwesomeCase, self).tearDown()
        FormProcessorTestUtils.delete_all_cases()

    def test_awesome(self):
        self.assertEqual(True, True)
