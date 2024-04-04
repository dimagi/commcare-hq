from collections import defaultdict
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils.functional import cached_property

from unittest.mock import Mock, patch

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    Field,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.util.workbook_json.excel import IteratorJSONReader

from ..bulk_management import (
    LocationCollection,
    LocationData,
    LocationStub,
    LocationTreeValidator,
    LocationTypeData,
    LocationTypeStub,
    NewLocationImporter,
    new_locations_import,
)
from ..const import ROOT_LOCATION_TYPE
from ..models import SQLLocation
from ..tree_utils import TreeError, assert_no_cycles
from ..util import LocationExporter, get_location_data_model
from .util import (
    LocationHierarchyPerTest,
    MockExportWriter,
    restrict_user_by_location,
)

# These example types and trees mirror the information available in the upload files

NOT_PROVIDED = LocationStub.NOT_PROVIDED


def LocTypeRow(
    name,
    code,
    parent_code,
    do_delete=False,
    shares_cases=False,
    view_descendants=False,
):
    return LocationTypeData(name, code, parent_code, do_delete, shares_cases, view_descendants, 0)


FLAT_LOCATION_TYPES = [
    LocTypeRow('State', 'state', ''),
    LocTypeRow('County', 'county', 'state'),
    LocTypeRow('City', 'city', 'county'),
]


