from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.users.models import CommCareUser


class TestLocationTypes(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationTypes, cls).setUpClass()
        cls.domain = create_domain('locations-test')

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestLocationTypes, cls).tearDownClass()

    def tearDown(self):
        LocationType.objects.filter(domain=self.domain.name).delete()

    def test_hierarchy(self):
        state = make_loc_type('state')

        district = make_loc_type('district', state)
        section = make_loc_type('section', district)
        block = make_loc_type('block', district)
        center = make_loc_type('center', block)

        county = make_loc_type('county', state)
        city = make_loc_type('city', county)

        hierarchy = LocationType.objects.full_hierarchy(self.domain.name)
        desired_hierarchy = {
            state.id: (
                state,
                {
                    district.id: (
                        district,
                        {
                            section.id: (section, {}),
                            block.id: (block, {
                                center.id: (center, {}),
                            }),
                        },
                    ),
                    county.id: (
                        county,
                        {city.id: (city, {})},
                    ),
                },
            ),
        }
        self.assertEqual(hierarchy, desired_hierarchy)


class TestLocationTypeOwnership(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationTypeOwnership, cls).setUpClass()
        cls.domain = 'locations-test-ownership'
        cls.project = create_domain(cls.domain)

    def setUp(self):
        self.user = CommCareUser.create(
            self.domain,
            'username',
            'password',
            created_by=None,
            created_via=None,
            first_name='Location types',
            last_name='Tester',
        )
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestLocationTypeOwnership, cls).tearDownClass()

    def test_no_case_sharing(self):
        no_case_sharing_type = make_loc_type('no-case-sharing', domain=self.domain)
        location = make_loc('loc', type=no_case_sharing_type.name, domain=self.domain)
        self.user.set_location(location)
        self.assertEqual([], self.user.get_case_sharing_groups())

    def test_sharing_no_descendants(self):
        case_sharing_type = make_loc_type('case-sharing', domain=self.domain, shares_cases=True)
        location = make_loc('loc', type=case_sharing_type.name, domain=self.domain)
        self.user.set_location(location)
        location_groups = self.user.get_case_sharing_groups()
        self.assertEqual(1, len(location_groups))
        self.assertEqual(location.location_id, location_groups[0]._id)

    def test_assigned_loc_included_with_descendants(self):
        parent_type = make_loc_type('parent', domain=self.domain, shares_cases=True, view_descendants=True)
        child_type = make_loc_type('child', domain=self.domain, shares_cases=True)
        parent_loc = make_loc('parent', type=parent_type.name, domain=self.domain)
        child_loc = make_loc('child', type=child_type.name, domain=self.domain, parent=parent_loc)
        self.user.set_location(parent_loc)
        self.assertEqual(
            set([parent_loc._id, child_loc._id]),
            set([g._id for g in self.user.get_case_sharing_groups()])
        )

    def test_only_case_sharing_descendents_included(self):
        parent_type = make_loc_type('parent', domain=self.domain, shares_cases=True, view_descendants=True)
        child_type = make_loc_type('child', domain=self.domain, shares_cases=False)
        grandchild_type = make_loc_type('grandchild', domain=self.domain, shares_cases=True)
        parent_loc = make_loc('parent', type=parent_type.name, domain=self.domain)
        child_loc = make_loc('child', type=child_type.name, domain=self.domain, parent=parent_loc)
        grandchild_loc = make_loc('grandchild', type=grandchild_type.name, domain=self.domain, parent=child_loc)
        self.user.set_location(parent_loc)
        self.assertEqual(
            set([parent_loc._id, grandchild_loc._id]),
            set([g._id for g in self.user.get_case_sharing_groups()])
        )

    def test_archived_locations_are_not_included(self):
        parent_type = make_loc_type('parent', domain=self.domain,
                shares_cases=True, view_descendants=True)
        child_type = make_loc_type('child', domain=self.domain,
                shares_cases=False)
        grandchild_type = make_loc_type('grandchild', domain=self.domain,
                shares_cases=True)
        parent_loc = make_loc('parent', type=parent_type.name,
                domain=self.domain)
        child_loc = make_loc('child', type=child_type.name, domain=self.domain,
                parent=parent_loc)
        grandchild_loc = make_loc('grandchild', type=grandchild_type.name,
                domain=self.domain, parent=child_loc)
        make_loc('archived_grandchild', type=grandchild_type.name,
                 domain=self.domain, parent=child_loc, is_archived=True)
        self.user.set_location(parent_loc)
        self.assertEqual(
            set([parent_loc._id, grandchild_loc._id]),
            set([g._id for g in self.user.get_case_sharing_groups()])
        )


class TestLocationTypeExpansions(SimpleTestCase):
    def setUp(self):
        self.city = LocationType(
            domain='test_domain',
            name='City',
            code='city',
        )
        self.state = LocationType(
            domain='test_domain',
            name='State',
            code='state',
        )

    def test_setting_expansion(self):
        """Expansions should either be an expansion from the root, or from a particular level
        """
        self.assertFalse(self.city.expand_from_root)
        self.city.expand_from = self.state
        self.assertFalse(self.city.expand_from_root)
        self.assertEqual(self.city.expand_from, self.state)

        self.city.expand_from_root = True
        self.assertTrue(self.city.expand_from_root)
        self.assertIsNone(self.city.expand_from)

        self.city.expand_from = self.state
        self.assertFalse(self.city.expand_from_root)
        self.assertEqual(self.city.expand_from, self.state)


def make_loc_type(name, parent_type=None, domain='locations-test',
                  shares_cases=False, view_descendants=False):
    return LocationType.objects.create(
        domain=domain,
        name=name,
        code=name,
        parent_type=parent_type,
        shares_cases=shares_cases,
        view_descendants=view_descendants
    )
