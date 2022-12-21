from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.resources.v0_6 import LocationResource
from corehq.util.view_utils import absolute_reverse


class LocationV6Test(APIResourceTest):
    api_name = 'v0.6'
    resource = LocationResource

    def setUp(self):
        self.parent_type = LocationType.objects.create(
            domain=self.domain.name,
            name="State",
            code="state",
        )

        self.child_type = LocationType.objects.create(
            domain=self.domain.name,
            name="City",
            code="city",
            parent_type=self.parent_type
        )

        self.location1 = SQLLocation.objects.create(
            domain=self.domain.name,
            location_id="1",
            name="Colorado",
            site_code="colorado",
            location_type=self.parent_type
        )

        self.location2 = SQLLocation.objects.create(
            domain=self.domain.name,
            location_id="2",
            name="Denver",
            site_code="denver",
            longitude=10.1234567891,
            latitude=11.1234567891,
            location_type=self.child_type,
            parent=self.location1,
            metadata={"population": "715,522"}
        )

    def single_endpoint(self, location_id):
        return absolute_reverse('api_dispatch_detail', kwargs={
            'resource_name': self.resource._meta.resource_name,
            'domain': self.domain.name,
            'api_name': self.api_name,
            'location_id': location_id
        })

    def test_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        location_1_dict = {
            "domain": self.domain.name,
            "last_modified": self.location1.last_modified.isoformat(),
            "latitude": None,
            "location_data": {},
            "location_id": "1",
            "location_type_code": "state",
            "location_type_name": "State",
            "longitude": None,
            "name": "Colorado",
            "parent_location_id": "",
            "site_code": "colorado"
        }

        location_2_dict = {
            "domain": self.domain.name,
            "last_modified": self.location2.last_modified.isoformat(),
            "latitude": "11.1234567891",
            "location_data": {
                "population": "715,522"
            },
            "location_id": "2",
            "location_type_code": "city",
            "location_type_name": "City",
            "longitude": "10.1234567891",
            "name": "Denver",
            "parent_location_id": "1",
            "site_code": "denver"
        }

        try:
            self.assertDictEqual(location_1_dict, response.json()['objects'][0])
            self.assertDictEqual(location_2_dict, response.json()['objects'][1])
        # Order of results doesn't matter, and order varies between envs.
        except AssertionError:
            self.assertDictEqual(location_1_dict, response.json()['objects'][1])
            self.assertDictEqual(location_2_dict, response.json()['objects'][0])

    def test_detail(self):
        response = self._assert_auth_get_resource(self.single_endpoint(self.location2.location_id))
        self.assertEqual(response.status_code, 200)

        self.assertDictEqual({
            "domain": self.domain.name,
            "last_modified": self.location2.last_modified.isoformat(),
            "latitude": "11.1234567891",
            "location_data": {
                "population": "715,522"
            },
            "location_id": "2",
            "location_type_code": "city",
            "location_type_name": "City",
            "longitude": "10.1234567891",
            "name": "Denver",
            "parent_location_id": "1",
            "site_code": "denver"
        }, response.json())
