from collections import namedtuple

from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import Location, LocationType
from corehq.apps.locations.tree_utils import TreeError, assert_no_cycles, expansion_validators
from corehq.apps.locations.bulk_management import (
    NewLocationImporter,
    LocationTypeStub,
    LocationStub,
    LocationTreeValidator,
    LocationCollection,
)


# These example types and trees mirror the information available in the upload files

FLAT_LOCATION_TYPES = [
    # name, code, parent_code, do_delete, shares_cases, view_descendants, expand_from, sync_to, index
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False, False, '', '', 0),
    ('County', 'county', 'state', False, False, True, '', '', 0),
    ('City', 'city', 'county', False, True, False, '', '', 0),
]

DUPLICATE_TYPE_CODES = [
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False, False, '', '', 0),
    ('County', 'county', 'state', False, False, True, '', '', 0),
    ('City', 'city', 'county', False, True, False, '', '', 0),
    ('Other County', 'county', 'state', False, False, True, '', '', 0),
]

CYCLIC_LOCATION_TYPES = [
    ('State', 'state', '', False, False, False, '', '', 0),
    ('County', 'county', 'state', False, False, True, '', '', 0),
    ('City', 'city', 'county', False, True, False, '', '', 0),
    # These three cycle:
    ('Region', 'region', 'village', False, False, False, '', '', 0),
    ('District', 'district', 'region', False, False, True, '', '', 0),
    ('Village', 'village', 'district', False, True, False, '', '', 0),
]

BASIC_LOCATION_TREE = [
    # (name, site_code, location_type, parent_code, location_id,
    # do_delete, external_id, latitude, longitude, index)
    # ('name', 'site_code', 'location_type', 'parent_code', 'location_id',
    # 'external_id', 'latitude', 'longitude'),
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', False, '', '', '', 0),
    ('Boston', 'boston', 'city', 'suffolk', '2346', False, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('Florida', 'florida', 'state', '', '5432', False, '', '', '', 0),
    ('Duval', 'duval', 'county', 'florida', '5433', False, '', '', '', 0),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False, '', '', '', 0),
]

MOVE_SUFFOLK_TO_FLORIDA = [
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    # this is the only changed line (parent is changed to florida)
    ('Suffolk', 'suffolk', 'county', 'florida', '2345', False, '', '', '', 0),
    ('Boston', 'boston', 'city', 'suffolk', '2346', False, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('Florida', 'florida', 'state', '', '5432', False, '', '', '', 0),
    ('Duval', 'duval', 'county', 'florida', '5433', False, '', '', '', 0),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False, '', '', '', 0),
]

DELETE_SUFFOLK = [
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    # These next two are marked as 'delete'
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', True, '', '', '', 0),
    ('Boston', 'boston', 'city', 'suffolk', '2346', True, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('Florida', 'florida', 'state', '', '5432', False, '', '', '', 0),
    ('Duval', 'duval', 'county', 'florida', '5433', False, '', '', '', 0),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False, '', '', '', 0),
]

MAKE_SUFFOLK_A_STATE_INVALID = [
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    # This still lists mass as a parent, which is invalid,
    # plus, Boston (a city), can't have a state as a parent
    ('Suffolk', 'suffolk', 'state', 'mass', '2345', False, '', '', '', 0),
    ('Boston', 'boston', 'city', 'suffolk', '2346', False, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('Florida', 'florida', 'state', '', '5432', False, '', '', '', 0),
    ('Duval', 'duval', 'county', 'florida', '5433', False, '', '', '', 0),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False, '', '', '', 0),
]

MAKE_SUFFOLK_A_STATE_VALID = [
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    ('Suffolk', 'suffolk', 'state', '', '2345', False, '', '', '', 0),
    ('Boston', 'boston', 'county', 'suffolk', '2346', False, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('Florida', 'florida', 'state', '', '5432', False, '', '', '', 0),
    ('Duval', 'duval', 'county', 'florida', '5433', False, '', '', '', 0),
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False, '', '', '', 0),
]

DUPLICATE_SITE_CODES = [
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', False, '', '', '', 0),
    ('Boston', 'boston', 'city', 'suffolk', '2346', False, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('East Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
]

SAME_NAME_SAME_PARENT = [
    ('Massachusetts', 'mass', 'state', '', '1234', False, '', '', '', 0),
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False, '', '', '', 0),
    # These two locations have the same name AND same parent
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False, '', '', '', 0),
    ('Cambridge', 'cambridge2', 'city', 'middlesex', '3458', False, '', '', '', 0),
]


