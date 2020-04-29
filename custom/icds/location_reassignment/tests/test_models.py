from datetime import datetime

from django.test import TestCase

from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.locations.tests.util import setup_locations_and_types
from custom.icds.location_reassignment.const import (
    DEPRECATED_AT,
    DEPRECATED_TO,
    DEPRECATED_VIA,
    DEPRECATES,
    DEPRECATES_AT,
    DEPRECATES_VIA,
)
from custom.icds.location_reassignment.models import (
    ExtractOperation,
    MergeOperation,
    MoveOperation,
    SplitOperation,
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
        old_location_ids = [loc.location_id for loc in old_locations]
        new_location_ids = [loc.location_id for loc in new_locations]
        operation_time = old_locations[0].metadata[DEPRECATED_AT]
        self.assertIsInstance(operation_time, datetime)
        for old_location in old_locations:
            self.assertEqual(old_location.metadata[DEPRECATED_TO], new_location_ids)
            self.assertEqual(old_location.metadata[DEPRECATED_VIA], operation.type)
            self.assertEqual(old_location.metadata[DEPRECATED_AT], operation_time)
            if archived:
                self.assertTrue(old_location.is_archived)
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
