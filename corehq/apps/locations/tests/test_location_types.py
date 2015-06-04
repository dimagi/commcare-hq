from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType


class TestLocationTypes(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain('locations-test')

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

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