def NewLocRow(
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
    delete_uncategorized_data=False,
):
    return LocationData(
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
        delete_uncategorized_data,
        0,
    )


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
        self.assertEqual(
            set(e.exception.affected_nodes),
            set(["County", "Region"])
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
        self.assertEqual(
            set(e.exception.affected_nodes),
            set(["Region", "District", "Village"])
        )


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


class UploadTestUtils(object):
    domain = 'test-bulk-management'

    @cached_property
    def locations_by_code(self):
        self.addCleanup(lambda: delattr(self, 'locations_by_code'))
        return {
            loc.site_code: loc
            for loc in SQLLocation.objects.filter(domain=self.domain)
        }

    @classmethod
    def as_pairs(cls, tree):
        # returns list of (site_code, parent_code) tuples
        pairs = set()
        for l in tree:
            if not l.do_delete:
                pairs.add((l.site_code, l.parent_code))
        return pairs

    def UpdateLocRow(self, name, site_code, location_type, parent_code, **kwargs):
        """Like NewLocRow, but looks up location_id from the site_code"""
        if 'location_id' in kwargs:
            raise Exception("If you're going to pass in location_id, use NewLocRow.")

        location_id = self.locations_by_code[site_code].location_id
        return NewLocRow(name, site_code, location_type, parent_code,
                         location_id=location_id, **kwargs)

    def bulk_update_locations(self, types, locations):
        importer = NewLocationImporter(
            self.domain,
            types,
            locations,
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
        actual = [LocationTypeData(
            lt.name,
            lt.code,
            lt.parent_type.code if lt.parent_type else '',
            False,
            lt.shares_cases or False,
            lt.view_descendants,
            index=0,
        ) for lt in actual_types]
        expected = [lt for lt in expected_types if not lt.do_delete]
        self.assertEqual(set(actual), set(expected))

    def assertLocationsMatch(self, expected_locations, check_attr='site_code'):
        collection = LocationCollection(self.domain_obj)

        actual = []
        for l in collection.locations:
            attr = getattr(l, check_attr)
            if l.parent:
                parent = l.parent.site_code
            else:
                parent = ROOT_LOCATION_TYPE
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
        for (l, desc) in descendants.items():
            q = SQLLocation.objects.filter(site_code=l)
            loc = q[0] if q else None

            actual = [i.site_code for i in loc.get_descendants()] if loc else []
            self.assertEqual(set(actual), set(desc))


class TestTreeValidator(UploadTestUtils, TestCase):
    basic_location_tree = [
        NewLocRow('Massachusetts', 'mass', 'state', ''),
        NewLocRow('Suffolk', 'suffolk', 'county', 'mass'),
        NewLocRow('Boston', 'boston', 'city', 'suffolk'),
        NewLocRow('Middlesex', 'middlesex', 'county', 'mass'),
        NewLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
        NewLocRow('Florida', 'florida', 'state', ''),
        NewLocRow('Duval', 'duval', 'county', 'florida'),
        NewLocRow('Jacksonville', 'jacksonville', 'city', 'duval'),
    ]

    @property
    def basic_update(self):
        return [
            self.UpdateLocRow(
                l.name,
                l.site_code,
                l.location_type,
                l.parent_code if l.parent_code != ROOT_LOCATION_TYPE else '')
            for l in self.basic_location_tree
        ]

    def setUp(self):
        super(TestTreeValidator, self).setUp()
        self.domain_obj = create_domain(self.domain)
        self.user = WebUser.create(self.domain, 'username', 'password', None, None)

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        self.domain_obj.delete()
        super(TestTreeValidator, self).tearDown()

    def get_validator(self, location_types, locations):
        old_collection = LocationCollection(self.domain_obj)
        data_model = get_location_data_model(self.domain)
        return LocationTreeValidator(
            [LocationTypeStub(data, old_collection) for data in location_types],
            [LocationStub(data, data_model, old_collection) for data in locations],
            old_collection=old_collection,
            user=self.user,
        )

    def test_good_location_set(self):
        validator = self.get_validator(FLAT_LOCATION_TYPES, self.basic_location_tree)
        assert_errors(validator, [])

    def test_cyclic_location_types(self):
        cyclic_location_types = [
            LocTypeRow('State', 'state', ''),
            LocTypeRow('County', 'county', 'state'),
            LocTypeRow('City', 'city', 'county'),
            # These three cycle:
            LocTypeRow('Region', 'region', 'village'),
            LocTypeRow('District', 'district', 'region'),
            LocTypeRow('Village', 'village', 'district'),
        ]
        validator = self.get_validator(cyclic_location_types, self.basic_location_tree)
        self.assertEqual(len(validator._validate_types_tree()), 3)

    def test_bad_type_change(self):
        make_suffolk_a_state_invalid = [
            NewLocRow('Massachusetts', 'mass', 'state', ''),
            # This still lists mass as a parent, which is invalid,
            # plus, Boston (a city), can't have a state as a parent
            NewLocRow('Suffolk', 'suffolk', 'state', 'mass'),
            NewLocRow('Boston', 'boston', 'city', 'suffolk'),
            NewLocRow('Middlesex', 'middlesex', 'county', 'mass'),
            NewLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
            NewLocRow('Florida', 'florida', 'state', ''),
            NewLocRow('Duval', 'duval', 'county', 'florida'),
            NewLocRow('Jacksonville', 'jacksonville', 'city', 'duval'),
        ]
        validator = self.get_validator(FLAT_LOCATION_TYPES, make_suffolk_a_state_invalid)

        assert_errors(validator, [
            "'suffolk' is a 'state' and should not have a parent",
            "'boston' is a 'city', so it should have a parent that is a 'county'",
        ])

    def test_good_type_change(self):
        make_suffolk_a_state_valid = [
            NewLocRow('Massachusetts', 'mass', 'state', ''),
            NewLocRow('Suffolk', 'suffolk', 'state', ''),
            NewLocRow('Boston', 'boston', 'county', 'suffolk'),
            NewLocRow('Middlesex', 'middlesex', 'county', 'mass'),
            NewLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
            NewLocRow('Florida', 'florida', 'state', ''),
            NewLocRow('Duval', 'duval', 'county', 'florida'),
            NewLocRow('Jacksonville', 'jacksonville', 'city', 'duval'),
        ]
        validator = self.get_validator(FLAT_LOCATION_TYPES, make_suffolk_a_state_valid)
        assert_errors(validator, [])

    def test_duplicate_type_codes(self):
        duplicate_type_codes = [
            LocTypeRow('State', 'state', ''),
            LocTypeRow('County', 'county', 'state'),
            LocTypeRow('City', 'city', 'county'),
            LocTypeRow('Other County', 'county', 'state'),
        ]
        validator = self.get_validator(duplicate_type_codes, self.basic_location_tree)
        assert_errors(validator, ["type code 'county' is used 2 times"])

    def test_duplicate_location(self):
        duplicate_site_codes = [
            NewLocRow('Massachusetts', 'mass', 'state', ''),
            NewLocRow('Suffolk', 'suffolk', 'county', 'mass'),
            NewLocRow('Boston', 'boston', 'city', 'suffolk'),
            NewLocRow('Middlesex', 'middlesex', 'county', 'mass'),
            NewLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
            NewLocRow('East Cambridge', 'cambridge', 'city', 'middlesex'),
        ]
        validator = self.get_validator(FLAT_LOCATION_TYPES, duplicate_site_codes)
        assert_errors(validator, [
            "site_code 'cambridge' is used 2 times",
        ])

    def test_same_name_same_parent(self):
        same_name_same_parent = [
            NewLocRow('Massachusetts', 'mass', 'state', ''),
            NewLocRow('Middlesex', 'middlesex', 'county', 'mass'),
            # These two locations have the same name AND same parent
            NewLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
            NewLocRow('Cambridge', 'cambridge2', 'city', 'middlesex'),
        ]
        validator = self.get_validator(FLAT_LOCATION_TYPES, same_name_same_parent)
        assert_errors(validator, [
            " 2 locations with the name 'Cambridge' under the parent 'middlesex'"
        ])

    def test_missing_types(self):
        # all types in the domain should be listed in given excel
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES + [LocTypeRow('Galaxy', 'galaxy', '')],
            self.basic_location_tree,
        )
        assert_errors(result, [])
        validator = self.get_validator(FLAT_LOCATION_TYPES, self.basic_update)
        assert_errors(validator, ["type code 'galaxy' is not listed"])

    def test_missing_location_ids(self):
        # not all locations need to be specified in the upload
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_location_tree + [NewLocRow('extra_state', 'ex_code', 'state', '')],
        )
        assert_errors(result, [])
        validator = self.get_validator(FLAT_LOCATION_TYPES, self.basic_update)
        assert_errors(validator, [])

    def test_unknown_location_ids(self):
        # all locations with IDs must already exist
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_location_tree,
        )
        assert_errors(result, [])
        new_locations = (
            self.basic_update +
            [NewLocRow('extra_state', 'ex_code', 'state', '', location_id='ex_id')]
        )
        validator = self.get_validator(FLAT_LOCATION_TYPES, new_locations)
        assert_errors(validator, ["'id: ex_id' is not found in your domain"])


