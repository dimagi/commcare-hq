from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.models import WebUser

from ..util import get_user_facility_ids


class UserFacilityTests(LocationHierarchyTestCase):
    domain = 'bha-user-facility-tests'
    location_type_names = ['state', 'registry', 'organization', 'facility', 'facility_data']
    location_structure = [
        ('state-1', [
            ('registry-1', [
                ('organization-1', [
                    ('facility-1a', []),
                    ('facility-1b', [
                        ('facility_data-1b', []),
                    ]),
                ]),
                ('organization-2', [
                    ('facility-2a', []),
                    ('facility-2b', []),
                ]),
            ]),
        ])
    ]

    def test_get_user_facility_ids(self):
        user = WebUser.create(self.domain, 'test@example.com', 'secret', None, None)
        user.add_to_assigned_locations(self.domain, self.locations['organization-1'])
        user.add_to_assigned_locations(self.domain, self.locations['facility-2a'])
        restore_user = user.to_ota_restore_user(self.domain)
        res = get_user_facility_ids(self.domain, restore_user)
        self.assertItemsEqual(res, [
            self.locations[loc_name].location_id for loc_name in [
                'facility-1a',
                'facility-1b',
                'facility-2a',
            ]
        ])
