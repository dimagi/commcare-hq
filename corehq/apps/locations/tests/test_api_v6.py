import json
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
            id="1234",
            location_id="1",
            name="Colorado",
            site_code="colorado",
            location_type=self.parent_type
        )

        self.location2 = SQLLocation.objects.create(
            domain=self.domain.name,
            id="1235",
            location_id="2",
            name="Denver",
            site_code="denver",
            longitude=10.1234567891,
            latitude=11.1234567891,
            location_type=self.child_type,
            parent=self.location1,
            metadata={"population": "715,522"}
        )

    def single_endpoint(self, id):
        return absolute_reverse('api_dispatch_detail', kwargs=dict(domain=self.domain.name,
                                                          api_name=self.api_name,
                                                          resource_name=self.resource._meta.resource_name,
                                                          location_id=id))

    # Disregards order of fields in output.
    def _validate_obj_output(self, desired_output, actual_output):
        for key in desired_output.keys():
            self.assertEqual(desired_output[key], actual_output[key])

    def test_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        self._validate_obj_output({
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
        }, json.loads(response.content.decode('utf-8'))['objects'][0])

        self._validate_obj_output({
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
        }, json.loads(response.content.decode('utf-8'))['objects'][1])

    def test_detail(self):
        response = self._assert_auth_get_resource(self.single_endpoint(self.location2.location_id))
        self.assertEqual(response.status_code, 200)

        self._validate_obj_output({
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
        }, json.loads(response.content.decode('utf-8')))