class TestBulkManagementNoInitialLocs(UploadTestUtils, TestCase):

    basic_tree = [
        NewLocRow('S1', 's1', 'state', ''),
        NewLocRow('S2', 's2', 'state', ''),
        NewLocRow('County11', 'county11', 'county', 's1'),
        NewLocRow('County21', 'county21', 'county', 's2'),
        NewLocRow('City111', 'city111', 'city', 'county11'),
        NewLocRow('City112', 'city112', 'city', 'county11'),
        NewLocRow('City211', 'city211', 'city', 'county21'),
    ]

    def setUp(self):
        super(TestBulkManagementNoInitialLocs, self).setUp()
        self.domain_obj = create_domain(self.domain)
        self.user = WebUser.create(self.domain, 'username', 'password', None, None)

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        self.domain_obj.delete()
        super(TestBulkManagementNoInitialLocs, self).tearDown()

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
            NewLocRow('S1', 1, 'state', '', external_id=11),
            NewLocRow('S2', 2, 'state', '', external_id=12),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            data
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(set([('1', ROOT_LOCATION_TYPE), ('2', ROOT_LOCATION_TYPE)]))

    def test_data_format(self):
        data = [
            NewLocRow('S1', '1', 'state', '', external_id='12', latitude='not-lat', longitude='2345'),
            NewLocRow('S2', '2', 'state', '', external_id='12', latitude='3434', longitude='2345'),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            data
        )
        assert_errors(result, ['index 0 should be valid decimal numbers'])

    def test_custom_data(self):
        tree = [
            NewLocRow('省 1', 's1', 'state', '', custom_data={'a': 1}),
            NewLocRow('County 11', 'c1', 'county', 's1', custom_data={'国际字幕': '试验'}),
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
        # setup some metadata
        tree = [
            NewLocRow('State 1', 's1', 'state', '', custom_data={'a': 1}),
            NewLocRow('County 11', 'c1', 'county', 's1', custom_data={'b': 'test'}),
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )

        locations = _codify(SQLLocation.objects.all())
        self.assertEqual(locations["s1"].metadata, {'a': '1'})
        self.assertEqual(locations["c1"].metadata, {'b': 'test'})

        tree = [
            self.UpdateLocRow('State 1', 's1', 'state', '', custom_data={'a': 1},
                              delete_uncategorized_data=True),
            self.UpdateLocRow('County 11', 'c1', 'county', 's1', custom_data={'b': 'test'}),
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )

        locations = _codify(SQLLocation.objects.all())
        # uncategorized data gets removed
        self.assertEqual(locations["s1"].metadata, {})
        # uncategorized data gets kept as long as it's specified
        self.assertEqual(locations["c1"].metadata, {'b': 'test'})

    def test_case_sensitivity(self):
        # site-codes are automatically converted to lower-case
        upper_case = [
            NewLocRow('State 1', 'S1', 'state', ''),
            NewLocRow('State 2', 'S2', 'state', ''),
            NewLocRow('County 11', 'C1', 'county', 's1'),
            NewLocRow('County 21', 'C2', 'county', 's2'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            upper_case,
        )

        lower_case = [
            self.UpdateLocRow('State 1', 'S1'.lower(), 'state', ''),
            self.UpdateLocRow('State 2', 'S2'.lower(), 'state', ''),
            self.UpdateLocRow('County 11', 'C1'.lower(), 'county', 's1'),
            self.UpdateLocRow('County 21', 'C2'.lower(), 'county', 's2'),
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
            NewLocRow('State 3', 's3', 'state', ''),
            NewLocRow('County 21', 'county3', 'county', 's3'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            addition
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree).union({
            ('s3', ROOT_LOCATION_TYPE), ('county3', 's3')
        }))

    def test_partial_parent_edits(self):
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )
        change_parents = [
            self.UpdateLocRow('County 21', 'county21', 'county', 's1'),
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_parents
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('s1', ROOT_LOCATION_TYPE), ('s2', ROOT_LOCATION_TYPE), ('county11', 's1'),
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
            self.UpdateLocRow('City211', 'city211', 'city', 's1'),
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
            self.UpdateLocRow('County 21', 'county21', 'city', 's2', do_delete=True),
            self.UpdateLocRow('City211', 'city211', 'city', 'county11', do_delete=True),
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
            self.UpdateLocRow('City111', 'city111', 'city', 'county11', do_delete=True),
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
            self.UpdateLocRow('County 21', 'county21', 'city', 's2', do_delete=True),
            # city211 is missing
        ]
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete
        )
        assert_errors(result, ["child locations 'city211' are missing"])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_tree))

    def test_new_root(self):
        # new locations can be added without having to specify all of old ones
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_tree
        )

        upload = [
            self.UpdateLocRow('S1', 's1', 'city', 'county11'),
            self.UpdateLocRow('S2', 's2', 'city', 'county11'),
            self.UpdateLocRow('County11', 'county11', 'county', 'city111'),
            self.UpdateLocRow('County21', 'county21', 'county', 'city111'),
            self.UpdateLocRow('City111', 'city111', 'state', ''),
            self.UpdateLocRow('City112', 'city112', 'state', ''),
            self.UpdateLocRow('City211', 'city211', 'state', ''),
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
        self.user = WebUser.create(self.domain, 'username', 'password', None, None)

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        super(TestBulkManagementWithInitialLocs, self).tearDown()

    @property
    def basic_update(self):
        return [
            self.UpdateLocRow('S1', 's1', 'state', ''),
            self.UpdateLocRow('S2', 's2', 'state', ''),
            self.UpdateLocRow('County11', 'county11', 'county', 's1'),
            self.UpdateLocRow('County21', 'county21', 'county', 's2'),
            self.UpdateLocRow('City111', 'city111', 'city', 'county11'),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11'),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21'),
        ]

    def test_large_upload(self):
        big_location_tree = [
            NewLocRow('{}'.format(i), '{}'.format(i), 'city', 'county11')
            for i in range(34)
        ]
        self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            self.basic_update
        )
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            big_location_tree
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_update + big_location_tree))

    def test_move_county21_to_state1(self):
        self.assertLocationsMatch(self.as_pairs(self.basic_update))

        move_county21_to_state1 = [
            self.UpdateLocRow('S1', 's1', 'state', ''),
            self.UpdateLocRow('S2', 's2', 'state', ''),
            self.UpdateLocRow('County11', 'county11', 'county', 's1'),
            # change parent_code from s2 -> s1
            self.UpdateLocRow('County21', 'county21', 'county', 's1'),
            self.UpdateLocRow('City111', 'city111', 'city', 'county11'),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11'),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21'),
            # create new city
            NewLocRow('City311', 'city311', 'city', 'county11'),
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
            self.UpdateLocRow('S1', 's1', 'state', ''),
            self.UpdateLocRow('S2', 's2', 'state', ''),
            self.UpdateLocRow('County11', 'county11', 'county', 's1', do_delete=True),
            self.UpdateLocRow('County21', 'county21', 'county', 's2'),
            self.UpdateLocRow('City111', 'city111', 'city', 'county11', do_delete=True),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11', do_delete=True),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21'),
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
            self.UpdateLocRow('S1', 's1', 'state', ''),
            # delete s2, but don't delete its descendatns. This is invalid
            self.UpdateLocRow('S2', 's2', 'state', '', do_delete=True),
            self.UpdateLocRow('County11', 'county11', 'county', 's1'),
            self.UpdateLocRow('County21', 'county21', 'county', 's2'),
            self.UpdateLocRow('City111', 'city111', 'city', 'county11'),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11'),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            delete_s2,
        )

        assert_errors(result, ["points to a location that's being deleted"])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        # Since there were errors, the location tree should be as it was
        self.assertLocationsMatch(self.as_pairs(self.basic_update))

    def test_delete_city_type_valid(self):
        # delete a location type and locations of that type
        delete_city_types = [
            LocTypeRow('State', 'state', ''),
            LocTypeRow('County', 'county', 'state'),
            LocTypeRow('City', 'city', 'county'),
        ]
        delete_cities_locations = [
            self.UpdateLocRow('S1', 's1', 'state', ''),
            self.UpdateLocRow('S2', 's2', 'state', ''),
            self.UpdateLocRow('County11', 'county11', 'county', 's1'),
            self.UpdateLocRow('County21', 'county21', 'county', 's2'),
            # delete locations of type 'city'
            self.UpdateLocRow('City111', 'city111', 'city', 'county11', do_delete=True),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11', do_delete=True),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21', do_delete=True),
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
            LocTypeRow('State', 'state', ''),
            LocTypeRow('County', 'county', 'state'),
            LocTypeRow('City', 'city', 'county'),
        ]
        delete_cities_locations = [
            self.UpdateLocRow('S1', 's1', 'state', '', do_delete=True),
            self.UpdateLocRow('S2', 's2', 'state', '', do_delete=True),
            self.UpdateLocRow('County11', 'county11', 'county', 's1', do_delete=True),
            self.UpdateLocRow('County21', 'county21', 'county', 's2', do_delete=True),
            self.UpdateLocRow('City111', 'city111', 'city', 'county11', do_delete=True),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11', do_delete=True),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21', do_delete=True),
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
            LocTypeRow('State', 'state', ''),
            LocTypeRow('County', 'county', 'state'),
            LocTypeRow('City', 'city', 'county', do_delete=True),
        ]

        result = self.bulk_update_locations(
            delete_city_types,  # delete city type
            self.basic_update,  # but don't delete locations of city type
        )

        assert_errors(result, [
            "'city111' in sheet points to a nonexistent or to be deleted location-type",
            "'city112' in sheet points to a nonexistent or to be deleted location-type",
            "'city211' in sheet points to a nonexistent or to be deleted location-type",
        ])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_update))

    def test_edit_names(self):
        # metadata attributes like 'name' can be updated
        self.assertLocationsMatch(self.as_pairs(self.basic_update))
        change_names = [
            # changing names
            self.UpdateLocRow('State 1', 's1', 'state', ''),
            self.UpdateLocRow('State 2', 's2', 'state', ''),
            self.UpdateLocRow('County 11', 'county11', 'county', 's1'),
            self.UpdateLocRow('County 21', 'county21', 'county', 's2'),
            self.UpdateLocRow('City 111', 'city111', 'city', 'county11'),
            self.UpdateLocRow('City 112', 'city112', 'city', 'county11'),
            self.UpdateLocRow('City 211', 'city211', 'city', 'county21'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_update))
        self.assertLocationsMatch(set([
            ('State 1', ROOT_LOCATION_TYPE),
            ('State 2', ROOT_LOCATION_TYPE),
            ('County 11', 's1'),
            ('County 21', 's2'),
            ('City 111', 'county11'),
            ('City 112', 'county11'),
            ('City 211', 'county21')
        ]), check_attr='name')

    def test_partial_type_edit(self):
        # edit a subset of types
        self.assertLocationsMatch(self.as_pairs(self.basic_update))

        edit_types = [
            LocTypeRow('State', 'state', ''),
            # change name of this type
            LocTypeRow('District', 'county', 'state'),
            # Make this one share cases
            LocTypeRow('City', 'city', 'county', shares_cases=True),
        ]

        result = self.bulk_update_locations(
            edit_types,
            self.basic_update,
        )

        assert_errors(result, [])
        self.assertLocationTypesMatch(edit_types)
        self.assertLocationsMatch(self.as_pairs(self.basic_update))

    def test_rearrange_locations(self):
        # a total rearrangement like reversing the tree can be done
        reverse_order = [
            LocTypeRow('State', 'state', 'county'),
            LocTypeRow('County', 'county', 'city'),
            LocTypeRow('City', 'city', ''),
        ]
        edit_types_of_locations = [
            # change parent from TOP to county
            self.UpdateLocRow('S1', 's1', 'state', 'county11'),
            self.UpdateLocRow('S2', 's2', 'state', 'county11'),
            # change parent from state to city
            self.UpdateLocRow('County11', 'county11', 'county', 'city111'),
            self.UpdateLocRow('County21', 'county21', 'county', 'city111'),
            # make these two TOP locations
            self.UpdateLocRow('City111', 'city111', 'city', ''),
            self.UpdateLocRow('City112', 'city112', 'city', ''),
            # delete this
            self.UpdateLocRow('City211', 'city211', 'city', 'county21', do_delete=True),
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
            self.UpdateLocRow('S1', 's1', 'state', ''),
            self.UpdateLocRow('S2', 's2', 'state', ''),
            # The two counties have the parents swapped
            self.UpdateLocRow('County11', 'county11', 'county', 's2'),
            self.UpdateLocRow('County21', 'county21', 'county', 's1'),
            self.UpdateLocRow('City111', 'city111', 'city', 'county11'),
            self.UpdateLocRow('City112', 'city112', 'city', 'county11'),
            self.UpdateLocRow('City211', 'city211', 'city', 'county21'),
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
            self.UpdateLocRow('My State 1', 's1', 'state', ''),
            self.UpdateLocRow('My County 11', 'county11', 'county', 's1'),
        ]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            change_names
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch({
            ('My State 1', ROOT_LOCATION_TYPE), ('S2', ROOT_LOCATION_TYPE), ('My County 11', 's1'),
            ('County21', 's2'), ('City111', 'county11'), ('City112', 'county11'),
            ('City211', 'county21'),
        }, check_attr='name')

    def test_delete_unsaved(self):
        # Add a new location with delete=True
        tree = self.basic_update + [NewLocRow('NewCity', 'newcity', 'city', 'county21', do_delete=True)]

        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            tree
        )
        assert_errors(result, [])
        self.assertLocationTypesMatch(FLAT_LOCATION_TYPES)
        self.assertLocationsMatch(self.as_pairs(self.basic_update))

    def test_fail_to_update_without_id(self):
        # You must specify a location_id to perform an update
        result = self.bulk_update_locations(
            FLAT_LOCATION_TYPES,
            [
                # This site_code is already taken:
                NewLocRow('New City211', 'city211', 'city', 'county21'),
                NewLocRow('City212', 'city212', 'city', 'county21'),
            ],
        )
        assert_errors(result, ["site_code 'city211' is in use"])

    def test_download_reupload_no_changes(self):
        # Make sure there's a bunch of data
        loc_fields = CustomDataFieldsDefinition.get_or_create(self.domain, 'LocationFields')
        loc_fields.set_fields([
            Field(slug='favorite_color'),
            Field(slug='language'),
        ])
        loc_fields.save()

        self.locations['City111'].latitude = Decimal('42.36')
        self.locations['City111'].longitude = Decimal('71.06')
        self.locations['City111'].external_id = '123'
        self.locations['County11'].metadata = {'favorite_color': 'purple',
                                               'language': 'en'}
        self.locations['City111'].save()

        self.locations['County11'].external_id = '321'
        self.locations['County11'].metadata = {'favorite_color': 'blue'}
        self.locations['County11'].save()

        # Export locations
        exporter = LocationExporter(self.domain)
        writer = MockExportWriter()
        exporter.write_data(writer)

        # Re-upload that export
        worksheets = []
        for sheet_title, headers in exporter.get_headers():
            rows = [[val if val is not None else '' for val in row]
                    for row in writer.data[sheet_title]]
            sheet = IteratorJSONReader(headers + rows)
            sheet.title = sheet_title
            worksheets.append(sheet)
        mock_importer = Mock()
        mock_importer.worksheets = worksheets
        with patch('corehq.apps.locations.models.SQLLocation.save') as save_location, \
             patch('corehq.apps.locations.models.LocationType.save') as save_type:
            result = new_locations_import(self.domain, mock_importer, self.user)

        # The upload should succeed and not perform any updates
        assert_errors(result, [])
        self.assertFalse(save_location.called)
        self.assertFalse(save_type.called)

    def test_dont_delete_referenced_location_types(self):
        self.location_types['State'].expand_to = self.location_types['County']
        self.location_types['State'].save()
        delete_county_type = [
            LocTypeRow('State', 'state', ''),
            LocTypeRow('County', 'county', 'state', do_delete=True),
            LocTypeRow('City', 'city', 'state'),
        ]
        result = self.bulk_update_locations(
            delete_county_type,
            [],
        )
        assert_errors(result, ["Location Type 'state' references the type to be deleted 'county'"
                               " via the field 'expand_to'"])