class TestTreeUtils(SimpleTestCase):
    def test_no_issues(self):
        assert_no_cycles([
            ("State", 'TOP'),
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
                ("State", 'TOP'),
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

    def test_expansion_validators(self):
        from_validator, to_validator = expansion_validators(
            [('a', 'TOP'), ('b', 'TOP'), ('c', 'a'), ('d', 'a'), ('e', 'b')]
        )
        self.assertEqual(from_validator('a'), ['a', 'TOP'])
        self.assertEqual(from_validator('b'), ['b', 'TOP'])
        self.assertEqual(from_validator('c'), ['c', 'a', 'TOP'])
        self.assertEqual(from_validator('d'), ['d', 'a', 'TOP'])
        self.assertEqual(from_validator('e'), ['e', 'b', 'TOP'])
        self.assertEqual(to_validator('a'), ['a', 'c', 'd'])
        self.assertEqual(to_validator('b'), ['b', 'e'])
        self.assertEqual(to_validator('c'), ['c'])
        self.assertEqual(to_validator('d'), ['d'])
        self.assertEqual(to_validator('e'), ['e'])


def get_validator(location_types, locations, old_collection=None):
    validator = LocationTreeValidator(
        [LocationTypeStub(*loc_type) for loc_type in location_types],
        [LocationStub(*loc) for loc in locations],
        old_collection=old_collection
    )
    return validator


MockCollection = namedtuple('MockCollection', 'types locations locations_by_id locations_by_site_code')


def make_collection(types, locations):
    types = [LocationTypeStub(*loc_type) for loc_type in types]

    locations = [LocationStub(*loc) for loc in locations]

    return MockCollection(
        types=types,
        locations=locations,
        locations_by_id={l.location_id: l for l in locations},
        locations_by_site_code={l.site_code: l for l in locations}
    )


class TestTreeValidator(SimpleTestCase):

    def test_good_location_set(self):
        validator = get_validator(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE)
        self.assertEqual(len(validator.errors), 0)

    def test_cyclic_location_types(self):
        validator = get_validator(CYCLIC_LOCATION_TYPES, BASIC_LOCATION_TREE)
        self.assertEqual(len(validator._validate_types_tree()), 3)

    def test_bad_type_change(self):
        validator = get_validator(FLAT_LOCATION_TYPES, MAKE_SUFFOLK_A_STATE_INVALID)

        all_errors = validator.errors
        self.assertEqual(len(all_errors), 2)

        tree_errors = validator._validate_location_tree()
        self.assertEqual(len(tree_errors), 2)

    def test_good_type_change(self):
        validator = get_validator(FLAT_LOCATION_TYPES, MAKE_SUFFOLK_A_STATE_VALID)
        errors = validator.errors
        self.assertEqual(len(errors), 0)

    def test_duplicate_type_codes(self):
        validator = get_validator(DUPLICATE_TYPE_CODES, BASIC_LOCATION_TREE)
        errors = validator.errors
        type_errors = validator._check_unique_type_codes()
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(type_errors), 1)
        self.assertIn("county", errors[0])

    def test_valid_expansions(self):
        validator = get_validator(
            [
                # name, code, parent_code, do_delete, shares_cases, view_descendants, expand_from, sync_to, index
                # empty from, descendant as to
                ('A', 'a', '', False, False, False, '', 'd', 0),
                # itself as from, descendant as to
                ('B', 'b', '', False, False, False, 'b', 'e', 0),
                # empty to, parentage as from
                ('C', 'c', 'a', False, False, False, 'a', '', 0),
                # itself as to, parentage as from
                ('D', 'd', 'a', False, False, False, 'a', 'd', 0),
                # parentage as from, empty to
                ('E', 'e', 'b', False, False, False, 'b', '', 0),
            ],
            []
        )
        errors = validator.errors
        self.assertEqual(errors, [])

    def test_invalid_expansions(self):
        validator = get_validator(
            [
                # name, code, parent_code, do_delete, shares_cases, view_descendants, expand_from, sync_to, index
                ('A', 'a', '', False, False, False, '', 'd', 0),
                # 'a' is not a descendant of 'b'
                ('B', 'b', '', False, False, False, 'b', 'a', 0),
                ('C', 'c', 'a', False, False, False, 'a', '', 0),
                # 'b' doesn't occur in its parentage
                ('D', 'd', 'a', False, False, False, 'b', 'd', 0),
                ('E', 'e', 'b', False, False, False, 'b', '', 0),
            ],
            []
        )
        errors = validator.errors
        self.assertEqual(len(errors), 2)

    def test_duplicate_location(self):
        validator = get_validator(FLAT_LOCATION_TYPES, DUPLICATE_SITE_CODES)
        errors = validator.errors
        self.assertEqual(len(errors), 2)
        self.assertEqual(len(validator._check_unique_location_codes()), 1)
        self.assertEqual(len(validator._check_unique_location_ids()), 1)
        self.assertIn("cambridge", errors[0])

    def test_same_name_same_parent(self):
        validator = get_validator(FLAT_LOCATION_TYPES, SAME_NAME_SAME_PARENT)
        errors = validator.errors
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(validator._check_location_names()), 1)
        self.assertIn("middlesex", errors[0])

    def test_missing_types(self):
        # all types in the domain should be listed in given excel
        old_types = FLAT_LOCATION_TYPES + [('Galaxy', 'galaxy', '', False, False, False, '', '', 0)]

        old_collection = make_collection(old_types, BASIC_LOCATION_TREE)
        validator = get_validator(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE, old_collection)

        missing_type_errors = validator._check_unlisted_type_codes()
        self.assertEqual(len(missing_type_errors), 1)
        self.assertEqual(len(validator.errors), 1)
        self.assertIn('galaxy', missing_type_errors[0])

    def test_missing_location_ids(self):
        # all locations in the domain should be listed in given excel
        old_locations = (
            BASIC_LOCATION_TREE +
            [('extra_state', 'ex_code', 'state', '', 'ex_id', False, '', '', '', 0)]
        )
        old_collection = make_collection(FLAT_LOCATION_TYPES, old_locations)
        validator = get_validator(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE, old_collection)
        missing_locations = validator._check_unlisted_location_ids()
        self.assertEqual(len(missing_locations), 1)
        self.assertEqual(len(validator.errors), 1)
        self.assertIn('extra_state', missing_locations[0])

    def test_unknown_location_ids(self):
        # all locations in the domain should be listed in given excel

        old_collection = make_collection(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE)
        new_locations = (
            BASIC_LOCATION_TREE +
            [('extra_state', 'ex_code', 'state', '', 'ex_id', False, '', '', '', 0)]
        )
        validator = get_validator(FLAT_LOCATION_TYPES, new_locations, old_collection)
        unknown_locations = validator._check_unknown_location_ids()
        self.assertEqual(len(unknown_locations), 1)
        self.assertEqual(len(validator.errors), 1)
        self.assertIn('ex_id', unknown_locations[0])


