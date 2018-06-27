# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

import attr
from django.test import SimpleTestCase, TestCase
from mock import MagicMock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..bulk_management import (
    NewLocationImporter,
    LocationTypeData,
    LocationStub,
    LocationTreeValidator,
    LocationCollection,
)
from ..const import ROOT_LOCATION_TYPE
from ..models import LocationType, SQLLocation
from ..tree_utils import TreeError, assert_no_cycles
from ..util import get_location_data_model
from .util import LocationHierarchyPerTest
import six
from six.moves import range

# These example types and trees mirror the information available in the upload files

NOT_PROVIDED = LocationStub.NOT_PROVIDED

FLAT_LOCATION_TYPES = [
    LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, False, False, False, 0),
    LocationTypeData('County', 'county', 'state', False, False, True, 0),
    LocationTypeData('City', 'city', 'county', False, True, False, 0),
]

DUPLICATE_TYPE_CODES = [
    LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, False, False, False, 0),
    LocationTypeData('County', 'county', 'state', False, False, True, 0),
    LocationTypeData('City', 'city', 'county', False, True, False, 0),
    LocationTypeData('Other County', 'county', 'state', False, False, True, 0),
]

CYCLIC_LOCATION_TYPES = [
    LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, False, False, False, 0),
    LocationTypeData('County', 'county', 'state', False, False, True, 0),
    LocationTypeData('City', 'city', 'county', False, True, False, 0),
    # These three cycle:
    LocationTypeData('Region', 'region', 'village', False, False, False, 0),
    LocationTypeData('District', 'district', 'region', False, False, True, 0),
    LocationTypeData('Village', 'village', 'district', False, True, False, 0),
]


def LocStub(
    name,
    site_code,
    location_type,
    parent_code,
    location_id='',
    do_delete=False,
    external_id='',
    latitude='',
    longitude='',
    custom_data=NOT_PROVIDED,
    index=0,
    data_model=None,
    delete_uncategorized_data=False,
):
    stub_tuple = (
        name,
        site_code,
        location_type,
        parent_code,
        location_id,
        do_delete,
        external_id,
        latitude,
        longitude,
        custom_data,
        index,
        data_model,
    )
    if delete_uncategorized_data:
        return stub_tuple + (True,)
    return stub_tuple


def _codify(items):
    return {it.site_code: it for it in items}


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

    def lookup_old_collection_data(self, old_collection, locs_by_code):
        if not self.is_new:
            self.db_object = MagicMock()


@attr.s
class TestLocationCollection(LocationCollection):

    domain_name = 'location-bulk-management'

    types = attr.ib(factory=list)
    locations = attr.ib(factory=list)

    def custom_data_validator(self):
        return lambda data: False


class IngoreOldLocationTreeValidator(LocationTreeValidator):
    """Skip checks that depend on self.old_collection"""

    def _check_required_locations_missing(self):
        return []

    def _check_unlisted_type_codes(self):
        return []

    def _check_unknown_location_ids(self):
        return []


def get_validator(location_types, locations, old_collection=None):
    if old_collection is None:
        StubClass = MockLocationStub
        old_collection = TestLocationCollection()
        Validator = IngoreOldLocationTreeValidator
    else:
        StubClass = LocationStub
        Validator = LocationTreeValidator
    return Validator(
        location_types,
        [StubClass(*loc) for loc in locations],
        old_collection=old_collection,
        user=None,  # TODO pass in a real user
    )


def make_collection(types, locations):
    types_by_code = {t.code: t for t in types}
    # make LocationTypeStub more like a real LocationType
    locations = [LocationStub(*loc) for loc in locations]
    locations_by_code = {loc.site_code: loc for loc in locations}
    idgen = iter(range(len(locations)))
    # make LocationStub more like a real SQLLocation
    for loc in locations:
        loc.id = next(idgen)
        loc.location_type = types_by_code[loc.location_type]
        if loc.parent_code == ROOT_LOCATION_TYPE:
            loc.parent_id = None
        else:
            loc.parent_id = locations_by_code[loc.parent_code].id
        assert loc.custom_data == NOT_PROVIDED, loc.custom_data
        loc.metadata = {}
        loc.full_clean = lambda **k: None

    return TestLocationCollection(types, locations)


