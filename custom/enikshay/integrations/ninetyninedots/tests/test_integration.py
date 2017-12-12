from __future__ import absolute_import
from datetime import datetime
import pytz
import os
import mock
from django.test import TestCase, override_settings


from corehq.form_processor.tests.utils import FormProcessorTestUtils

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.integrations.ninetyninedots.views import (
    validate_adherence_values,
    validate_beneficiary_id,
)
from custom.enikshay.case_utils import get_open_episode_case_from_person
from custom.enikshay.integrations.ninetyninedots.api_spec import load_api_spec
from custom.enikshay.integrations.ninetyninedots.utils import (
    create_adherence_cases,
    PatientDetailsUpdater,
    update_adherence_confidence_level,
    update_default_confidence_level,
)
from custom.enikshay.integrations.ninetyninedots.exceptions import NinetyNineDotsException
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin


def property_setter(param, val, sector):
    return {'property_set_with_setter': val}


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class Receiver99DotsTests(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(Receiver99DotsTests, self).setUp()
        self.fake_api_spec_patch = mock.patch('custom.enikshay.integrations.ninetyninedots.utils.load_api_spec')
        fake_api_spec = self.fake_api_spec_patch.start()
        fake_api_spec.return_value = load_api_spec(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_api_spec.yaml')
        )
        self.spec = fake_api_spec()
        self.create_case_structure()

    def tearDown(self):
        self.fake_api_spec_patch.stop()

    def _get_fake_request(self):
        fake_request = {prop: '123' for prop in self.spec.required_params}
        fake_request['beneficiary_id'] = self.person_id
        return fake_request

    def test_required_properties(self):
        # request with required properties gets passed through fine
        PatientDetailsUpdater(self.domain, self._get_fake_request())

        # Without the required property, raises an error
        with self.assertRaises(NinetyNineDotsException) as e:
            PatientDetailsUpdater(None, {'boop': 'barp'})
        self.assertTrue(", ".join(self.spec.required_params) in str(e.exception))

    def test_patient_not_found(self):
        fake_request = self._get_fake_request()
        fake_request['beneficiary_id'] = '123'
        with self.assertRaises(NinetyNineDotsException) as e:
            PatientDetailsUpdater(None, fake_request)
        self.assertTrue(str(e.exception), "No patient exists with this beneficiary ID")

    def test_invalid_choice(self):
        fake_request = self._get_fake_request()

        # A request with a valid choice passes through fine
        fake_request['has_choices'] = 'foo'
        PatientDetailsUpdater(None, fake_request)

        # A request with an invalid choice raises an error
        fake_request = self._get_fake_request()
        fake_request['has_choices'] = 'biff'
        with self.assertRaises(NinetyNineDotsException) as e:
            PatientDetailsUpdater(None, fake_request)
        self.assertEqual(str(e.exception), "biff is not a valid value for has_choices.")

    def test_wrong_direction(self):
        fake_request = self._get_fake_request()
        fake_request['outbound_only'] = 'foo'
        with self.assertRaises(NinetyNineDotsException) as e:
            PatientDetailsUpdater(self.domain, fake_request).update_cases()
        self.assertEqual(str(e.exception), "outbound_only is not a valid parameter to update")

        fake_request = self._get_fake_request()
        fake_request['inbound_only'] = 'bar'
        # shouldn't throw an exception
        PatientDetailsUpdater(self.domain, fake_request).update_cases()

    def test_update_with_setter(self):
        fake_request = self._get_fake_request()
        fake_request['with_setter'] = 'foo'

        PatientDetailsUpdater(self.domain, fake_request).update_cases()

        person_case = CaseAccessors(self.domain).get_case(self.person_id)
        self.assertEqual(person_case.get_case_property('property_set_with_setter'), 'foo')

    def test_case_update(self):
        fake_request = self._get_fake_request()
        fake_request['has_choices'] = 'foo'
        PatientDetailsUpdater(self.domain, fake_request).update_cases()

        person_case = CaseAccessors(self.domain).get_case(self.person_id)
        self.assertEqual(person_case.get_case_property('required_param'), '123')

        episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(episode_case.get_case_property('has_choices'), 'foo')

    def test_split_name(self):
        fake_request = self._get_fake_request()

        fake_request['split_name'] = 'Arya Horseface Stark'
        PatientDetailsUpdater(self.domain, fake_request).update_cases()

        person_case = CaseAccessors(self.domain).get_case(self.person_id)
        self.assertEqual(person_case.get_case_property('foo'), 'Arya')
        self.assertEqual(person_case.get_case_property('bar'), 'Horseface Stark')

    def test_validate_patient_adherence_data(self):
        with self.assertRaises(NinetyNineDotsException) as e:
            validate_beneficiary_id(None)
            self.assertEqual(e.message, "Beneficiary ID is null")

        with self.assertRaises(NinetyNineDotsException) as e:
            validate_adherence_values(u'123')
            self.assertEqual(e.message, "Adherences invalid")


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class NinetyNineDotsCaseTests(ENikshayCaseStructureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(NinetyNineDotsCaseTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def test_create_adherence_cases(self):
        self.create_case_structure()
        case_accessor = CaseAccessors(self.domain)
        adherence_values = [
            {
                "timestamp": "2009-03-05T01:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456789",
                "sharedNumber": False,
                "adherenceSource": "99DOTS",
            },
            {
                "timestamp": "2016-03-05T02:00:01-05:00",
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
                "adherenceSource": "MERM",
            },
            {
                "timestamp": "2016-03-05T19:00:01-05:00",  # next day in india
                "numberFromWhichPatientDialled": "+910123456787",
                "sharedNumber": True,
            }
        ]
        create_adherence_cases(self.domain, 'person', adherence_values)
        potential_adherence_cases = case_accessor.get_reverse_indexed_cases(['episode'])
        adherence_cases = [case for case in potential_adherence_cases if case.type == 'adherence']
        self.assertEqual(len(adherence_cases), 3)

        self.assertItemsEqual(
            [case.dynamic_case_properties().get('adherence_date') for case in adherence_cases],
            ['2009-03-05', '2016-03-05', '2016-03-06']
        )
        self.assertItemsEqual(
            [case.dynamic_case_properties().get('adherence_source') for case in adherence_cases],
            ['99DOTS', 'MERM', '99DOTS']
        )
        for adherence_case in adherence_cases:
            self.assertEqual(
                adherence_case.dynamic_case_properties().get('adherence_confidence'),
                'high'
            )

    def test_update_adherence_confidence(self):
        self.create_case_structure()
        case_accessor = CaseAccessors(self.domain)
        adherence_dates = [
            datetime(2005, 7, 10),
            datetime(2016, 8, 10),
            datetime(2016, 8, 11),
        ]
        adherence_cases = self.create_adherence_cases(adherence_dates)

        update_adherence_confidence_level(
            self.domain,
            self.person_id,
            datetime(2016, 8, 10, tzinfo=pytz.UTC),
            datetime(2016, 8, 11, tzinfo=pytz.UTC),
            "new_confidence_level",
        )
        adherence_case_ids = [adherence_date.strftime("%Y-%m-%d-%H-%M") for adherence_date in adherence_dates]
        adherence_cases = {case.case_id: case for case in case_accessor.get_cases(adherence_case_ids)}

        self.assertEqual(
            adherence_cases[adherence_case_ids[0]].dynamic_case_properties()['adherence_confidence'],
            'medium',
        )
        self.assertEqual(
            adherence_cases[adherence_case_ids[1]].dynamic_case_properties()['adherence_confidence'],
            'new_confidence_level',
        )
        self.assertEqual(
            adherence_cases[adherence_case_ids[2]].dynamic_case_properties()['adherence_confidence'],
            'new_confidence_level',
        )

    def test_update_default_confidence_level(self):
        self.create_case_structure()
        confidence_level = "new_confidence_level"
        update_default_confidence_level(self.domain, self.person_id, confidence_level)
        episode = get_open_episode_case_from_person(self.domain, self.person_id)
        self.assertEqual(episode.dynamic_case_properties().get('default_adherence_confidence'), confidence_level)
