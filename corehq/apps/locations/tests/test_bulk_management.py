# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple, defaultdict

from django.test import SimpleTestCase, TestCase
from mock import MagicMock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tree_utils import TreeError, assert_no_cycles
from corehq.apps.locations.bulk_management import (
    NewLocationImporter,
    LocationTypeStub,
    LocationStub,
    LocationTreeValidator,
    LocationCollection,
)
import six


# These example types and trees mirror the information available in the upload files
from corehq.apps.locations.util import get_location_data_model

NOT_PROVIDED = LocationStub.NOT_PROVIDED

FLAT_LOCATION_TYPES = [
    # name, code, parent_code, do_delete, shares_cases, view_descendants, index
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False, False, 0),
    ('County', 'county', 'state', False, False, True, 0),
    ('City', 'city', 'county', False, True, False, 0),
]

DUPLICATE_TYPE_CODES = [
    # ('name', 'code', 'parent_code', 'shares_cases', 'view_descendants'),
    ('State', 'state', '', False, False, False, 0),
    ('County', 'county', 'state', False, False, True, 0),
    ('City', 'city', 'county', False, True, False, 0),
    ('Other County', 'county', 'state', False, False, True, 0),
]

CYCLIC_LOCATION_TYPES = [
    ('State', 'state', '', False, False, False, 0),
    ('County', 'county', 'state', False, False, True, 0),
    ('City', 'city', 'county', False, True, False, 0),
    # These three cycle:
    ('Region', 'region', 'village', False, False, False, 0),
    ('District', 'district', 'region', False, False, True, 0),
    ('Village', 'village', 'district', False, True, False, 0),
]


# external_id, latitude, longitude, custom_data, index, location_data_model
extra_stub_args = ('', '', '', NOT_PROVIDED, 0, None)

BASIC_LOCATION_TREE = [
    # (name, site_code, location_type, parent_code, location_id,
    # do_delete, external_id, latitude, longitude, index)
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', False) + extra_stub_args,
    ('Boston', 'boston', 'city', 'suffolk', '2346', False) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('Florida', 'florida', 'state', '', '5432', False) + extra_stub_args,
    ('Duval', 'duval', 'county', 'florida', '5433', False) + extra_stub_args,
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False) + extra_stub_args,
]


MOVE_SUFFOLK_TO_FLORIDA = [
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    # this is the only changed line (parent is changed to florida)
    ('Suffolk', 'suffolk', 'county', 'florida', '2345', False) + extra_stub_args,
    ('Boston', 'boston', 'city', 'suffolk', '2346', False) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('Florida', 'florida', 'state', '', '5432', False) + extra_stub_args,
    ('Duval', 'duval', 'county', 'florida', '5433', False) + extra_stub_args,
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False) + extra_stub_args,
]

DELETE_SUFFOLK = [
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    # These next two are marked as 'delete'
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', True) + extra_stub_args,
    ('Boston', 'boston', 'city', 'suffolk', '2346', True) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('Florida', 'florida', 'state', '', '5432', False) + extra_stub_args,
    ('Duval', 'duval', 'county', 'florida', '5433', False) + extra_stub_args,
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False) + extra_stub_args,
]

MAKE_SUFFOLK_A_STATE_INVALID = [
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    # This still lists mass as a parent, which is invalid,
    # plus, Boston (a city), can't have a state as a parent
    ('Suffolk', 'suffolk', 'state', 'mass', '2345', False) + extra_stub_args,
    ('Boston', 'boston', 'city', 'suffolk', '2346', False) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('Florida', 'florida', 'state', '', '5432', False) + extra_stub_args,
    ('Duval', 'duval', 'county', 'florida', '5433', False) + extra_stub_args,
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False) + extra_stub_args,
]