def assert_errors(result, expected_errors):
    """Assert that result errors match expected errors

    Uses substring matching to coorelate expected to actual errrors.

    Raise if any expected error is not matched or if any actual
    errors are found that were not matched by an expected error.

    This function has O(n**2) complexity on the number of errors.
    """
    def find_and_remove(expected_error):
        for i, actual_error in enumerate(actual_errors):
            if expected_error in actual_error:
                del actual_errors[i]
                return True
        return False

    actual_errors = list(result.errors)
    missing_errors = [e for e in expected_errors if not find_and_remove(e)]
    errors = []
    if missing_errors:
        errors.append("missing expected errors:")
        errors.extend(missing_errors)
    if actual_errors:
        if errors:
            errors.append("")
        errors.append("unexpected errors:")
        errors.extend(actual_errors)
    assert not errors, "\n".join(errors)


class TestTreeValidator(SimpleTestCase):
    basic_location_tree = [
        LocStub('Massachusetts', 'mass', 'state', '', '1234'),
        LocStub('Suffolk', 'suffolk', 'county', 'mass', '2345'),
        LocStub('Boston', 'boston', 'city', 'suffolk', '2346'),
        LocStub('Middlesex', 'middlesex', 'county', 'mass', '3456'),
        LocStub('Cambridge', 'cambridge', 'city', 'middlesex', '3457'),
        LocStub('Florida', 'florida', 'state', '', '5432'),
        LocStub('Duval', 'duval', 'county', 'florida', '5433'),
        LocStub('Jacksonville', 'jacksonville', 'city', 'duval', '5434'),
    ]

    def test_good_location_set(self):
        validator = get_validator(FLAT_LOCATION_TYPES, self.basic_location_tree)
        assert_errors(validator, [])

    def test_cyclic_location_types(self):
        validator = get_validator(CYCLIC_LOCATION_TYPES, self.basic_location_tree)
        self.assertEqual(len(validator._validate_types_tree()), 3)

    def test_bad_type_change(self):
        make_suffolk_a_state_invalid = [
            LocStub('Massachusetts', 'mass', 'state', '', '1234'),
            # This still lists mass as a parent, which is invalid,
            # plus, Boston (a city), can't have a state as a parent
            LocStub('Suffolk', 'suffolk', 'state', 'mass', '2345'),
            LocStub('Boston', 'boston', 'city', 'suffolk', '2346'),
            LocStub('Middlesex', 'middlesex', 'county', 'mass', '3456'),
            LocStub('Cambridge', 'cambridge', 'city', 'middlesex', '3457'),
            LocStub('Florida', 'florida', 'state', '', '5432'),
            LocStub('Duval', 'duval', 'county', 'florida', '5433'),
            LocStub('Jacksonville', 'jacksonville', 'city', 'duval', '5434'),
        ]
        validator = get_validator(FLAT_LOCATION_TYPES, make_suffolk_a_state_invalid)

        assert_errors(validator, [
            "'suffolk' is a 'state' and should not have a parent",
            "'boston' is a 'city', so it should have a parent that is a 'county'",
        ])

    def test_good_type_change(self):
        make_suffolk_a_state_valid = [
            LocStub('Massachusetts', 'mass', 'state', '', '1234'),
            LocStub('Suffolk', 'suffolk', 'state', '', '2345'),
            LocStub('Boston', 'boston', 'county', 'suffolk', '2346'),
            LocStub('Middlesex', 'middlesex', 'county', 'mass', '3456'),
            LocStub('Cambridge', 'cambridge', 'city', 'middlesex', '3457'),
            LocStub('Florida', 'florida', 'state', '', '5432'),
            LocStub('Duval', 'duval', 'county', 'florida', '5433'),
            LocStub('Jacksonville', 'jacksonville', 'city', 'duval', '5434'),
        ]
        validator = get_validator(FLAT_LOCATION_TYPES, make_suffolk_a_state_valid)
        assert_errors(validator, [])

    def test_duplicate_type_codes(self):
        validator = get_validator(DUPLICATE_TYPE_CODES, self.basic_location_tree)
        assert_errors(validator, ["type code 'county' is used 2 times"])

    def test_duplicate_location(self):
        duplicate_site_codes = [
            LocStub('Massachusetts', 'mass', 'state', '', '1234'),
            LocStub('Suffolk', 'suffolk', 'county', 'mass', '2345'),
            LocStub('Boston', 'boston', 'city', 'suffolk', '2346'),
            LocStub('Middlesex', 'middlesex', 'county', 'mass', '3456'),
            LocStub('Cambridge', 'cambridge', 'city', 'middlesex', '3457'),
            LocStub('East Cambridge', 'cambridge', 'city', 'middlesex', '3457'),
        ]
        validator = get_validator(FLAT_LOCATION_TYPES, duplicate_site_codes)
        assert_errors(validator, [
            "site_code 'cambridge' is used 2 times",
            "location_id '3457' is listed 2 times",
        ])

    def test_same_name_same_parent(self):
        same_name_same_parent = [
            LocStub('Massachusetts', 'mass', 'state', '', '1234'),
            LocStub('Middlesex', 'middlesex', 'county', 'mass', '3456'),
            # These two locations have the same name AND same parent
            LocStub('Cambridge', 'cambridge', 'city', 'middlesex', '3457'),
            LocStub('Cambridge', 'cambridge2', 'city', 'middlesex', '3458'),
        ]
        validator = get_validator(FLAT_LOCATION_TYPES, same_name_same_parent)
        assert_errors(validator, [
            " 2 locations with the name 'Cambridge' under the parent 'middlesex'"
        ])

    def test_missing_types(self):
        # all types in the domain should be listed in given excel
        old_types = FLAT_LOCATION_TYPES + [LocationTypeData('Galaxy', 'galaxy', ROOT_LOCATION_TYPE, False, False, False, 0)]

        old_collection = make_collection(old_types, self.basic_location_tree)
        validator = get_validator(FLAT_LOCATION_TYPES, self.basic_location_tree, old_collection)
        assert_errors(validator, ["type code 'galaxy' is not listed"])

    def test_missing_location_ids(self):
        # not all locations need to be specified in the upload
        old_locations = (
            self.basic_location_tree +
            [LocStub('extra_state', 'ex_code', 'state', '', 'ex_id')]
        )
        old_collection = make_collection(FLAT_LOCATION_TYPES, old_locations)
        validator = get_validator(FLAT_LOCATION_TYPES, self.basic_location_tree, old_collection)
        assert_errors(validator, [])

    def test_unknown_location_ids(self):
        # all locations in the domain should be listed in given excel

        old_collection = make_collection(FLAT_LOCATION_TYPES, self.basic_location_tree)
        new_locations = (
            self.basic_location_tree +
            [LocStub('extra_state', 'ex_code', 'state', '', 'ex_id')]
        )
        validator = get_validator(FLAT_LOCATION_TYPES, new_locations, old_collection)
        assert_errors(validator, ["'id: ex_id' is not found in your domain"])