class TestBulkManagement(TestCase):
    basic_tree = [
        # (name, site_code, location_type, parent_code, location_id,
        # do_delete, external_id, latitude, longitude, index)
        ('S1', 's1', 'state', '', '', False, '', '', '', 0),
        ('S2', 's2', 'state', '', '', False, '', '', '', 0),
        ('County11', 'county11', 'county', 's1', '', False, '', '', '', 0),
        ('County21', 'county21', 'county', 's2', '', False, '', '', '', 0),
        ('City111', 'city111', 'city', 'county11', '', False, '', '', '', 0),
        ('City112', 'city112', 'city', 'county11', '', False, '', '', '', 0),
        ('City211', 'city211', 'city', 'county21', '', False, '', '', '', 0),
    ]

    @classmethod
    def as_pairs(cls, tree):
        pairs = []
        for l in tree:
            code = l[1]
            parent_code = l[3] or None
            do_delete = l[5]
            if not do_delete:
                pairs.append((code, parent_code))
        return set(pairs)

    def setUp(self):
        super(TestBulkManagement, self).setUp()
        self.domain = create_domain('location-bulk-management')

    def tearDown(self):
        super(TestBulkManagement, self).tearDown()
        # domain delete cascades to everything else
        self.domain.delete()

    def create_location_types(self, location_types):
        def _make_loc_type(name, code, parent_code, _delete, shares_cases, view_descendants,
                           expand_from, sync_to, _i, parent_type=None):
            return LocationType.objects.create(
                domain=self.domain.name,
                name=name,
                code=code,
                parent_type=parent_type,
                shares_cases=shares_cases,
                view_descendants=view_descendants
            )

        lt_by_code = {}
        for lt in location_types:
            code = lt[1]
            parent_code = lt[2]
            parent_type = lt_by_code.get(parent_code)
            location_type = _make_loc_type(*lt, parent_type=parent_type)
            lt_by_code[code] = location_type
        return lt_by_code

    def create_locations(self, locations, lt_by_code):
        def _make_loc(name, site_code, location_type, _parent_code, _,
                      _delete, external_id, latitude, longitude, _i, parent=None):
            _type = lt_by_code.get(location_type)
            loc = Location(
                site_code=site_code, name=name, domain=self.domain.name, location_type=_type,
                parent=parent,
            )
            loc.save()
            return loc

        locations_by_code = {}
        for l in locations:
            code = l[1]
            parent_code = l[3]
            parent = locations_by_code.get(parent_code)
            location = _make_loc(*l, parent=parent)
            locations_by_code[code] = location
        return locations_by_code

    def bulk_update_locations(self, types, locations):
        importer = NewLocationImporter(
            self.domain.name,
            [LocationTypeStub(*loc_type) for loc_type in types],
            [LocationStub(*loc) for loc in locations],
        )
        result = importer.run()
        return result

    def assertLocationTypesMatch(self, expected_types):
        # Makes sure that the set of all location types in the domain matches
        # the passed-in location types
        actual_types = self.domain.location_types
        actual = [
            (lt.code, lt.parent_type.code) if lt.parent_type else (lt.code, None)
            for lt in actual_types
        ]

        expected = []
        for lt in expected_types:
            code = lt[1]
            parent_code = lt[2] or None
            do_delete = lt[3]
            if not do_delete:
                expected.append((code, parent_code))

        self.assertEqual(set(actual), set(expected))

    def assertLocationsMatch(self, expected_locations):
        collection = LocationCollection(self.domain)
        actual = collection.locations
        actual = [
            (l.site_code, l.parent.site_code) if l.parent else (l.site_code, None)
            for l in actual
        ]

        self.assertEqual(set(actual), expected_locations)

    def test_location_creation(self):
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's2'),
            ('city111', 'county11'), ('city112', 'county11'), ('city211', 'county21')
        ]))

    def test_move_county21_to_state1(self):
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

        _loc_id = lambda x: locations_by_code[x].location_id
        move_county21_to_state1 = [
            # (name, site_code, location_type, parent_code, location_id,
            # do_delete, external_id, latitude, longitude, index)
            ('S1', 's1', 'state', '', _loc_id('s1'), False, '', '', '', 0),
            ('S2', 's2', 'state', '', _loc_id('s2'), False, '', '', '', 0),
            ('County11', 'county11', 'county', 's1', _loc_id('county11'), False, '', '', '', 0),
            # change parent_code from s2 -> s1
            ('County21', 'county21', 'county', 's1', _loc_id('county21'), False, '', '', '', 0),
            ('City111', 'city111', 'city', 'county11', _loc_id('city111'), False, '', '', '', 0),
            ('City112', 'city112', 'city', 'county11', _loc_id('city112'), False, '', '', '', 0),
            ('City211', 'city211', 'city', 'county21', _loc_id('city211'), False, '', '', '', 0),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            move_county21_to_state1,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's1'),
            ('city111', 'county11'), ('city112', 'county11'), ('city211', 'county21')
        ]))

    def test_delete_city112(self):
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        delete_city112 = [
            ('S1', 's1', 'state', '', _loc_id('s1'), False, '', '', '', 0),
            ('S2', 's2', 'state', '', _loc_id('s2'), False, '', '', '', 0),
            ('County11', 'county11', 'county', 's1', _loc_id('county11'), False, '', '', '', 0),
            ('County21', 'county21', 'county', 's2', _loc_id('county21'), False, '', '', '', 0),
            ('City111', 'city111', 'city', 'county11', _loc_id('city111'), False, '', '', '', 0),
            # delete city112
            ('City112', 'city112', 'city', 'county11', _loc_id('city112'), True, '', '', '', 0),
            ('City211', 'city211', 'city', 'county21', _loc_id('city211'), False, '', '', '', 0),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_city112,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's2'),
            ('city111', 'county11'), ('city211', 'county21')
        ]))

    def test_invalid_tree(self):
        # Invalid location upload should not pass or affect existing location structure
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        delete_s2 = [
            ('S1', 's1', 'state', '', _loc_id('s1'), False, '', '', '', 0),
            # delete s2, but don't delete its descendatns. This is invalid
            ('S2', 's2', 'state', '', _loc_id('s2'), True, '', '', '', 0),
            ('County11', 'county11', 'county', 's1', _loc_id('county11'), False, '', '', '', 0),
            ('County21', 'county21', 'county', 's2', _loc_id('county21'), False, '', '', '', 0),
            ('City111', 'city111', 'city', 'county11', _loc_id('city111'), False, '', '', '', 0),
            ('City112', 'city112', 'city', 'county11', _loc_id('city112'), False, '', '', '', 0),
            ('City211', 'city211', 'city', 'county21', _loc_id('city211'), False, '', '', '', 0),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_s2,
        )

        self.assertNotEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        # Since there were errors, the location tree should be as it was
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's2'),
            ('city111', 'county11'), ('city112', 'county11'), ('city211', 'county21')
        ]))

    def test_edit_by_sitecode(self):
        # Locations can be referred by site_code and empty location_id
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        move_county21_to_state1 = [
            ('S1', '', 'state', '', _loc_id('s1'), False, '', '', '', 0),
            ('S2', '', 'state', '', _loc_id('s2'), False, '', '', '', 0),
            ('County11', '', 'county', 's1', _loc_id('county11'), False, '', '', '', 0),
            ('County21', '', 'county', 's1', _loc_id('county21'), False, '', '', '', 0),
            ('City111', '', 'city', 'county11', _loc_id('city111'), False, '', '', '', 0),
            ('City112', '', 'city', 'county11', _loc_id('city112'), False, '', '', '', 0),
            ('City211', '', 'city', 'county21', _loc_id('city211'), False, '', '', '', 0),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,  # No change to types
            move_county21_to_state1,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's1'),
            ('city111', 'county11'), ('city112', 'county11'), ('city211', 'county21')
        ]))

    def test_edit_by_location_id(self):
        # Locations can be referred by location_id and empty site_code
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        move_county21_to_state1 = [
            ('S1', 's1', 'state', '', '', False, '', '', '', 0),
            ('S2', 's2', 'state', '', '', False, '', '', '', 0),
            ('County11', 'county11', 'county', 's1', '', False, '', '', '', 0),
            # change parent_code from s2 -> s1
            ('County21', 'county21', 'county', 's1', '', False, '', '', '', 0),
            ('City111', 'city111', 'city', 'county11', '', False, '', '', '', 0),
            ('City112', 'city112', 'city', 'county11', '', False, '', '', '', 0),
            ('City211', 'city211', 'city', 'county21', '', False, '', '', '', 0),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,  # No change to types
            move_county21_to_state1,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's1'),
            ('city111', 'county11'), ('city112', 'county11'), ('city211', 'county21')
        ]))

    def test_delete_city_type_valid(self):
        # delete a location type and locations of that type
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        delete_city_types = [
            ('State', 'state', '', False, False, False, '', '', 0),
            ('County', 'county', 'state', False, False, True, '', '', 0),
            ('City', 'city', 'county', True, True, False, '', '', 0),
        ]
        delete_cities_locations = [
            ('S1', 's1', 'state', '', '', False, '', '', '', 0),
            ('S2', 's2', 'state', '', '', False, '', '', '', 0),
            ('County11', 'county11', 'county', 's1', '', False, '', '', '', 0),
            ('County21', 'county21', 'county', 's2', '', False, '', '', '', 0),
            # delete locations of type 'city'
            ('City111', 'city111', 'city', 'county11', '', True, '', '', '', 0),
            ('City112', 'city112', 'city', 'county11', '', True, '', '', '', 0),
            ('City211', 'city211', 'city', 'county21', '', True, '', '', '', 0),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # No change to types
            delete_cities_locations,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(delete_city_types)
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's2'),
        ]))

    def test_delete_city_type_invalid(self):
        # delete a location type but don't delete locations of that type.
        # this is invalid upload and should not go through
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        delete_city_types = [
            ('State', 'state', '', False, False, False, '', '', 0),
            ('County', 'county', 'state', False, False, True, '', '', 0),
            ('City', 'city', 'county', True, True, False, '', '', 0),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # delete city type
            self.basic_tree,  # but don't delete locations of city type
        )

        self.assertNotEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))
