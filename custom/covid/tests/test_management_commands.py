import logging
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from dimagi.utils.parsing import json_format_date

from corehq.apps.app_manager.util import enable_usercase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class CaseCommandsTest(TestCase):
    domain = 'cases-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()

        cls.domain_obj = create_domain(cls.domain)
        enable_usercase(cls.domain)

        cls.mobile_worker = CommCareUser.create(cls.domain, "username", "p@ssword123", None, None)
        cls.user_id = cls.mobile_worker.user_id

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        delete_all_users()
        super().tearDown()

    def test_invalid_username(self):
        with self.assertRaises(Exception):
            call_command('add_hq_user_id_to_case', self.domain, 'checkin', '--username=afakeuserthatdoesnotexist')

    def submit_case_block(self, create, case_id, **kwargs):
        return submit_case_blocks(
            [
                CaseBlock(
                    create=create,
                    case_id=case_id,
                    **kwargs
                ).as_text()
            ], domain=self.domain
        )

    def create_active_location(self, loc_id):
        location_type = LocationType.objects.create(
            domain=self.domain,
            name="Active location",
            administrative=True,
        )
        SQLLocation.objects.create(
            domain=self.domain, name='active', location_id=loc_id, location_type=location_type,
        )

    def create_checkin_case_with_hq_user_id(self):
        checkin_case_id = uuid.uuid4().hex
        hq_user_id = uuid.uuid4().hex
        self.submit_case_block(
            True, checkin_case_id, user_id=self.user_id, owner_id='owner_id', case_type='checkin',
            update={"hq_user_id": hq_user_id},
        )
        return checkin_case_id, hq_user_id

    def test_add_hq_user_id_to_case(self):
        username = normalize_username("mobile_worker", self.domain)
        new_mobile_worker = CommCareUser.create(self.domain, username, "123", None, None)
        user_id = new_mobile_worker.user_id
        new_mobile_worker.save()

        checkin_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, checkin_case_id, user_id=user_id, case_type='checkin',
            update={"username": new_mobile_worker.raw_username, "hq_user_id": None}
        )
        checkin_case_no_username_id = uuid.uuid4().hex
        self.submit_case_block(
            True, checkin_case_no_username_id, user_id=user_id, case_type='checkin', update={"hq_user_id": None}
        )
        lab_result_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, lab_result_case_id, user_id=user_id, case_type='lab_result',
            update={"username": new_mobile_worker.raw_username, "hq_user_id": None}
        )
        checkin_case = CommCareCase.objects.get_case(checkin_case_id, self.domain)
        self.assertEqual('', checkin_case.get_case_property('hq_user_id'))
        self.assertEqual(checkin_case.case_json["username"], 'mobile_worker')

        call_command('add_hq_user_id_to_case', self.domain, 'checkin')

        checkin_case = CommCareCase.objects.get_case(checkin_case_id, self.domain)
        checkin_case_no_username = CommCareCase.objects.get_case(checkin_case_no_username_id, self.domain)
        lab_result_case = CommCareCase.objects.get_case(lab_result_case_id, self.domain)
        self.assertEqual(checkin_case.get_case_property('hq_user_id'), user_id)
        self.assertEqual(checkin_case_no_username.case_json['hq_user_id'], '')
        self.assertEqual(lab_result_case.case_json['hq_user_id'], '')

    def test_update_case_index_relationship(self):
        patient_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_id, user_id=self.user_id, owner_id='owner1', case_type='patient',
        )

        lab_result_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, lab_result_case_id, user_id=self.user_id, owner_id='owner1', case_type='lab_result',
            index={'patient': ('patient', patient_case_id, 'child')}
        )

        lab_result_case = CommCareCase.objects.get_case(lab_result_case_id, self.domain)
        self.assertEqual(lab_result_case.indices[0].referenced_type, 'patient')
        self.assertEqual(lab_result_case.indices[0].relationship, 'child')

        quoted_lab_result_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, quoted_lab_result_case_id, user_id=self.user_id, owner_id='owner1', case_type='lab_result',
            index={'patient': ("'patient'", patient_case_id, 'child')}
        )

        call_command('update_case_index_relationship', self.domain, 'lab_result')

        lab_result_case = CommCareCase.objects.get_case(lab_result_case_id, self.domain)
        self.assertEqual(lab_result_case.indices[0].relationship, 'extension')
        self.assertEqual(lab_result_case.get_case_property('owner_id'), '-')

        quoted_lab_result_case = CommCareCase.objects.get_case(quoted_lab_result_case_id, self.domain)
        self.assertEqual(quoted_lab_result_case.indices[0].referenced_type, 'patient')
        self.assertEqual(quoted_lab_result_case.indices[0].relationship, 'extension')
        self.assertEqual(quoted_lab_result_case.get_case_property('owner_id'), '-')

    def test_update_case_index_relationship_with_location(self):
        location_type = LocationType.objects.create(
            domain=self.domain,
            name="Location",
        )
        SQLLocation.objects.create(
            domain=self.domain, name='traveler_loc', location_id='traveler_loc_id', location_type=location_type,
        )
        SQLLocation.objects.create(
            domain=self.domain, name='non_traveler_loc', location_id='non_traveler_loc_id',
            location_type=location_type,
        )
        patient_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_id, user_id=self.user_id, owner_id='owner1', case_type='patient',
        )
        traveler_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, traveler_case_id, user_id=self.user_id, owner_id='traveler_loc_id', case_type='contact',
            index={'patient': ('patient', patient_case_id, 'child')}
        )

        non_traveler_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, non_traveler_case_id, user_id=self.user_id, owner_id='non_traveler_loc_id', case_type='contact',
            index={'patient': ('patient', patient_case_id, 'child')}
        )

        excluded_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, excluded_case_id, user_id=self.user_id, owner_id='owner1', case_type='contact',
            index={'patient': ('patient', patient_case_id, 'child')}, update={"has_index_case": 'no'},
        )

        traveler_case = CommCareCase.objects.get_case(traveler_case_id, self.domain)
        self.assertEqual(traveler_case.indices[0].referenced_type, 'patient')
        self.assertEqual(traveler_case.indices[0].relationship, 'child')

        call_command('update_case_index_relationship', self.domain, 'contact', '--location=traveler_loc_id')

        traveler_case = CommCareCase.objects.get_case(traveler_case_id, self.domain)
        self.assertEqual(traveler_case.indices[0].relationship, 'child')
        non_traveler_case = CommCareCase.objects.get_case(non_traveler_case_id, self.domain)
        self.assertEqual(non_traveler_case.indices[0].relationship, 'extension')
        excluded_case = CommCareCase.objects.get_case(excluded_case_id, self.domain)
        self.assertEqual(excluded_case.indices[0].relationship, 'child')

    def test_update_case_index_relationship_with_inactive_location(self):
        location_type = LocationType.objects.create(
            domain=self.domain,
            name="Location",
        )
        SQLLocation.objects.create(
            domain=self.domain, name='inactive_loc', location_id='inactive_loc_id',
            location_type=location_type,
        )
        patient_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_id, user_id=self.user_id, owner_id='owner1', case_type='patient',
        )
        inactive_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, inactive_case_id, user_id=self.user_id, owner_id='inactive_loc_id', case_type='contact',
            index={'patient': ('patient', patient_case_id, 'child')}
        )

        other_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, other_case_id, user_id=self.user_id, owner_id='other_owner_id', case_type='contact',
            index={'patient': ('patient', patient_case_id, 'child')}
        )

        inactive_case = CommCareCase.objects.get_case(inactive_case_id, self.domain)
        self.assertEqual(inactive_case.indices[0].referenced_type, 'patient')
        self.assertEqual(inactive_case.indices[0].relationship, 'child')

        call_command('update_case_index_relationship', self.domain, 'contact',
                     '--inactive-location=inactive_loc_id')

        inactive_case = CommCareCase.objects.get_case(inactive_case_id, self.domain)
        self.assertEqual(inactive_case.indices[0].relationship, 'extension')
        non_traveler_case = CommCareCase.objects.get_case(other_case_id, self.domain)
        self.assertEqual(non_traveler_case.indices[0].relationship, 'child')

    def test_update_owner_ids(self):
        parent_loc_type = LocationType.objects.create(
            domain=self.domain,
            name='health-department',
        )
        investigators = LocationType.objects.create(
            domain=self.domain,
            name='Investigators',
        )

        parent_loc = SQLLocation.objects.create(
            domain=self.domain, name='test-parent-location', location_id='test-parent-location',
            location_type=parent_loc_type,
        )
        SQLLocation.objects.create(
            domain=self.domain, name='test-child-location', location_id='test-child-location',
            location_type=investigators, parent=parent_loc,
        )
        SQLLocation.objects.create(
            domain=self.domain, name='test-wrong-child-location', location_id='test-wrong-child-location',
            location_type=parent_loc_type, parent=parent_loc,
        )

        investigation_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, investigation_case_id, user_id=self.user_id, owner_id='test-parent-location',
            case_type='investigation',
        )

        improper_investigation_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, improper_investigation_case_id, user_id=self.user_id, owner_id='fake-test-location',
            case_type='investigation',
        )

        investigation_case = CommCareCase.objects.get_case(investigation_case_id, self.domain)
        self.assertEqual(investigation_case.get_case_property('owner_id'), 'test-parent-location')

        call_command('update_owner_ids', self.domain, 'investigation')

        improper_investigation_case = CommCareCase.objects.get_case(improper_investigation_case_id, self.domain)
        self.assertEqual(improper_investigation_case.get_case_property('owner_id'), 'fake-test-location')
        investigation_case = CommCareCase.objects.get_case(investigation_case_id, self.domain)
        self.assertEqual(investigation_case.get_case_property('owner_id'), 'test-child-location')

    def test_add_primary_assignment_cases(self):
        self.create_active_location('active-location')
        checkin_case_id, hq_user_id = self.create_checkin_case_with_hq_user_id()

        patient_case_primary_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_primary_id, user_id=self.user_id, owner_id='active-location', case_type='patient',
            update={"is_assigned_primary": 'yes', "assigned_to_primary_checkin_case_id": checkin_case_id},
        )

        call_command('add_assignment_cases', self.domain, 'patient', '--location=active-location')
        assignment_cases = CommCareCase.objects.get_case_ids_in_domain(self.domain, "assignment")
        self.assertEqual(len(assignment_cases), 1)
        self.assertEqual(
            CommCareCase.objects.get_case(assignment_cases[0], self.domain).indices[0].relationship,
            'extension',
        )

    def test_add_temp_assignment_cases(self):
        self.create_active_location('active-location')
        checkin_case_id, hq_user_id = self.create_checkin_case_with_hq_user_id()

        patient_case_temp_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_temp_id, user_id=self.user_id, owner_id='active-location', case_type='patient',
            update={"is_assigned_temp": 'yes', "assigned_to_temp_checkin_case_id": checkin_case_id},
        )

        call_command('add_assignment_cases', self.domain, 'patient', '--location=active-location')
        assignment_cases = CommCareCase.objects.get_case_ids_in_domain(self.domain, "assignment")
        self.assertEqual(len(assignment_cases), 1)
        self.assertEqual(
            CommCareCase.objects.get_case(assignment_cases[0], self.domain).indices[0].relationship,
            'extension',
        )

    def test_add_primary_and_temp_assingment_cases(self):
        self.create_active_location('active-location')
        checkin_case_id, hq_user_id = self.create_checkin_case_with_hq_user_id()

        patient_case_both_primary_and_temp_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_both_primary_and_temp_id, user_id=self.user_id, owner_id='active-location',
            case_type='patient', update={"is_assigned_temp": 'yes',
                                         "is_assigned_primary": 'yes',
                                         "assigned_to_primary_checkin_case_id": checkin_case_id,
                                         "assigned_to_temp_checkin_case_id": checkin_case_id},
        )

        call_command('add_assignment_cases', self.domain, 'patient', '--location=active-location')
        assignment_cases = CommCareCase.objects.get_case_ids_in_domain(self.domain, "assignment")
        self.assertEqual(len(assignment_cases), 2)
        self.assertEqual(
            CommCareCase.objects.get_case(assignment_cases[0], self.domain).indices[0].relationship,
            'extension',
        )

    def test_add_assignment_cases_invalid_assigned_to_ids(self):
        self.create_active_location('active-location')
        patient_case_both_primary_and_temp_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_both_primary_and_temp_id, user_id=self.user_id, owner_id='active-location',
            case_type='patient', update={"is_assigned_temp": 'yes',
                                         "is_assigned_primary": 'yes',
                                         "assigned_to_primary_checkin_case_id": 'not_a_invalid_id',
                                         "assigned_to_temp_checkin_case_id": 'also_not_a_invalid_id'},
        )
        call_command('add_assignment_cases', self.domain, 'patient', '--location=active-location')
        assignment_cases = CommCareCase.objects.get_case_ids_in_domain(self.domain, "assignment")
        self.assertEqual(len(assignment_cases), 0)

    def test_add_assignment_cases_with_inactive_location(self):
        self.create_active_location('active-location')
        checkin_case_id, hq_user_id = self.create_checkin_case_with_hq_user_id()

        patient_case_primary_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient_case_primary_id, user_id=self.user_id, owner_id='active-location', case_type='patient',
            update={"is_assigned_primary": 'yes', "assigned_to_primary_checkin_case_id": checkin_case_id},
        )

        call_command('add_assignment_cases', self.domain, 'patient', '--location=loc-thats-not-act')
        assignment_cases = CommCareCase.objects.get_case_ids_in_domain(self.domain, "assignment")
        self.assertEqual(len(assignment_cases), 0)

    def test_clear_owner_ids(self):
        patient1_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient1_case_id, user_id=self.user_id, owner_id='owner1', case_type='patient',
        )

        patient2_case_id = uuid.uuid4().hex
        self.submit_case_block(
            True, patient2_case_id, user_id=self.user_id, owner_id='owner1', case_type='patient',
        )

        call_command('clear_owner_ids', self.domain, 'patient')

        patient1_case = CommCareCase.objects.get_case(patient1_case_id, self.domain)
        patient2_case = CommCareCase.objects.get_case(patient2_case_id, self.domain)

        self.assertEqual(patient1_case.get_case_property('owner_id'), '-')
        self.assertEqual(patient2_case.get_case_property('owner_id'), '-')


