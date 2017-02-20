from datetime import date
from django.test import SimpleTestCase
from corehq.apps.dhis2.models import JsonApiRequest, DataValue


TEST_API_URL = 'http://localhost:9080/api/'
TEST_API_USERNAME = 'admin'
TEST_API_PASSWORD = 'district'
TEST_ORG_UNIT = {
    'shortName': 'USC',
    'name': 'The United States of Canada',
    'openingDate': date(2017, 2, 17)
}
TEST_CATEGORY_COMBO = {
    'shortName': 'Test Combo',
    'name': 'Test Category Combination',
    'dataDimensionType': 'ATTRIBUTE',
}
TEST_DATA_ELEMENT = {
    'shortName': 'avg hand size',
    'name': 'Average hand size (mm)',
    'aggregationType': 'AVERAGE',
    'domainType': 'AGGREGATE',
    # 'categoryCombo': {'id': TBD},
    'valueType': 'INTEGER_POSITIVE',
}


class JsonApiRequestTests(SimpleTestCase):

    @classmethod
    def _add_user_to_org_unit(cls, user_id, org_unit_id):
        user_data = cls.api.get('users/' + user_id)
        user_data['organisationUnits'].append({'id': org_unit_id})
        cls.api.put('users/' + user_id, user_data)

    @classmethod
    def _remove_user_from_org_unit(cls, user_id, org_unit_id):
        user_data = cls.api.get('users/' + user_id)
        user_data['organisationUnits'] = [ou for ou in user_data['organisationUnits'] if ou['id'] != org_unit_id]
        cls.api.put('users/' + user_id, user_data)

    @classmethod
    def _get_or_create(cls, resource_list, data):
        response = cls.api.get(resource_list)
        for item in response[resource_list]:
            if item['displayName'] == data['name']:
                return item['id']
        response = cls.api.post(resource_list, data)
        return response['response']['lastImported']

    @classmethod
    def setUpClass(cls):
        cls.api = JsonApiRequest(TEST_API_URL, TEST_API_USERNAME, TEST_API_PASSWORD)

        response = cls.api.get('me')
        cls.user_id = response['id']

        cls.org_unit_id = cls._get_or_create('organisationUnits', TEST_ORG_UNIT)
        cls._add_user_to_org_unit(cls.user_id, cls.org_unit_id)

        cls.cat_combo_id = cls._get_or_create('categoryCombos', TEST_CATEGORY_COMBO)

        TEST_DATA_ELEMENT['categoryCombo'] = {'id': cls.cat_combo_id}
        cls.data_element_id = cls._get_or_create('dataElements', TEST_DATA_ELEMENT)

    @classmethod
    def tearDownClass(cls):
        # We can't tear down the data we created, because we can't delete data elements without deleting data
        # value audits, and we can only do that directly from the database. But we can remove the user from the
        # test org unit:
        cls._remove_user_from_org_unit(cls.user_id, cls.org_unit_id)

    def test_authentication(self):
        me = self.api.get('me')
        self.assertEqual(me['code'], TEST_API_USERNAME)

    def test_send_data_value_set(self):
        response = self.api.post('dataValueSets', {'dataValues': [
            DataValue(dataElement=self.data_element_id, period="201701", orgUnit=self.org_unit_id, value="180"),
            DataValue(dataElement=self.data_element_id, period="201702", orgUnit=self.org_unit_id, value="200"),
        ]})
        self.assertEqual(response['status'], 'SUCCESS')
        self.assertEqual(response['importCount']['imported'], 2)
