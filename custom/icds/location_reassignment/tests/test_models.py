from datetime import datetime

from django.test import TestCase

from mock import patch

from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tests.util import setup_locations_and_types
from custom.icds.location_reassignment.const import (
    DEPRECATED_AT,
    DEPRECATED_TO,
    DEPRECATED_VIA,
    DEPRECATES,
    DEPRECATES_AT,
    DEPRECATES_VIA,
    LGD_CODE,
    MAP_LOCATION_NAME,
)
from custom.icds.location_reassignment.exceptions import InvalidTransitionError
from custom.icds.location_reassignment.models import (
    ExtractOperation,
    MergeOperation,
    MoveOperation,
    SplitOperation,
    Transition,
)


class BaseTest(TestCase):
    operation = None
    domain = "test"
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ]),
        ('California', [
            ('Los Angeles', []),
        ])
    ]

    @classmethod
    def setUpClass(cls):
        super(BaseTest, cls).setUpClass()
        cls.domain_obj = bootstrap_domain(cls.domain)

    def setUp(self):
        super(BaseTest, self).setUp()
        self.location_types, self.locations = setup_locations_and_types(
            self.domain,
            self.location_type_names,
            [],
            self.location_structure,
        )

    def _validate_operation(self, operation, archived):
        old_locations = operation.old_locations
        new_locations = operation.new_locations
        old_location_ids = ",".join([loc.location_id for loc in old_locations])
        new_location_ids = ",".join([loc.location_id for loc in new_locations])
        operation_time = old_locations[0].metadata[DEPRECATED_AT]
        self.assertIsInstance(operation_time, datetime)
        for old_location in old_locations:
            self.assertEqual(old_location.metadata[DEPRECATED_TO], new_location_ids)
            self.assertEqual(old_location.metadata[DEPRECATED_VIA], operation.type)
            self.assertEqual(old_location.metadata[DEPRECATED_AT], operation_time)
            if archived:
                self.assertTrue(old_location.is_archived)
                self.assertEqual(old_location.archived_on, operation_time)
        for new_location in new_locations:
            self.assertEqual(new_location.metadata[DEPRECATES], old_location_ids)
            self.assertEqual(new_location.metadata[DEPRECATES_VIA], operation.type)
            self.assertEqual(new_location.metadata[DEPRECATES_AT], operation_time)


class TestOperation(BaseTest):
    def check_operation(self, old_site_codes, new_site_codes, archived=True):
        operation = self.operation(self.domain, old_site_codes, new_site_codes)
        operation.valid()
        operation.perform()
        self._validate_operation(operation, archived)


class TestMergeOperation(TestOperation):
    operation = MergeOperation

    def test_perform(self):
        new_site_codes = [self.locations['Boston'].site_code]
        old_site_codes = [self.locations['Cambridge'].site_code, self.locations['Somerville'].site_code]
        self.check_operation(old_site_codes, new_site_codes)


class TestSplitOperation(TestOperation):
    operation = SplitOperation

    def test_perform(self):
        old_site_codes = [self.locations['Boston'].site_code]
        new_site_codes = [self.locations['Cambridge'].site_code, self.locations['Somerville'].site_code]
        self.check_operation(old_site_codes, new_site_codes)


class TestExtractOperation(TestOperation):
    operation = ExtractOperation

    def test_perform(self):
        old_site_codes = [self.locations['Boston'].site_code]
        new_site_codes = [self.locations['Cambridge'].site_code]
        self.check_operation(old_site_codes, new_site_codes, archived=False)


class TestMoveOperation(TestOperation):
    operation = MoveOperation

    def test_perform(self):
        old_site_codes = [self.locations['Boston'].site_code]
        new_site_codes = [self.locations['Cambridge'].site_code]
        self.check_operation(old_site_codes, new_site_codes)


class TestTransition(BaseTest):
    @patch('custom.icds.location_reassignment.models.deactivate_users_at_location')
    def test_perform(self, deactivate_users_mock):
        transition = Transition(domain=self.domain, location_type_code='city', operation=MoveOperation.type)
        transition.add(
            old_site_code=self.locations['Boston'].site_code,
            new_site_code='new_boston',
            new_location_details={
                'name': 'New Boston',
                'parent_site_code': self.locations['Suffolk'].site_code,
                'lgd_code': 'New Boston LGD Code',
                'sub_district_name': 'New Boston Sub District'
            },
            old_username="ethan",
            new_username="aquaman"
        )
        self.assertEqual(SQLLocation.objects.filter(domain=self.domain, site_code='new_boston').count(), 0,
                         "New location already present")
        transition.perform()
        self._validate_operation(transition.operation_obj, archived=True)
        new_location = SQLLocation.active_objects.get_or_None(domain=self.domain, site_code='new_boston')
        self.assertIsNotNone(new_location, "New location not created successfully")
        self.assertEqual(new_location.metadata[LGD_CODE], 'New Boston LGD Code')
        self.assertEqual(new_location.metadata[MAP_LOCATION_NAME], 'New Boston Sub District')
        deactivate_users_mock.assert_called_with(self.locations['Boston'].location_id)

    @patch('custom.icds.location_reassignment.models.deactivate_users_at_location')
    def test_invalid_operation(self, deactivate_users_mock):
        transition = Transition(domain=self.domain, location_type_code='city', operation=MoveOperation.type)
        transition.add(
            old_site_code='missing_old_location',
            new_site_code='new_boston',
            new_location_details={
                'name': 'New Boston',
                'parent_site_code': self.locations['Suffolk'].site_code,
                'lgd_code': 'New Boston LGD Code',
                'sub_district_name': None
            },
            old_username="ethan",
            new_username="aquaman"
        )
        self.assertEqual(SQLLocation.objects.filter(domain=self.domain, site_code='new_boston').count(), 0)
        with self.assertRaisesMessage(InvalidTransitionError,
                                      "Could not load location with following site codes: missing_old_location"):
            transition.perform()
        self.assertEqual(SQLLocation.objects.filter(domain=self.domain, site_code='new_boston').count(), 0,
                         "Unexpected new location created")
        deactivate_users_mock.assert_not_called()

    @patch('custom.icds.location_reassignment.models.deactivate_users_at_location')
    def test_can_perform_deprecation(self, *mocks):
        transition = Transition(domain=self.domain, location_type_code='city', operation=MoveOperation.type)
        transition.add(
            old_site_code=self.locations['Boston'].site_code,
            new_site_code='new_boston',
            new_location_details={
                'name': 'New Boston',
                'parent_site_code': self.locations['Suffolk'].site_code,
                'lgd_code': 'New Boston LGD Code',
                'sub_district_name': 'New Boston Sub District'
            },
            old_username="ethan",
            new_username="aquaman"
        )

        location = self.locations['Boston']
        location.metadata[DEPRECATED_VIA] = MergeOperation.type
        location.save()
        with self.assertRaisesMessage(
            InvalidTransitionError,
            "Move operation: location Boston with site code boston cannot be deprecated again."
        ):
            transition.perform()

        location = self.locations['Boston']
        location.metadata[DEPRECATED_VIA] = ExtractOperation.type
        location.save()

        location = self.locations['Boston']
        location.metadata[DEPRECATED_VIA] = ExtractOperation.type
        location.save()
        transition.perform()
        self._validate_operation(transition.operation_obj, archived=True)