class UploadTestUtils(object):
    domain = 'test-bulk-management'
    basic_tree = [
        LocStub('S1', 's1', 'state', ''),
        LocStub('S2', 's2', 'state', ''),
        LocStub('County11', 'county11', 'county', 's1'),
        LocStub('County21', 'county21', 'county', 's2'),
        LocStub('City111', 'city111', 'city', 'county11'),
        LocStub('City112', 'city112', 'city', 'county11'),
        LocStub('City211', 'city211', 'city', 'county21'),
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

    def get_loc_id(self, name):
        return self.locations[name].location_id

    def bulk_update_locations(self, types, locations):
        importer = NewLocationImporter(
            self.domain,
            types,
            [LocationStub(*loc) for loc in locations],
            self.user,
            chunk_size=10
        )
        result = importer.run()
        return result

    def assertLocationTypesMatch(self, expected_types):
        # Makes sure that the set of all location types in the domain matches
        # the passed-in location types
        actual_types = self.domain_obj.location_types
        # covert it to the format of passed-in tuples
        actual = [(
            lt.name,
            lt.code,
            lt.parent_type.code if lt.parent_type else ROOT_LOCATION_TYPE,
            False,
            lt.shares_cases or False,
            lt.view_descendants
        ) for lt in actual_types]
        expected = []
        for lt in expected_types:
            do_delete = lt[3]
            if not do_delete:
                # drop index
                expected.append(tuple(lt[0:-1]))

        self.assertEqual(set(actual), set(expected))

    def assertLocationsMatch(self, expected_locations, check_attr='site_code'):
        collection = LocationCollection(self.domain_obj)

        actual = []
        for l in collection.locations:
            attr = getattr(l, check_attr)
            if l.parent:
                parent = l.parent.site_code
            else:
                parent = None
            actual.append((attr, parent))

        self.assertEqual(set(actual), expected_locations)
        self.assertDescendants(expected_locations)

    def assertDescendants(self, pairs):
        # Given list of (child, parent), check that for each location
        # SQLLocation.get_descendants is same as calculated descendants

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


class TestBulkManagementNoInitialLocs(UploadTestUtils, TestCase):

    def setUp(self):
        super(TestBulkManagementNoInitialLocs, self).setUp()
        self.domain_obj = create_domain(self.domain)
        self.user = WebUser.create(self.domain, 'username', 'password')

    def tearDown(self):
        super(TestBulkManagementNoInitialLocs, self).tearDown()
        self.user.delete()
        self.domain_obj.delete()

    def test_location_creation(self):
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_int_datatype(self):
        data = [
            LocStub('S1', 1, 'state', '', external_id='12'),
            LocStub('S2', 2, 'state', '', external_id='12'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            data
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([('1', None), ('2', None)]))

    def test_data_format(self):
        data = [
            LocStub('S1', '1', 'state', '', external_id='12', latitude='not-lat', longitude='2345'),
            LocStub('S2', '2', 'state', '', external_id='12', latitude='3434', longitude='2345'),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            data
        )
        assert_errors(result, ['index 0 should be valid decimal numbers'])

    def test_custom_data(self):
        data_model = get_location_data_model(self.domain)
        tree = [
            LocStub('省 1', 's1', 'state', '',
                    custom_data={'a': 1}, data_model=data_model),
            LocStub('County 11', 'c1', 'county', 's1',
                    custom_data={'国际字幕': '试验'}, data_model=data_model),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(tree))

        locations = _codify(SQLLocation.objects.all())
        self.assertEqual(locations["s1"].metadata, {'a': '1'})  # test that ints are coerced to strings
        self.assertEqual(locations["c1"].metadata, {'国际字幕': '试验'})

    def test_custom_data_delete_uncategorized(self):
        data_model = get_location_data_model(self.domain)

        # setup some metadata
        tree = [
            LocStub('State 1', 's1', 'state', '',
                    custom_data={'a': 1}, data_model=data_model),
            LocStub('County 11', 'c1', 'county', 's1',
                    custom_data={'b': 'test'}, data_model=data_model),
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )

        locations = _codify(SQLLocation.objects.all())
        self.assertEqual(locations["s1"].metadata, {'a': '1'})
        self.assertEqual(locations["c1"].metadata, {'b': 'test'})

        tree = [
            LocStub('State 1', 's1', 'state', '',
                    custom_data={'a': 1}, data_model=data_model,
                    delete_uncategorized_data=True),
            LocStub('County 11', 'c1', 'county', 's1',
                    custom_data={}, data_model=data_model),
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )

        locations = _codify(SQLLocation.objects.all())
        self.assertEqual(locations["s1"].metadata, {})  # uncategorized data get's removed
        self.assertEqual(locations["c1"].metadata, {'b': 'test'})  # uncategorized data get's kept

    def test_case_sensitivity(self):
        # site-codes are automatically converted to lower-case
        upper_case = [
            LocStub('State 1', 'S1', 'state', ''),
            LocStub('State 2', 'S2', 'state', ''),
            LocStub('County 11', 'C1', 'county', 's1'),
            LocStub('County 21', 'C2', 'county', 's2'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            upper_case,
        )

        lower_case = [
            LocStub('State 1', 'S1'.lower(), 'state', ''),
            LocStub('State 2', 'S2'.lower(), 'state', ''),
            LocStub('County 11', 'C1'.lower(), 'county', 's1'),
            LocStub('County 21', 'C2'.lower(), 'county', 's2'),
        ]

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(lower_case))

    def test_partial_addition(self):
        # new locations can be added without having to specify all of old ones
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        addition = [
            LocStub('State 3', 's3', 'state', ''),
            LocStub('County 21', 'county3', 'county', 's3'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            addition
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree).union({
            ('s3', None), ('county3', 's3')
        }))

    def test_partial_parent_edits(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        change_parents = [
            LocStub('County 21', 'county21', 'county', 's1'),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_parents
        )

        assert_errors(result, [])
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
            LocStub('City211', 'city211', 'city', 's1'),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_parents
        )

        assert_errors(result, [
            "'city211' is a 'city', so it should have a parent that is a 'county'",
        ])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_partial_delete_children(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        # deleting location that has children, if listing all of its children is valid
        delete = [
            LocStub('County 21', 'county21', 'city', 's2', do_delete=True),
            LocStub('City211', 'city211', 'city', 'county11', do_delete=True),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree) - {
            ('city211', 'county21'), ('county21', 's2')
        })

        # deleting location if it doesn't have children should work
        delete = [
            LocStub('City111', 'city111', 'city', 'county11', do_delete=True),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )

        assert_errors(result, [])
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
            LocStub('County 21', 'county21', 'city', 's2', do_delete=True),
            # city211 is missing
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )
        assert_errors(result, ["child locations 'city211' are missing"])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_large_upload(self):
        big_location_tree = [
            LocStub('{}'.format(i), '{}'.format(i), 'city', 'county11')
            for i in range(34)
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            big_location_tree
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree + big_location_tree))

    def test_new_root(self):
        # new locations can be added without having to specify all of old ones
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        upload = [
            LocStub('S1', 's1', 'city', 'county11'),
            LocStub('S2', 's2', 'city', 'county11'),
            LocStub('County11', 'county11', 'county', 'city111'),
            LocStub('County21', 'county21', 'county', 'city111'),
            LocStub('City111', 'city111', 'state', ''),
            LocStub('City112', 'city112', 'state', ''),
            LocStub('City211', 'city211', 'state', ''),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            upload
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(upload))


