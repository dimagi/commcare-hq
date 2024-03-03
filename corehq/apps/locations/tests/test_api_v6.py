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

        self.county = LocationType.objects.create(
            domain=self.domain.name,
            name="County",
            code="county",
            parent_type=self.parent_type
        )
        self.south_park = SQLLocation.objects.create(
            domain=self.domain.name,
            location_id="22",
            name="south park",
            site_code="south_park",
            location_type=self.county
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

    def test_post(self):
        post_data = {
            "latitude": 31.1234,
            "location_data": {
                "city_pop": "729"
            },
            "location_type_code": "city",
            "longitude": 32.5678,
            "name": "Fairplay",
            "parent_location_id": "1",
            "site_code": "fairplay"
        }
        response = self._assert_auth_post_resource(self.list_endpoint, post_data)
        self.assertEqual(response.status_code, 201)

        created_location = SQLLocation.objects.get(name="Fairplay")
        post_data_location_data = post_data.pop('location_data')
        created_location_json = created_location.to_json()
        self.assertTrue(all(
            key_value_pair in created_location_json.items()
            for key_value_pair in post_data.items()))
        self.assertTrue(all(
            key_value_pair in created_location_json['metadata'].items()
            for key_value_pair in post_data_location_data.items()))

    def test_successful_put1(self):
        put_data = {
            "name": "New Denver",
            "site_code": "new_denver",
            "longitude": 33.9012
        }
        response = self._assert_auth_post_resource(self.single_endpoint(self.location2.location_id),
                                                   put_data, method='PUT')
        self.assertEqual(response.status_code, 200)

        self.location2_updated = SQLLocation.objects.get(location_id=self.location2.location_id)
        self.assertEqual(self.location2_updated.name, "New Denver")
        self.assertEqual(self.location2_updated.site_code, "new_denver")
        self.assertEqual(float(self.location2_updated.longitude), 33.9012)

    def test_successful_put2(self):
        self.kansas = SQLLocation.objects.create(
            domain=self.domain.name,
            location_id="4",
            name="Kansas",
            site_code="kansas",
            location_type=self.parent_type
        )
        put_data = {
            "parent_location_id": self.kansas.location_id,
            "location_type_code": self.county.code
        }
        response = self._assert_auth_post_resource(self.single_endpoint(self.location2.location_id),
                                                   put_data, method='PUT')
        self.assertEqual(response.status_code, 200)

        self.location2_updated = SQLLocation.objects.get(location_id=self.location2.location_id)
        self.assertEqual(self.location2_updated.location_type.code, self.county.code)

    def test_change_location_type_with_children(self):
        self.kansas = SQLLocation.objects.create(
            domain=self.domain.name,
            location_id="4",
            name="Kansas",
            site_code="kansas",
            location_type=self.parent_type
        )
        put_data = {
            "parent_location_id": self.kansas.location_id,
            "location_type_code": self.county.code
        }
        response = self._assert_auth_post_resource(self.single_endpoint(self.location1.location_id),
                                                   put_data, method='PUT')
        self.assertEqual(response.json(),
                         {'error': 'You cannot change the location type of a location with children'})
        self.assertEqual(response.status_code, 400)

    def test_invalid_parent(self):
        put_data = {
            "parent_location_id": self.south_park.location_id,
        }
        response = self._assert_auth_post_resource(self.single_endpoint(self.location2.location_id),
                                                   put_data, method='PUT')
        self.assertEqual(response.json(),
                         {'error': 'The selected parent location cannot have child locations!'})
        self.assertEqual(response.status_code, 400)

    def test_name_unique_among_siblings(self):
        post_data = post_data = {
            "location_type_code": "city",
            "name": "Denver",
            "parent_location_id": "1",
            "site_code": "second_denver"
        }
        response = self._assert_auth_post_resource(self.list_endpoint, post_data, method='POST')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(),
                         {'error': 'Location with same name and parent already exists.'})

    def test_site_code_special_chars(self):
        put_data = {
            "site_code": "special$char",
        }
        response = self._assert_auth_post_resource(self.single_endpoint(self.location2.location_id),
                                                   put_data, method='PUT')
        self.assertEqual(response.status_code, 400)

    def test_site_code_unique(self):
        put_data = {
            "site_code": "south_park",
        }
        response = self._assert_auth_post_resource(self.single_endpoint(self.location2.location_id),
                                                   put_data, method='PUT')
        self.assertEqual(response.status_code, 400)

    def test_successful_patch_list(self):
        patch_data = {
            "objects": [
                {
                    "name": "newtown",
                    "latitude": "31.41",
                    "location_type_code": self.child_type.code,
                    "parent_location_id": self.location1.location_id
                },
                {
                    "location_id": self.south_park.location_id,
                    "latitude": "32.42",
                    "parent_location_id": self.location1.location_id
                }
            ]
        }
        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   patch_data, method='PATCH')
        self.assertEqual(response.status_code, 202)

        self.assertTrue(SQLLocation.objects.filter(
            domain=self.domain.name, name="newtown").exists())
        newtown = SQLLocation.objects.get(domain=self.domain.name, name="newtown")
        self.assertEqual(newtown.parent_location_id, self.location1.location_id)
        self.assertEqual(float(newtown.latitude), 31.41)

        updated_south_park = SQLLocation.objects.get(domain=self.domain.name, name=self.south_park.name)
        self.assertEqual(float(updated_south_park.latitude), 32.42)
        self.assertEqual(updated_south_park.parent_location_id, self.location1.location_id)

    def test_patch_list_is_atomic(self):
        patch_data = {
            "objects": [
                {
                    "name": "newtown",
                    "latitude": "31.41",
                    "location_type_code": self.child_type.code,
                    "parent_location_id": self.location1.location_id
                },
                {
                    "location_id": self.south_park.location_id,
                    "latitude": "32.42",
                    "parent_location_id": self.location2.location_id  # Invalid parent
                }
            ]
        }

        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   patch_data, method='PATCH')
        self.assertEqual(response.status_code, 400)
        # "newtown" should not be created since the update to South Park failed
        self.assertFalse(SQLLocation.objects.filter(
            domain=self.domain.name, name="newtown").exists())

    def test_patch_list_missing_location_id(self):
        patch_data = {
            "objects": [
                {
                    "_id": self.south_park.location_id,  # Incorrect ID key
                    "latitude": "32.42",
                }
            ]
        }

        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   patch_data, method='PATCH')
        self.assertEqual(response.status_code, 400)

        unknown_location_id = 'qwerty'
        patch_data = {
            "objects": [
                {
                    "location_id": unknown_location_id,
                    "latitude": "32.42",
                }
            ]
        }

        response = self._assert_auth_post_resource(self.list_endpoint,
                                                   patch_data, method='PATCH')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(),
                         {'error': "Could not update: could not find location with"
                                   f" given ID {unknown_location_id} on the domain."})