@es_test(requires=[case_search_adapter], setup_class=True)
class TestUpdateAllActivityCompleteDate(TestCase):
    domain = 'all_activity_complete_date'

    @staticmethod
    def _make_case(case_type, update, inactive_owner=True):
        case_id = str(uuid.uuid4())
        return CaseBlock(
            case_id=case_id,
            case_type=case_type,
            case_name=case_id,
            owner_id='9074edfe555043fd8f16825a6236a313' if inactive_owner else 'active',
            create=True,
            update={**{
                "all_activity_complete_date": "",
                'current_status': 'closed',
            }, **update},
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cases = {
            'good': cls._make_case('patient', {"all_activity_complete_date": "original_value"}),
            'bad_but_ignore': cls._make_case('patient', {"all_activity_complete_date": "date(today())"}),
            'not_status_closed': cls._make_case('patient', {"current_status": "open"}),
            'in_active_location': cls._make_case(
                'patient', {"isolation_end_date": "2022-01-04"}, inactive_owner=False),
            'contact_to_ignore': cls._make_case('contact', {'final_disposition': 'converted_to_pui'}),
            'patient_to_update': cls._make_case('patient', {"isolation_end_date": "2022-01-04"}),
            'patient_to_update_adjust': cls._make_case('patient', {"symptom_onset_date": "2022-01-05"}),
            'contact_to_update': cls._make_case('contact', {"quarantine_end_date": "2022-01-07"}),
            'contact_to_update_adjust': cls._make_case('contact', {"exposure_date": "2022-01-06"}),
            'no_fallback': cls._make_case('patient', {}),
        }
        case_search_es_setup(cls.domain, list(cls.cases.values()))

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    @patch('corehq.apps.hqcase.bulk.username_to_user_id', new=lambda _: 'my_username')
    def test(self):
        logging.getLogger('custom.covid.management.commands.update_all_activity_complete_date').disabled = True
        call_command('update_all_activity_complete_date', self.domain, 'patient')
        call_command('update_all_activity_complete_date', self.domain, 'contact')

        cases = {
            label: (CommCareCase.objects.get_case(case_block.case_id), case_block)
            for label, case_block in self.cases.items()
        }

        # These cases should not have been affected
        for label in [
                'good',
                'bad_but_ignore',
                'not_status_closed',
                'in_active_location',
                'contact_to_ignore',
        ]:
            case, case_block = cases[label]
            self.assertEqual(len(case.transactions), 1)
            self.assertEqual(
                case.get_case_property('all_activity_complete_date'),
                case_block.update.get('all_activity_complete_date'),
            )

        case, case_block = cases['patient_to_update']
        self.assertEqual(len(case.transactions), 2)
        self.assertEqual(
            case.get_case_property('all_activity_complete_date'),
            case_block.update.get('isolation_end_date'),
        )

        case, case_block = cases['patient_to_update_adjust']
        self.assertEqual(len(case.transactions), 2)
        self.assertEqual(
            case.get_case_property('all_activity_complete_date'),
            '2022-01-20',
        )

        case, case_block = cases['contact_to_update']
        self.assertEqual(len(case.transactions), 2)
        self.assertEqual(
            case.get_case_property('all_activity_complete_date'),
            case_block.update.get('quarantine_end_date'),
        )

        case, case_block = cases['contact_to_update_adjust']
        self.assertEqual(len(case.transactions), 2)
        self.assertEqual(
            case.get_case_property('all_activity_complete_date'),
            '2022-01-21',
        )

        case, case_block = cases['no_fallback']
        self.assertEqual(len(case.transactions), 2)
        self.assertEqual(
            case.get_case_property('all_activity_complete_date'),
            json_format_date(case.get_case_property('opened_on') + timedelta(days=15))
        )
