from __future__ import absolute_import, unicode_literals

import json

from corehq.apps.api.tests.utils import APIResourceTest
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField
from corehq.apps.fixtures.resources.v0_1 import LookupTableResource


class TestLookupTableResource(APIResourceTest):
    resource = LookupTableResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestLookupTableResource, cls).setUpClass()
        cls.data_type = FixtureDataType(
            domain=cls.domain.name,
            tag="lookup_table",
            fields=[
                FixtureTypeField(
                    field_name="fixture_property",
                    properties=["lang", "name"]
                )
            ],
            item_attributes=[]
        )
        cls.data_type.save()

    @classmethod
    def tearDownClass(cls):
        cls.data_type.delete()
        super(TestLookupTableResource, cls).tearDownClass()

    def _data_type_json(self):
        return {
            "fields": [
                {
                    "field_name": "fixture_property",
                    "properties": ["lang", "name"],
                },
            ],
            "id": self.data_type._id,
            "is_global": True,
            "resource_uri": "",
            "tag": "lookup_table"
        }

    def test_get_list(self):
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        fixture_data_types = json.loads(response.content)['objects']
        self.assertEqual(len(fixture_data_types), 1)
        self.assertEqual(fixture_data_types, self._data_type_json())

    def test_get_single(self):
        response = self._assert_auth_get_resource(self.single_endpoint(self.data_type._id))
        self.assertEqual(response.status_code, 200)

        fixture_data_type = json.loads(response.content)
        self.assertEqual(fixture_data_type, self._data_type_json())

    def test_delete(self):
        data_type = FixtureDataType(
            domain=self.domain.name,
            tag="lookup_table2",
            fields=[
                FixtureTypeField(
                    field_name="fixture_property",
                    properties=["lang", "name"]
                )
            ],
            item_attributes=[]
        )
        data_type.save()
        self.addCleanup(data_type.delete)

        self.assertEqual(2, len(FixtureDataType.by_domain(self.domain.name)))
        response = self._assert_auth_post_resource(self.single_endpoint(data_type._id), '', method='DELETE')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(1, len(FixtureDataType.by_domain(self.domain.name)))

    def test_create(self):
        lookup_table = {
            "tag": "table_name",
            "fields": [{
                "field_name": "fieldA",
                "properties": ["property1", "property2"]
            }]
        }

        response = self._assert_auth_post_resource(
            self.list_endpoint, json.dumps(lookup_table), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data_type = FixtureDataType.by_domain_tag(self.domain.name, "table_name").first()
        self.addCleanup(data_type.delete)
        self.assertEqual(data_type.tag, "table_name")
        self.assertEqual(len(data_type.fields), 1)
        self.assertEqual(data_type.fields[0]['fieldname'], 'fieldA')
        self.assertEqual(data_type.fields[0]['properties'], ['property1', 'property2'])
