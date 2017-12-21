from __future__ import absolute_import

from datetime import datetime

from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from corehq.motech.repeaters.dbaccessors import (
    delete_all_repeat_records,
    delete_all_repeaters,
)
from corehq.motech.repeaters.models import RepeatRecord
from custom.enikshay.const import (
    PRIMARY_PHONE_NUMBER,
    TREATMENT_OUTCOME,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_PHONE,
)
from custom.enikshay.integrations.ninetyninedots.repeaters import (
    NinetyNineDotsAdherenceRepeater,
    NinetyNineDotsRegisterPatientRepeater,
    NinetyNineDotsTreatmentOutcomeRepeater,
    NinetyNineDotsUnenrollPatientRepeater,
    NinetyNineDotsUpdatePatientRepeater,
)
from custom.enikshay.tests.utils import (
    ENikshayCaseStructureMixin,
    ENikshayLocationStructureMixin,
)


class ENikshayRepeaterTestBase(ENikshayCaseStructureMixin, TestCase):
    maxDiff = None

    def setUp(self):
        super(ENikshayRepeaterTestBase, self).setUp()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def tearDown(self):
        super(ENikshayRepeaterTestBase, self).tearDown()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def _create_99dots_enabled_case(self):
        dots_enabled_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'case_type': 'episode',
                "update": dict(
                    dots_99_enabled='true',
                )
            }
        )
        self.create_case(dots_enabled_case)

    def _create_99dots_registered_case(self):
        dots_registered_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    dots_99_registered='true',
                )
            }
        )
        self.create_case(dots_registered_case)

    def _update_case(self, case_id, case_properties, close=False):
        return self.create_case(
            CaseStructure(
                case_id=case_id,
                attrs={
                    "close": close,
                    "update": case_properties,
                }
            )
        )


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestRegisterPatientRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestRegisterPatientRepeater, self).setUp()

        self.repeater = NinetyNineDotsRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):
        # 99dots not enabled
        self.create_case(self.episode)
        self.assign_person_to_location(self.phi.location_id)
        self.assertEqual(0, len(self.repeat_records().all()))

        # enable 99dots, should register a repeat record
        self._create_99dots_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))

        # updating some other random properties shouldn't create a new repeat record
        self._update_case(self.episode_id, {'some_property': "changed"})
        self.assertEqual(1, len(self.repeat_records().all()))

        # set as registered, shouldn't register a new repeat record
        self._create_99dots_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestUpdatePatientRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestUpdatePatientRepeater, self).setUp()
        self.repeater = NinetyNineDotsUpdatePatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['person', 'episode']
        self.repeater.save()

    def test_trigger(self):
        self.create_case_structure()
        self._update_case(self.person_id, {PRIMARY_PHONE_NUMBER: '999999999', })
        self.assign_person_to_location(self.phi.location_id)
        self.assertEqual(0, len(self.repeat_records().all()))

        self._create_99dots_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.person_id, {'name': 'Elrond', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.person_id, {PRIMARY_PHONE_NUMBER: '999999999', })
        self.assertEqual(1, len(self.repeat_records().all()))

        # update a pertinent case with something that shouldn't trigger,
        # and a non-pertinent case with a property that is in the list of triggers
        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=self.person_id,
                attrs={
                    "update": {'name': 'Elrond', },
                }
            ),
            CaseStructure(
                case_id=self.occurrence_id,
                attrs={
                    "update": {PRIMARY_PHONE_NUMBER: '999999999', },
                }
            ),

        ])
        self.assertEqual(1, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {TREATMENT_SUPPORTER_PHONE: '999999999', })
        self.assertEqual(2, len(self.repeat_records().all()))

    def test_update_owner_id(self):
        self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)
        self._create_99dots_registered_case()
        self._update_case(self.person_id, {'owner_id': self.dto.location_id})
        self.assertEqual(1, len(self.repeat_records().all()))

    def test_trigger_multiple_cases(self):
        """Submitting a form with noop case blocks was throwing an exception
        """
        self.create_case_structure()
        self.assign_person_to_location(self.phi.location_id)
        self._create_99dots_registered_case()

        empty_case = CaseStructure(
            case_id=self.episode_id,
        )
        person_case = CaseStructure(
            case_id=self.person_id,
            attrs={
                'case_type': 'person',
                'update': {PRIMARY_PHONE_NUMBER: '9999999999'}
            }
        )

        self.factory.create_or_update_cases([empty_case, person_case])
        self.assertEqual(1, len(self.repeat_records().all()))

    def test_create_person_no_episode(self):
        """On registration this was failing hard if a phone number was added but no episode was created
        http://manage.dimagi.com/default.asp?241290#1245284
        """
        self.create_case(self.person)
        self.assertEqual(0, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestAdherenceRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestAdherenceRepeater, self).setUp()
        self.repeater = NinetyNineDotsAdherenceRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['adherence']
        self.repeater.save()

    def test_trigger(self):
        self.create_case_structure()
        self._create_99dots_registered_case()
        self._create_99dots_enabled_case()
        self.assign_person_to_location(self.phi.location_id)
        self.assertEqual(0, len(self.repeat_records().all()))

        self.create_adherence_cases([datetime(2017, 2, 17)])
        self.assertEqual(0, len(self.repeat_records().all()))

        self.create_adherence_cases([datetime(2017, 2, 18)], adherence_source='enikshay')
        self.assertEqual(1, len(self.repeat_records().all()))

        case = self.create_adherence_cases([datetime(2017, 2, 20)], adherence_source='enikshay')
        self.assertEqual(2, len(self.repeat_records().all()))

        # Updating the case doesn't make a new repeat record
        self._update_case(case[0].case_id, {'dots_99_error': "hello"})
        self.assertEqual(2, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestTreatmentOutcomeRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestTreatmentOutcomeRepeater, self).setUp()
        self.repeater = NinetyNineDotsTreatmentOutcomeRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger(self):
        self.create_case_structure()
        self._create_99dots_registered_case()
        self._create_99dots_enabled_case()
        self.assign_person_to_location(self.phi.location_id)
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {TREATMENT_OUTCOME: 'the_end_of_days'})
        self.assertEqual(1, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {TREATMENT_SUPPORTER_FIRST_NAME: 'boo'})
        self.assertEqual(1, len(self.repeat_records().all()))


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestUnenrollPatientRepeater(ENikshayLocationStructureMixin, ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestUnenrollPatientRepeater, self).setUp()
        self.repeater = NinetyNineDotsUnenrollPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    def test_trigger_99dots_disabled(self):
        self.create_case_structure()
        self._create_99dots_registered_case()
        self._create_99dots_enabled_case()
        self.assign_person_to_location(self.phi.location_id)
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {'dots_99_enabled': 'false'})
        self.assertEqual(1, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {'dots_99_enabled': 'true'})
        self.assertEqual(1, len(self.repeat_records().all()))

    def test_trigger_case_closed(self):
        self.create_case_structure()
        self._create_99dots_registered_case()
        self._create_99dots_enabled_case()
        self.assign_person_to_location(self.phi.location_id)
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {'close_reason': 'boo'}, close=True)
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {'close_reason': 'duplicate'}, close=True)
        self.assertEqual(1, len(self.repeat_records().all()))
