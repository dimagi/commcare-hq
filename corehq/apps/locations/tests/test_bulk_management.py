from django.test import SimpleTestCase, TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tree_utils import TreeError, assert_no_cycles
from corehq.apps.locations.bulk_management import (
    bulk_update_organization,
    LocationTypeStub,
    LocationStub,
    LocationTreeValidator,
)

# These example types and trees mirror the information available in the upload files

FLAT_LOCATION_TYPES = [
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False),
    ('County', 'county', 'state', False, True),
    ('City', 'city', 'county', True, False),
]

DUPLICATE_TYPE_CODES = [
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False),
    ('County', 'county', 'state', False, True),
    ('City', 'city', 'county', True, False),
    ('Other County', 'county', 'state', False, True),
]

CYCLIC_LOCATION_TYPES = [
    ('State', 'state', '', False, False),
    ('County', 'county', 'state', False, True),
    ('City', 'city', 'county', True, False),
    # These three cycle:
    ('Region', 'region', 'village', False, False),
    ('District', 'district', 'region', False, True),
    ('Village', 'village', 'district', True, False),
]

BASIC_LOCATION_TREE = [
    # ('name', 'site_code', 'location_type', 'parent_code', 'location_id',
    # 'external_id', 'latitude', 'longitude'),
    ('Massachusetts', 'mass', 'state', '', '1234', '', '', ''),
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', '', '', ''),
    ('Boston', 'boston', 'city', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', 'state', '', '5432', '', '', ''),
    ('Duval', 'duval', 'county', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', '', '', ''),
]

MOVE_SUFFOLK_TO_FLORIDA = [
    ('Massachusetts', 'mass', 'state', '', '1234', '', '', ''),
    # this is the only changed line (parent is changed to florida)
    ('Suffolk', 'suffolk', 'county', 'florida', '2345', '', '', ''),
    ('Boston', 'boston', 'city', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', 'state', '', '5432', '', '', ''),
    ('Duval', 'duval', 'county', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', '', '', ''),
]

DELETE_SUFFOLK = [
    ('Massachusetts', 'mass', 'state', '', '1234', '', '', '', ''),
    # These next two are marked as 'delete'
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', '', '', '', 'delete'),
    ('Boston', 'boston', 'city', 'suffolk', '2346', '', '', '', 'delete'),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', '', '', '', ''),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', '', ''),
    ('Florida', 'florida', 'state', '', '5432', '', '', '', ''),
    ('Duval', 'duval', 'county', 'florida', '5433', '', '', '', ''),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', '', '', '', ''),
]

MAKE_SUFFOLK_A_STATE_INVALID = [
    ('Massachusetts', 'mass', 'state', '', '1234', '', '', ''),
    # This still lists mass as a parent, which is invalid,
    # plus, Boston (a city), can't have a state as a parent
    ('Suffolk', 'suffolk', 'state', 'mass', '2345', '', '', ''),
    ('Boston', 'boston', 'city', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', 'state', '', '5432', '', '', ''),
    ('Duval', 'duval', 'county', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', '', '', ''),
]

MAKE_SUFFOLK_A_STATE_VALID = [
    ('Massachusetts', 'mass', 'state', '', '1234', '', '', ''),
    ('Suffolk', 'suffolk', 'state', '', '2345', '', '', ''),
    ('Boston', 'boston', 'county', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', 'state', '', '5432', '', '', ''),
    ('Duval', 'duval', 'county', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', '', '', ''),
]

DUPLICATE_SITE_CODES = [
    # ('name', 'site_code', 'location_type', 'parent_code', 'location_id',
    # 'external_id', 'latitude', 'longitude'),
    ('Massachusetts', 'mass', 'state', '', '1234', '', '', ''),
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', '', '', ''),
    ('Boston', 'boston', 'city', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', ''),
    ('East Cambridge', 'cambridge', 'city', 'middlesex', '3457', '', '', ''),
]


class TestBulkManagement(TestCase):

    def setUp(self):
        super(TestBulkManagement, self).setUp()
        self.domain = create_domain('location-bulk-management')

    def tearDown(self):
        super(TestBulkManagement, self).tearDown()
        # domain delete cascades to everything else
        self.domain.delete()

    def create_location_types(self, location_types):
        # populates the domain with location_types
        pass

    def create_locations(self, locations):
        # populates the domain with locations
        pass

    def assertLocationTypesMatch(self, location_types):
        # Makes sure that the set of all location types in the domain matches
        # the passed-in location types
        pass

    def assertLocationsMatch(self, locations):
        # Makes sure that the set of all locations in the domain matches
        # the passed-in locations
        pass

    def test_move_suffolk_to_florida(self):
        self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(BASIC_LOCATION_TREE)

        # the functionality that's yet to be created
        bulk_update_organization(
            self.domain,
            FLAT_LOCATION_TYPES,  # No change to types
            MOVE_SUFFOLK_TO_FLORIDA,  # This is the desired end result
        )

        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(MOVE_SUFFOLK_TO_FLORIDA)

    def test_delete_suffolk(self):
        self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(BASIC_LOCATION_TREE)

        bulk_update_organization(
            self.domain,
            FLAT_LOCATION_TYPES,
            DELETE_SUFFOLK,
        )

        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(DELETE_SUFFOLK)


class TestTreeUtils(SimpleTestCase):
    def test_no_issues(self):
        assert_no_cycles([
            ("State", None),
            ("County", "State"),
            ("City", "County"),
            ("Region", "State"),
            ("District", "Region"),
        ])

    def test_bad_parent_ref(self):
        with self.assertRaises(TreeError) as e:
            assert_no_cycles([
                ("County", "State"),  # State doesn't exist
                ("City", "County"),
                ("Region", "State"),  # State doesn't exist
                ("District", "Region"),
            ])
        self.assertItemsEqual(
            e.exception.affected_nodes,
            ["County", "Region"]
        )

    def test_has_cycle(self):
        with self.assertRaises(TreeError) as e:
            assert_no_cycles([
                ("State", None),
                ("County", "State"),
                ("City", "County"),
                # These three cycle:
                ("Region", "Village"),
                ("District", "Region"),
                ("Village", "District"),
            ])
        self.assertItemsEqual(
            e.exception.affected_nodes,
            ["Region", "District", "Village"]
        )


def get_errors(location_types, locations):
    return LocationTreeValidator(
        [LocationTypeStub(*loc_type) for loc_type in location_types],
        [LocationStub(*loc) for loc in locations],
    ).errors


class TestTreeValidator(SimpleTestCase):
    def test_good_location_set(self):
        errors = get_errors(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE)
        self.assertEqual(len(errors), 0)

    def test_cyclic_location_types(self):
        errors = get_errors(CYCLIC_LOCATION_TYPES, BASIC_LOCATION_TREE)
        self.assertEqual(len(errors), 3)

    def test_bad_type_change(self):
        errors = get_errors(FLAT_LOCATION_TYPES, MAKE_SUFFOLK_A_STATE_INVALID)
        self.assertEqual(len(errors), 2)

    def test_good_type_change(self):
        errors = get_errors(FLAT_LOCATION_TYPES, MAKE_SUFFOLK_A_STATE_VALID)
        self.assertEqual(len(errors), 0)

    def test_duplicate_type_codes(self):
        errors = get_errors(DUPLICATE_TYPE_CODES, BASIC_LOCATION_TREE)
        self.assertEqual(len(errors), 1)
        self.assertIn("county", errors[0])

    def test_duplicate_site_code(self):
        errors = get_errors(FLAT_LOCATION_TYPES, DUPLICATE_SITE_CODES)
        self.assertEqual(len(errors), 1)
        self.assertIn("cambridge", errors[0])