class TestRestrictedUserUpload(UploadTestUtils, LocationHierarchyPerTest):
    location_type_names = [lt.name for lt in FLAT_LOCATION_TYPES]
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ])
    ]

    def setUp(self):
        super(TestRestrictedUserUpload, self).setUp()
        self.user = WebUser.create(self.domain, 'username', 'password', None, None)
        self.user.set_location(self.domain, self.locations['Middlesex'])
        restrict_user_by_location(self.domain, self.user)

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)
        super(TestRestrictedUserUpload, self).tearDown()

    def test_only_additions(self):
        upload = [
            NewLocRow('Lowell', 'lowell', 'city', 'middlesex'),
            NewLocRow('Framingham', 'framingham', 'city', 'middlesex'),
        ]
        result = self.bulk_update_locations(FLAT_LOCATION_TYPES, upload)
        assert_errors(result, [])

    def test_subtree_upload_no_changes(self):
        upload = [
            # Parent locations can be included as long as they're not changed
            self.UpdateLocRow('Massachusetts', 'massachusetts', 'state', ''),
            self.UpdateLocRow('Middlesex', 'middlesex', 'county', 'massachusetts'),
            self.UpdateLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
            self.UpdateLocRow('Somerville', 'somerville', 'city', 'middlesex'),
        ]
        with patch('corehq.apps.locations.models.SQLLocation.save') as save_location:
            result = self.bulk_update_locations(FLAT_LOCATION_TYPES, upload)
        assert_errors(result, [])
        self.assertFalse(save_location.called)

    def test_subtree_upload_with_changes(self):
        upload = [
            self.UpdateLocRow('Massachusetts', 'massachusetts', 'state', ''),
            # This line represents a change
            self.UpdateLocRow('New Middlesex', 'middlesex', 'county', 'massachusetts'),
            self.UpdateLocRow('Cambridge', 'cambridge', 'city', 'middlesex'),
            self.UpdateLocRow('Somerville', 'somerville', 'city', 'middlesex'),
            NewLocRow('Lowell', 'lowell', 'city', 'middlesex'),
        ]
        with patch('corehq.apps.locations.models.SQLLocation.save') as save_location:
            result = self.bulk_update_locations(FLAT_LOCATION_TYPES, upload)
        assert_errors(result, [])
        self.assertEqual(save_location.call_count, 2)

    def test_out_of_bounds_edit(self):
        upload = [
            # Suffolk isn't accessible
            self.UpdateLocRow('New Suffolk', 'suffolk', 'county', 'massachusetts'),
        ]
        result = self.bulk_update_locations(FLAT_LOCATION_TYPES, upload)
        assert_errors(result, ["You do not have permission to edit 'suffolk'"])

    def test_out_of_bounds_addition(self):
        upload = [
            NewLocRow('Lowell', 'lowell', 'city', 'middlesex'),
            # Suffolk isn't accessible, can't create children there
            NewLocRow('Revere', 'revere', 'city', 'suffolk'),
        ]
        result = self.bulk_update_locations(FLAT_LOCATION_TYPES, upload)
        assert_errors(result, ["You do not have permission to add locations in 'suffolk'"])

    def test_cant_add_top_level_locations(self):
        upload = [
            NewLocRow('Lowell', 'lowell', 'city', 'middlesex'),
            NewLocRow('Idaho', 'idaho', 'state', ''),
        ]
        result = self.bulk_update_locations(FLAT_LOCATION_TYPES, upload)
        assert_errors(result, ["You do not have permission to add top level locations"])

    def test_cant_modify_types(self):
        types = FLAT_LOCATION_TYPES + [
            LocTypeRow('Galaxy', 'galaxy', '')]
        result = self.bulk_update_locations(types, [])
        assert_errors(result, ["You do not have permission to add or modify location types"])
