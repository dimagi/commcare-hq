from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.bulk_management import bulk_update_organization

# These example types and trees mirror the information available in the upload files

# TODO What fields should be editable in the upload?
# Look at what's editable in the UI, especially with commtrack enabled versus disabled

FLAT_LOCATION_TYPES = [
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False),
    ('County', 'county', 'state', False, True),
    ('City', 'city', 'county', True, False),
]
BASIC_LOCATION_TREE = [
    # ('name', 'site_code', 'parent_code', 'location_id', 'external_id', 'latitude', 'longitude'),
    ('Massachusetts', 'mass', '', '1234', '', '', ''),
    ('Suffolk', 'suffolk', 'mass', '2345', '', '', ''),
    ('Boston', 'boston', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', '', '5432', '', '', ''),
    ('Duval', 'duval', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'duval', '5434', '', '', ''),
]

MOVE_SUFFOLK_TO_FLORIDA = [
    # ('name', 'site_code', 'parent_code', 'location_id', 'external_id', 'latitude', 'longitude'),
    ('Massachusetts', 'mass', '', '1234', '', '', ''),
    # this is the only changed line:
    ('Suffolk', 'suffolk', 'florida', '2345', '', '', ''),
    ('Boston', 'boston', 'suffolk', '2346', '', '', ''),
    ('Middlesex', 'middlesex', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', '', '5432', '', '', ''),
    ('Duval', 'duval', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'duval', '5434', '', '', ''),
]

DELETE_SUFFOLK = [
    # ('name', 'site_code', 'parent_code', 'location_id', 'external_id', 'latitude', 'longitude', 'deleted'),
    ('Massachusetts', 'mass', '', '1234', '', '', ''),
    # this is the only changed line:
    ('Suffolk', 'suffolk', 'florida', '2345', '', '', '', 'yes'),
    ('Boston', 'boston', 'suffolk', '2346', '', '', '', 'yes'),
    ('Middlesex', 'middlesex', 'mass', '3456', '', '', ''),
    ('Cambridge', 'cambridge', 'middlesex', '3457', '', '', ''),
    ('Florida', 'florida', '', '5432', '', '', ''),
    ('Duval', 'duval', 'florida', '5433', '', '', ''),
    ('Jacksonville', 'jacksonville', 'duval', '5434', '', '', ''),
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

        # the functionality that's yet to be created
        bulk_update_organization(
            self.domain,
            FLAT_LOCATION_TYPES,
            DELETE_SUFFOLK,
        )

        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(DELETE_SUFFOLK)