class TestBulkManagementWithInitialLocs(UploadTestUtils, LocationHierarchyPerTest):
    location_type_names = ['State', 'County', 'City']
    location_structure = [
        ('S1', [
            ('County11', [
                ('City111', []),
                ('City112', []),
            ]),
        ]),
        ('S2', [
            ('County21', [
                ('City211', []),
            ]),
        ])
    ]

    def setUp(self):
        super(TestBulkManagementWithInitialLocs, self).setUp()
        self.user = WebUser.create(self.domain, 'username', 'password')
        self.location_types['County'].view_descendants = True
        self.location_types['County'].save()
        self.location_types['City'].shares_cases = True
        self.location_types['City'].save()

    def tearDown(self):
        super(TestBulkManagementWithInitialLocs, self).tearDown()
        self.user.delete()

    def test_move_county21_to_state1(self):
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

        move_county21_to_state1 = [
            LocStub('S1', 's1', 'state', '', self.get_loc_id('S1')),
            LocStub('S2', 's2', 'state', '', self.get_loc_id('S2')),
            LocStub('County11', 'county11', 'county', 's1', self.get_loc_id('County11')),
            # change parent_code from s2 -> s1
            LocStub('County21', 'county21', 'county', 's1', self.get_loc_id('County21')),
            LocStub('City111', 'city111', 'city', 'county11', self.get_loc_id('City111')),
            LocStub('City112', 'city112', 'city', 'county11', self.get_loc_id('City112')),
            LocStub('City211', 'city211', 'city', 'county21', self.get_loc_id('City211')),
            # create new city
            LocStub('City311', 'city311', 'city', 'county11', ''),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            move_county21_to_state1,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(move_county21_to_state1))

    def test_delete_county11(self):
        delete_county11 = [
            LocStub('S1', 's1', 'state', '', self.get_loc_id('S1')),
            LocStub('S2', 's2', 'state', '', self.get_loc_id('S2')),
            LocStub('County11', 'county11', 'county', 's1', self.get_loc_id('County11'), do_delete=True),
            LocStub('County21', 'county21', 'county', 's2', self.get_loc_id('County21')),
            LocStub('City111', 'city111', 'city', 'county11', self.get_loc_id('City111'), do_delete=True),
            LocStub('City112', 'city112', 'city', 'county11', self.get_loc_id('City112'), do_delete=True),
            LocStub('City211', 'city211', 'city', 'county21', self.get_loc_id('City211')),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_county11,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(delete_county11))

    def test_invalid_tree(self):
        # Invalid location upload should not pass or affect existing location structure
        delete_s2 = [
            LocStub('S1', 's1', 'state', '', self.get_loc_id('S1')),
            # delete s2, but don't delete its descendatns. This is invalid
            LocStub('S2', 's2', 'state', '', self.get_loc_id('S2'), do_delete=True),
            LocStub('County11', 'county11', 'county', 's1', self.get_loc_id('County11')),
            LocStub('County21', 'county21', 'county', 's2', self.get_loc_id('County21')),
            LocStub('City111', 'city111', 'city', 'county11', self.get_loc_id('City111')),
            LocStub('City112', 'city112', 'city', 'county11', self.get_loc_id('City112')),
            LocStub('City211', 'city211', 'city', 'county21', self.get_loc_id('City211')),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_s2,
        )

        assert_errors(result, ["points to a location that's being deleted"])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        # Since there were errors, the location tree should be as it was
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_edit_by_location_id(self):
        # Locations can be referred by location_id and empty site_code
        move_county21_to_state1 = [
            LocStub('S1', '', 'state', '', self.get_loc_id('S1')),
            LocStub('S2', '', 'state', '', self.get_loc_id('S2')),
            LocStub('County11', '', 'county', 's1', self.get_loc_id('County11')),
            LocStub('County21', '', 'county', 's1', self.get_loc_id('County21')),
            LocStub('City111', '', 'city', 'county11', self.get_loc_id('City111')),
            LocStub('City112', '', 'city', 'county11', self.get_loc_id('City112')),
            LocStub('City211', '', 'city', 'county21', self.get_loc_id('City211')),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,  # No change to types
            move_county21_to_state1,  # This is the desired end result
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([
            ('s1', None), ('s2', None), ('county11', 's1'), ('county21', 's1'),
            ('city111', 'county11'), ('city112', 'county11'), ('city211', 'county21')
        ]))

    def test_edit_by_sitecode(self):
        # Locations can be referred by site_code and empty location_id
        move_county21_to_state1 = [
            LocStub('S1', 's1', 'state', ''),
            LocStub('S2', 's2', 'state', ''),
            LocStub('County11', 'county11', 'county', 's1'),
            # change parent_code from s2 -> s1
            LocStub('County21', 'county21', 'county', 's1'),
            LocStub('City111', 'city111', 'city', 'county11'),
            LocStub('City112', 'city112', 'city', 'county11'),
            LocStub('City211', 'city211', 'city', 'county21'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,  # No change to types
            move_county21_to_state1,  # This is the desired end result
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(move_county21_to_state1))

    def test_delete_city_type_valid(self):
        # delete a location type and locations of that type
        delete_city_types = [
            LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, False, False, False, 0),
            LocationTypeData('County', 'county', 'state', False, False, True, 0),
            LocationTypeData('City', 'city', 'county', True, True, False, 0),
        ]
        delete_cities_locations = [
            LocStub('S1', 's1', 'state', ''),
            LocStub('S2', 's2', 'state', ''),
            LocStub('County11', 'county11', 'county', 's1'),
            LocStub('County21', 'county21', 'county', 's2'),
            # delete locations of type 'city'
            LocStub('City111', 'city111', 'city', 'county11', do_delete=True),
            LocStub('City112', 'city112', 'city', 'county11', do_delete=True),
            LocStub('City211', 'city211', 'city', 'county21', do_delete=True),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # No change to types
            delete_cities_locations,  # This is the desired end result
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(delete_city_types)
        self.assertLocationsMatch(self.as_pairs(delete_cities_locations))

    def test_delete_everything(self):
        # delete everything
        delete_city_types = [
            LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, True, False, False, 0),
            LocationTypeData('County', 'county', 'state', True, False, True, 0),
            LocationTypeData('City', 'city', 'county', True, True, False, 0),
        ]
        delete_cities_locations = [
            LocStub('S1', 's1', 'state', '', do_delete=True),
            LocStub('S2', 's2', 'state', '', do_delete=True),
            LocStub('County11', 'county11', 'county', 's1', do_delete=True),
            LocStub('County21', 'county21', 'county', 's2', do_delete=True),
            LocStub('City111', 'city111', 'city', 'county11', do_delete=True),
            LocStub('City112', 'city112', 'city', 'county11', do_delete=True),
            LocStub('City211', 'city211', 'city', 'county21', do_delete=True),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # No change to types
            delete_cities_locations,  # This is the desired end result
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(delete_city_types)
        self.assertLocationsMatch(self.as_pairs(delete_cities_locations))

    def test_delete_city_type_invalid(self):
        # delete a location type but don't delete locations of that type.
        # this is invalid upload and should not go through
        delete_city_types = [
            LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, False, False, False, 0),
            LocationTypeData('County', 'county', 'state', False, False, True, 0),
            LocationTypeData('City', 'city', 'county', True, True, False, 0),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # delete city type
            self.basic_tree,  # but don't delete locations of city type
        )

        assert_errors(result, [
            "'city111' in sheet points to a nonexistent or to be deleted location-type",
            "'city112' in sheet points to a nonexistent or to be deleted location-type",
            "'city211' in sheet points to a nonexistent or to be deleted location-type",
        ])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_edit_names(self):
        # metadata attributes like 'name' can be updated
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))
        change_names = [
            # changing names
            LocStub('State 1', '', 'state', '', self.get_loc_id('S1')),
            LocStub('State 2', '', 'state', '', self.get_loc_id('S2')),
            LocStub('County 11', '', 'county', 's1', self.get_loc_id('County11')),
            LocStub('County 21', '', 'county', 's2', self.get_loc_id('County21')),
            LocStub('City 111', '', 'city', 'county11', self.get_loc_id('City111')),
            LocStub('City 112', '', 'city', 'county11', self.get_loc_id('City112')),
            LocStub('City 211', '', 'city', 'county21', self.get_loc_id('City211')),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))
        self.assertLocationsMatch(set([
            ('State 1', None), ('State 2', None), ('County 11', 's1'), ('County 21', 's2'),
            ('City 111', 'county11'), ('City 112', 'county11'), ('City 211', 'county21')
        ]), check_attr='name')

    def test_partial_type_edit(self):
        # edit a subset of types
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

        edit_types = [
            LocationTypeData('State', 'state', ROOT_LOCATION_TYPE, False, False, False, 0),
            # change name of this type
            LocationTypeData('District', 'county', 'state', False, False, False, 0),
            LocationTypeData('City', 'city', 'county', False, False, False, 0),
        ]

        result = self.bulk_update_locations(
            edit_types,
            self.basic_tree,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(edit_types)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_rearrange_locations(self):
        # a total rearrangement like reversing the tree can be done
        reverse_order = [
            LocationTypeData('State', 'state', 'county', False, False, False, 0),
            LocationTypeData('County', 'county', 'city', False, False, False, 0),
            LocationTypeData('City', 'city', ROOT_LOCATION_TYPE, False, False, False, 0),
        ]
        edit_types_of_locations = [
            # change parent from TOP to county
            LocStub('S1', 's1', 'state', 'county11'),
            LocStub('S2', 's2', 'state', 'county11'),
            # change parent from state to city
            LocStub('County11', 'county11', 'county', 'city111'),
            LocStub('County21', 'county21', 'county', 'city111'),
            # make these two TOP locations
            LocStub('City111', 'city111', 'city', ''),
            LocStub('City112', 'city112', 'city', ''),
            # delete this
            LocStub('City211', 'city211', 'city', 'county21', do_delete=True),
        ]

        result = self.bulk_update_locations(
            reverse_order,  # No change to types
            edit_types_of_locations,  # This is the desired end result
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(reverse_order)
        self.assertLocationsMatch(self.as_pairs(edit_types_of_locations))

    def test_swap_parents(self):
        swap_parents = [
            LocStub('S1', 's1', 'state', ''),
            LocStub('S2', 's2', 'state', ''),
            # The two counties have the parents swapped
            LocStub('County11', 'county11', 'county', 's2'),
            LocStub('County21', 'county21', 'county', 's1'),
            LocStub('City111', 'city111', 'city', 'county11'),
            LocStub('City112', 'city112', 'city', 'county11'),
            LocStub('City211', 'city211', 'city', 'county21'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            swap_parents,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(swap_parents))

    def test_partial_attribute_edits_by_location_id(self):
        # a subset of locations can be edited and can be referenced by location_id
        change_names = [
            LocStub('My State 1', '', 'state', '', self.get_loc_id('S1')),
            LocStub('My County 11', '', 'county', 's1', self.get_loc_id('County11')),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('My State 1', None), ('S2', None), ('My County 11', 's1'),
            ('County21', 's2'), ('City111', 'county11'), ('City112', 'county11'),
            ('City211', 'county21'),
        }, check_attr='name')

    def test_partial_attribute_edits_by_site_code(self):
        # a subset of locations can be edited and can be referenced by site_code
        change_names = [
            LocStub('My State 1', 's1', 'state', ''),
            LocStub('My County 11', 'county11', 'county', 's1'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('My State 1', None), ('S2', None), ('My County 11', 's1'),
            ('County21', 's2'), ('City111', 'county11'), ('City112', 'county11'),
            ('City211', 'county21'),
        }, check_attr='name')

    def test_delete_unsaved(self):
        # Add a new location with delete=True
        tree = self.basic_tree + [LocStub('NewCity', 'newcity', 'city', 'county21', do_delete=True)]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))