MAKE_SUFFOLK_A_STATE_VALID = [
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    ('Suffolk', 'suffolk', 'state', '', '2345', False) + extra_stub_args,
    ('Boston', 'boston', 'county', 'suffolk', '2346', False) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('Florida', 'florida', 'state', '', '5432', False) + extra_stub_args,
    ('Duval', 'duval', 'county', 'florida', '5433', False) + extra_stub_args,
    ('Jacksonville', 'jacksonville', 'city', 'duval', '5434', False) + extra_stub_args,
]

DUPLICATE_SITE_CODES = [
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    ('Suffolk', 'suffolk', 'county', 'mass', '2345', False) + extra_stub_args,
    ('Boston', 'boston', 'city', 'suffolk', '2346', False) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('East Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
]

SAME_NAME_SAME_PARENT = [
    ('Massachusetts', 'mass', 'state', '', '1234', False) + extra_stub_args,
    ('Middlesex', 'middlesex', 'county', 'mass', '3456', False) + extra_stub_args,
    # These two locations have the same name AND same parent
    ('Cambridge', 'cambridge', 'city', 'middlesex', '3457', False) + extra_stub_args,
    ('Cambridge', 'cambridge2', 'city', 'middlesex', '3458', False) + extra_stub_args,
]

BIG_LOCATION_TREE = [
    # (name, site_code, location_type, parent_code, location_id,
    # do_delete, external_id, latitude, longitude, index)
    ('0', '0', 'city', 'county11', '', False) + extra_stub_args,
    ('1', '1', 'city', 'county11', '', False) + extra_stub_args,
    ('2', '2', 'city', 'county11', '', False) + extra_stub_args,
    ('3', '3', 'city', 'county11', '', False) + extra_stub_args,
    ('4', '4', 'city', 'county11', '', False) + extra_stub_args,
    ('5', '5', 'city', 'county11', '', False) + extra_stub_args,
    ('6', '6', 'city', 'county11', '', False) + extra_stub_args,
    ('7', '7', 'city', 'county11', '', False) + extra_stub_args,
    ('8', '8', 'city', 'county11', '', False) + extra_stub_args,
    ('9', '9', 'city', 'county11', '', False) + extra_stub_args,
    ('10', '10', 'city', 'county11', '', False) + extra_stub_args,
    ('11', '11', 'city', 'county11', '', False) + extra_stub_args,
    ('12', '12', 'city', 'county11', '', False) + extra_stub_args,
    ('13', '13', 'city', 'county11', '', False) + extra_stub_args,
    ('14', '14', 'city', 'county11', '', False) + extra_stub_args,
    ('15', '15', 'city', 'county11', '', False) + extra_stub_args,
    ('16', '16', 'city', 'county11', '', False) + extra_stub_args,
    ('17', '17', 'city', 'county11', '', False) + extra_stub_args,
    ('18', '18', 'city', 'county11', '', False) + extra_stub_args,
    ('19', '19', 'city', 'county11', '', False) + extra_stub_args,
    ('20', '20', 'city', 'county11', '', False) + extra_stub_args,
    ('21', '21', 'city', 'county11', '', False) + extra_stub_args,
    ('22', '22', 'city', 'county11', '', False) + extra_stub_args,
    ('23', '23', 'city', 'county11', '', False) + extra_stub_args,
    ('24', '24', 'city', 'county11', '', False) + extra_stub_args,
    ('25', '25', 'city', 'county11', '', False) + extra_stub_args,
    ('26', '26', 'city', 'county11', '', False) + extra_stub_args,
    ('27', '27', 'city', 'county11', '', False) + extra_stub_args,
    ('28', '28', 'city', 'county11', '', False) + extra_stub_args,
    ('29', '29', 'city', 'county11', '', False) + extra_stub_args,
    ('30', '30', 'city', 'county11', '', False) + extra_stub_args,
    ('31', '31', 'city', 'county11', '', False) + extra_stub_args,
    ('32', '32', 'city', 'county11', '', False) + extra_stub_args,
    ('33', '33', 'city', 'county11', '', False) + extra_stub_args,
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


class MockLocationStub(LocationStub):
    def lookup_old_collection_data(self, old_collection):
        try:
            return super(MockLocationStub, self).lookup_old_collection_data(old_collection)
        except AttributeError:
            # This will happen if the LocationStub is not new and an old_collection is not given
            self.db_object = MagicMock()


def get_validator(location_types, locations, old_collection=None):
    validator = LocationTreeValidator(
        [LocationTypeStub(*loc_type) for loc_type in location_types],
        [MockLocationStub(*loc) for loc in locations],
        old_collection=old_collection
    )
    return validator


MockCollection = namedtuple(
    'MockCollection',
    'types locations locations_by_id locations_by_site_code domain_name '
    'custom_data_validator locations_by_parent_code')


def make_collection(types, locations):
    types = [LocationTypeStub(*loc_type) for loc_type in types]

    locations = [LocationStub(*loc) for loc in locations]

    def locations_by_parent_code():
        locs_by_parent = defaultdict(list)
        for loc in locations:
            locs_by_parent[loc.parent_code].append(loc)
        return locs_by_parent

    return MockCollection(
        types=types,
        locations=locations,
        locations_by_id={l.location_id: l for l in locations},
        locations_by_site_code={l.site_code: l for l in locations},
        locations_by_parent_code=locations_by_parent_code(),
        custom_data_validator=None,
        domain_name='location-bulk-management',
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
        old_types = FLAT_LOCATION_TYPES + [('Galaxy', 'galaxy', '', False, False, False, 0)]

        old_collection = make_collection(old_types, BASIC_LOCATION_TREE)
        validator = get_validator(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE, old_collection)

        missing_type_errors = validator._check_unlisted_type_codes()
        self.assertEqual(len(missing_type_errors), 1)
        self.assertEqual(len(validator.errors), 1)
        self.assertIn('galaxy', missing_type_errors[0])

    def test_missing_location_ids(self):
        # not all locations need to be specified in the upload
        old_locations = (
            BASIC_LOCATION_TREE +
            [('extra_state', 'ex_code', 'state', '', 'ex_id', False) + extra_stub_args]
        )
        old_collection = make_collection(FLAT_LOCATION_TYPES, old_locations)
        validator = get_validator(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE, old_collection)
        self.assertEqual(len(validator.errors), 0)

    def test_unknown_location_ids(self):
        # all locations in the domain should be listed in given excel

        old_collection = make_collection(FLAT_LOCATION_TYPES, BASIC_LOCATION_TREE)
        new_locations = (
            BASIC_LOCATION_TREE +
            [('extra_state', 'ex_code', 'state', '', 'ex_id', False) + extra_stub_args]
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
        ('S1', 's1', 'state', '', '', False) + extra_stub_args,
        ('S2', 's2', 'state', '', '', False) + extra_stub_args,
        ('County11', 'county11', 'county', 's1', '', False) + extra_stub_args,
        ('County21', 'county21', 'county', 's2', '', False) + extra_stub_args,
        ('City111', 'city111', 'city', 'county11', '', False) + extra_stub_args,
        ('City112', 'city112', 'city', 'county11', '', False) + extra_stub_args,
        ('City211', 'city211', 'city', 'county21', '', False) + extra_stub_args,
    ]

    @classmethod
    def as_pairs(cls, tree):
        # returns list of (site_code, parent_code) tuples
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
                           _i, parent_type=None):
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
        def _make_loc(name, site_code, location_type, parent_code, location_id,
                      do_delete, external_id, latitude, longitude, custom_data,
                      index, location_data_model, parent=None):
            _type = lt_by_code.get(location_type)
            loc = SQLLocation(
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
            chunk_size=10
        )
        result = importer.run()
        return result

    def assertLocationTypesMatch(self, expected_types):
        # Makes sure that the set of all location types in the domain matches
        # the passed-in location types
        actual_types = self.domain.location_types
        # covert it to the format of passed-in tuples
        actual = [
            (lt.name, lt.code,
             lt.parent_type.code if lt.parent_type else '', False, lt.shares_cases or False,
             lt.view_descendants)
            for lt in actual_types
        ]
        expected = []
        for lt in expected_types:
            do_delete = lt[3]
            if not do_delete:
                # drop index
                expected.append(tuple(lt[0:-1]))

        self.assertEqual(set(actual), set(expected))

    def assertLocationsMatch(self, expected_locations, check_attr='site_code'):
        collection = LocationCollection(self.domain)

        actual = []
        for l in collection.locations:
            attr = getattr(l, check_attr)
            if l.parent:
                parent = l.parent.site_code
            else:
                parent = None
            actual.append((attr, parent))

        self.assertEqual(set(actual), expected_locations)
        self.assertMpttDescendants(expected_locations)

    def assertMpttDescendants(self, pairs):
        # Given list of (child, parent), check that for each location
        # SQLLocation.get_descendants is same as calculated descendants

        from collections import defaultdict

        # index by parent, to calculate descendants
        by_parent = defaultdict(list)
        for (child, parent) in pairs:
            by_parent[parent].append(child)

        descendants = defaultdict(list)

        def get_descendants(l):
            if descendants[l]:
                return descendants[l]

            to_ret = []
            children = by_parent[l]
            for child in children:
                to_ret = to_ret + get_descendants(child)
            return children + to_ret

        # calculate descendants for each location
        for (child, pair) in pairs:
            descendants[child] = get_descendants(child)

        # for each location assert that calculated and expected get_descendants are equal
        for (l, desc) in six.iteritems(descendants):
            q = SQLLocation.objects.filter(site_code=l)
            loc = q[0] if q else None

            actual = [i.site_code for i in loc.get_descendants()] if loc else []
            self.assertEqual(set(actual), set(desc))

    def test_location_creation(self):
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_int_datatype(self):
        data = [
            ('S1', 1, 'state', '', '', False, '12', '', '2345', NOT_PROVIDED, 0, None),
            ('S2', 2, 'state', '', '', False, '12', '', '2345', NOT_PROVIDED, 0, None),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            data
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([('1', None), ('2', None)]))

    def test_data_format(self):
        data = [
            ('S1', '1', 'state', '', '', False, '12', 'not-lat', '2345', NOT_PROVIDED, 0, None),
            ('S2', '2', 'state', '', '', False, '12', '3434', '2345', NOT_PROVIDED, 0, None),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            data
        )
        self.assertEqual(len(result.errors), 1)
        self.assertTrue('lat' in result.errors[0])

    def test_move_county21_to_state1(self):
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

        _loc_id = lambda x: locations_by_code[x].location_id
        move_county21_to_state1 = [
            # (name, site_code, location_type, parent_code, location_id,
            # do_delete, external_id, latitude, longitude, index)
            ('S1', 's1', 'state', '', _loc_id('s1'), False) + extra_stub_args,
            ('S2', 's2', 'state', '', _loc_id('s2'), False) + extra_stub_args,
            ('County11', 'county11', 'county', 's1', _loc_id('county11'), False) + extra_stub_args,
            # change parent_code from s2 -> s1
            ('County21', 'county21', 'county', 's1', _loc_id('county21'), False) + extra_stub_args,
            ('City111', 'city111', 'city', 'county11', _loc_id('city111'), False) + extra_stub_args,
            ('City112', 'city112', 'city', 'county11', _loc_id('city112'), False) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', _loc_id('city211'), False) + extra_stub_args,
            # create new city
            ('City311', 'city311', 'city', 'county11', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            move_county21_to_state1,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(move_county21_to_state1))

    def test_delete_county11(self):
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        delete_county11 = [
            ('S1', 's1', 'state', '', _loc_id('s1'), False) + extra_stub_args,
            ('S2', 's2', 'state', '', _loc_id('s2'), False) + extra_stub_args,
            ('County11', 'county11', 'county', 's1', _loc_id('county11'), True) + extra_stub_args,
            ('County21', 'county21', 'county', 's2', _loc_id('county21'), False) + extra_stub_args,
            ('City111', 'city111', 'city', 'county11', _loc_id('city111'), True) + extra_stub_args,
            ('City112', 'city112', 'city', 'county11', _loc_id('city112'), True) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', _loc_id('city211'), False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_county11,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(delete_county11))

    def test_invalid_tree(self):
        # Invalid location upload should not pass or affect existing location structure
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        delete_s2 = [
            ('S1', 's1', 'state', '', _loc_id('s1'), False) + extra_stub_args,
            # delete s2, but don't delete its descendatns. This is invalid
            ('S2', 's2', 'state', '', _loc_id('s2'), True) + extra_stub_args,
            ('County11', 'county11', 'county', 's1', _loc_id('county11'), False) + extra_stub_args,
            ('County21', 'county21', 'county', 's2', _loc_id('county21'), False) + extra_stub_args,
            ('City111', 'city111', 'city', 'county11', _loc_id('city111'), False) + extra_stub_args,
            ('City112', 'city112', 'city', 'county11', _loc_id('city112'), False) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', _loc_id('city211'), False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_s2,
        )

        self.assertNotEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        # Since there were errors, the location tree should be as it was
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_edit_by_location_id(self):
        # Locations can be referred by location_id and empty site_code
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        move_county21_to_state1 = [
            ('S1', '', 'state', '', _loc_id('s1'), False) + extra_stub_args,
            ('S2', '', 'state', '', _loc_id('s2'), False) + extra_stub_args,
            ('County11', '', 'county', 's1', _loc_id('county11'), False) + extra_stub_args,
            ('County21', '', 'county', 's1', _loc_id('county21'), False) + extra_stub_args,
            ('City111', '', 'city', 'county11', _loc_id('city111'), False) + extra_stub_args,
            ('City112', '', 'city', 'county11', _loc_id('city112'), False) + extra_stub_args,
            ('City211', '', 'city', 'county21', _loc_id('city211'), False) + extra_stub_args,
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

    def test_edit_by_sitecode(self):
        # Locations can be referred by site_code and empty location_id
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        move_county21_to_state1 = [
            ('S1', 's1', 'state', '', '', False) + extra_stub_args,
            ('S2', 's2', 'state', '', '', False) + extra_stub_args,
            ('County11', 'county11', 'county', 's1', '', False) + extra_stub_args,
            # change parent_code from s2 -> s1
            ('County21', 'county21', 'county', 's1', '', False) + extra_stub_args,
            ('City111', 'city111', 'city', 'county11', '', False) + extra_stub_args,
            ('City112', 'city112', 'city', 'county11', '', False) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,  # No change to types
            move_county21_to_state1,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(move_county21_to_state1))

    def test_delete_city_type_valid(self):
        # delete a location type and locations of that type
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        delete_city_types = [
            ('State', 'state', '', False, False, False, 0),
            ('County', 'county', 'state', False, False, True, 0),
            ('City', 'city', 'county', True, True, False, 0),
        ]
        delete_cities_locations = [
            ('S1', 's1', 'state', '', '', False) + extra_stub_args,
            ('S2', 's2', 'state', '', '', False) + extra_stub_args,
            ('County11', 'county11', 'county', 's1', '', False) + extra_stub_args,
            ('County21', 'county21', 'county', 's2', '', False) + extra_stub_args,
            # delete locations of type 'city'
            ('City111', 'city111', 'city', 'county11', '', True) + extra_stub_args,
            ('City112', 'city112', 'city', 'county11', '', True) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', '', True) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # No change to types
            delete_cities_locations,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(delete_city_types)
        self.assertLocationsMatch(self.as_pairs(delete_cities_locations))

    def test_delete_everything(self):
        # delete everything
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        delete_city_types = [
            ('State', 'state', '', True, False, False, 0),
            ('County', 'county', 'state', True, False, True, 0),
            ('City', 'city', 'county', True, True, False, 0),
        ]
        delete_cities_locations = [
            ('S1', 's1', 'state', '', '', True) + extra_stub_args,
            ('S2', 's2', 'state', '', '', True) + extra_stub_args,
            ('County11', 'county11', 'county', 's1', '', True) + extra_stub_args,
            ('County21', 'county21', 'county', 's2', '', True) + extra_stub_args,
            ('City111', 'city111', 'city', 'county11', '', True) + extra_stub_args,
            ('City112', 'city112', 'city', 'county11', '', True) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', '', True) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # No change to types
            delete_cities_locations,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(delete_city_types)
        self.assertLocationsMatch(self.as_pairs(delete_cities_locations))

    def test_delete_city_type_invalid(self):
        # delete a location type but don't delete locations of that type.
        # this is invalid upload and should not go through
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        delete_city_types = [
            ('State', 'state', '', False, False, False, 0),
            ('County', 'county', 'state', False, False, True, 0),
            ('City', 'city', 'county', True, True, False, 0),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # delete city type
            self.basic_tree,  # but don't delete locations of city type
        )

        self.assertNotEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_edit_names(self):
        # metadata attributes like 'name' can be updated
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))
        _loc_id = lambda x: locations_by_code[x].location_id
        change_names = [
            # (name, site_code, location_type, parent_code, location_id,
            # do_delete, external_id, latitude, longitude, index)
            # changing names
            ('State 1', '', 'state', '', _loc_id('s1'), False) + extra_stub_args,
            ('State 2', '', 'state', '', _loc_id('s2'), False) + extra_stub_args,
            ('County 11', '', 'county', 's1', _loc_id('county11'), False) + extra_stub_args,
            ('County 21', '', 'county', 's2', _loc_id('county21'), False) + extra_stub_args,
            ('City 111', '', 'city', 'county11', _loc_id('city111'), False) + extra_stub_args,
            ('City 112', '', 'city', 'county11', _loc_id('city112'), False) + extra_stub_args,
            ('City 211', '', 'city', 'county21', _loc_id('city211'), False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))
        self.assertLocationsMatch(set([
            ('State 1', None), ('State 2', None), ('County 11', 's1'), ('County 21', 's2'),
            ('City 111', 'county11'), ('City 112', 'county11'), ('City 211', 'county21')
        ]), check_attr='name')

    def test_partial_type_edit(self):
        # edit a subset of types
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

        edit_types = [
            ('State', 'state', '', False, False, False, 0),
            # change name of this type
            ('District', 'county', 'state', False, False, False, 0),
            ('City', 'city', 'county', False, False, False, 0),
        ]

        result = self.bulk_update_locations(
            edit_types,
            self.basic_tree,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(edit_types)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_rearrange_locations(self):
        # a total rearrangement like reversing the tree can be done
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        reverse_order = [
            ('State', 'state', 'county', False, False, False, 0),
            ('County', 'county', 'city', False, False, False, 0),
            ('City', 'city', '', False, False, False, 0),
        ]
        edit_types_of_locations = [
            # change parent from TOP to county
            ('S1', 's1', 'state', 'county11', '', False) + extra_stub_args,
            ('S2', 's2', 'state', 'county11', '', False) + extra_stub_args,
            # change parent from state to city
            ('County11', 'county11', 'county', 'city111', '', False) + extra_stub_args,
            ('County21', 'county21', 'county', 'city111', '', False) + extra_stub_args,
            # make these two TOP locations
            ('City111', 'city111', 'city', '', '', False) + extra_stub_args,
            ('City112', 'city112', 'city', '', '', False) + extra_stub_args,
            # delete this
            ('City211', 'city211', 'city', 'county21', '', True) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            reverse_order,  # No change to types
            edit_types_of_locations,  # This is the desired end result
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(reverse_order)
        self.assertLocationsMatch(self.as_pairs(edit_types_of_locations))

    def test_swap_parents(self):
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        original = [
            ('State 1', 's1', 'state', '', '', False) + extra_stub_args,
            ('State 2', 's2', 'state', '', '', False) + extra_stub_args,
            ('County 11', 'c1', 'county', 's1', '', False) + extra_stub_args,
            ('County 21', 'c2', 'county', 's2', '', False) + extra_stub_args,
        ]
        self.create_locations(original, lt_by_code)

        swap_parents = [
            ('State 1', 's1', 'state', '', '', False) + extra_stub_args,
            ('State 2', 's2', 'state', '', '', False) + extra_stub_args,
            ('County 11', 'c1', 'county', 's2', '', False) + extra_stub_args,
            ('County 21', 'c2', 'county', 's1', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            swap_parents,
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(swap_parents))

    def test_custom_data(self):
        data_model = get_location_data_model(self.domain.name)
        tree = [
            ('省 1', 's1', 'state', '', '', False, '', '', '', {'a': 1}, 0, data_model, False),
            ('County 11', 'c1', 'county', 's1', '', False, '', '', '', {'国际字幕': '试验'}, 0, data_model, False),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(tree))

        locations = SQLLocation.objects.all()
        self.assertEqual(locations[0].metadata, {'a': '1'})  # test that ints are coerced to strings
        self.assertEqual(locations[1].metadata, {'国际字幕': '试验'})

    def test_custom_data_delete_uncategorized(self):
        data_model = get_location_data_model(self.domain.name)

        # setup some metadata
        tree = [
            ('State 1', 's1', 'state', '', '', False, '', '', '', {'a': 1}, 0, data_model, False),
            ('County 11', 'c1', 'county', 's1', '', False, '', '', '', {'b': 'test'}, 0, data_model, False),
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )

        locations = SQLLocation.objects.all()
        self.assertEqual(locations[0].metadata, {'a': '1'})
        self.assertEqual(locations[1].metadata, {'b': 'test'})

        tree = [
            ('State 1', 's1', 'state', '', '', False, '', '', '', {'a': 1}, 0, data_model, True),
            ('County 11', 'c1', 'county', 's1', '', False, '', '', '', {}, 0, data_model, False),
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )

        locations = SQLLocation.objects.all()
        self.assertEqual(locations[0].metadata, {})  # uncategorized data get's removed
        self.assertEqual(locations[1].metadata, {'b': 'test'})  # uncategorized data get's kept

    def test_case_sensitivity(self):
        # site-codes are automatically converted to lower-case
        upper_case = [
            ('State 1', 'S1', 'state', '', '', False) + extra_stub_args,
            ('State 2', 'S2', 'state', '', '', False) + extra_stub_args,
            ('County 11', 'C1', 'county', 's1', '', False) + extra_stub_args,
            ('County 21', 'C2', 'county', 's2', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            upper_case,
        )

        lower_case = [
            ('State 1', 'S1'.lower(), 'state', '', '', False) + extra_stub_args,
            ('State 2', 'S2'.lower(), 'state', '', '', False) + extra_stub_args,
            ('County 11', 'C1'.lower(), 'county', 's1', '', False) + extra_stub_args,
            ('County 21', 'C2'.lower(), 'county', 's2', '', False) + extra_stub_args,
        ]

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(lower_case))

    def test_partial_addition(self):
        # new locations can be added without having to specify all of old ones
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        addition = [
            ('State 3', 's3', 'state', '', '', False) + extra_stub_args,
            ('County 21', 'county3', 'county', 's3', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            addition
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree).union({
            ('s3', None), ('county3', 's3')
        }))

    def test_partial_attribute_edits_by_location_id(self):
        # a subset of locations can be edited and can be referenced by location_id
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        locations_by_code = self.create_locations(self.basic_tree, lt_by_code)

        _loc_id = lambda x: locations_by_code[x].location_id
        change_names = [
            ('My State 1', '', 'state', '', _loc_id('s1'), False) + extra_stub_args,
            ('My County 11', '', 'county', 's1', _loc_id('county11'), False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('My State 1', None), ('S2', None), ('My County 11', 's1'),
            ('County21', 's2'), ('City111', 'county11'), ('City112', 'county11'),
            ('City211', 'county21'),
        }, check_attr='name')

    def test_partial_attribute_edits_by_site_code(self):
        # a subset of locations can be edited and can be referenced by site_code
        lt_by_code = self.create_location_types(FLAT_LOCATION_TYPES)
        self.create_locations(self.basic_tree, lt_by_code)

        change_names = [
            ('My State 1', 's1', 'state', '', '', False) + extra_stub_args,
            ('My County 11', 'county11', 'county', 's1', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('My State 1', None), ('S2', None), ('My County 11', 's1'),
            ('County21', 's2'), ('City111', 'county11'), ('City112', 'county11'),
            ('City211', 'county21'),
        }, check_attr='name')

    def test_partial_parent_edits(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        change_parents = [
            ('County 21', 'county21', 'county', 's1', '', False) + extra_stub_args,
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_parents
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('s1', None), ('s2', None), ('county11', 's1'),
            ('county21', 's1'), ('city111', 'county11'), ('city112', 'county11'),
            ('city211', 'county21'),
        })

    def test_partial_parent_edits_invalid(self):
        # can't set invalid type location for a parent location
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        change_parents = [
            # city type can't have parent of state type
            ('City211', 'city211', 'city', 's1', '', False) + extra_stub_args,
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_parents
        )

        self.assertNotEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_partial_delete_children(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        # deleting location that has children, if listing all of its children is valid
        delete = [
            ('County 21', 'county21', 'city', 's2', '', True) + extra_stub_args,
            ('City211', 'city211', 'city', 'county11', '', True) + extra_stub_args,
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree) - {
            ('city211', 'county21'), ('county21', 's2')
        })

        # deleting location if it doesn't have children should work
        delete = [
            ('City111', 'city111', 'city', 'county11', '', True) + extra_stub_args,
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )

        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree) - {
            ('city211', 'county21'), ('county21', 's2'), ('city111', 'county11')
        })

    def test_partial_delete_children_invalid(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        # deleting location that has children, without listing all of its children is invalid
        delete = [
            ('County 21', 'county21', 'city', 's2', '', True) + extra_stub_args,
            # city211 is missing
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )
        self.assertNotEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_large_upload(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            BIG_LOCATION_TREE
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree + BIG_LOCATION_TREE))

    def test_new_root(self):
        # new locations can be added without having to specify all of old ones
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        upload = [
            ('S1', 's1', 'city', 'county11', '', False) + extra_stub_args,
            ('S2', 's2', 'city', 'county11', '', False) + extra_stub_args,
            ('County11', 'county11', 'county', 'city111', '', False) + extra_stub_args,
            ('County21', 'county21', 'county', 'city111', '', False) + extra_stub_args,
            ('City111', 'city111', 'state', '', '', False) + extra_stub_args,
            ('City112', 'city112', 'state', '', '', False) + extra_stub_args,
            ('City211', 'city211', 'state', '', '', False) + extra_stub_args,
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            upload
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(upload))

    def test_delete_unsaved(self):
        self.create_location_types(FLAT_LOCATION_TYPES)

        basic_tree = [
            # (name, site_code, location_type, parent_code, location_id,
            # do_delete, external_id, latitude, longitude, index)
            ('S2', 's2', 'state', '', '', False) + extra_stub_args,
            ('County21', 'county21', 'county', 's2', '', False) + extra_stub_args,
            ('City211', 'city211', 'city', 'county21', '', True) + extra_stub_args,  # delete unsaved
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            basic_tree
        )
        self.assertEqual(result.errors, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(basic_tree[:-1]))
