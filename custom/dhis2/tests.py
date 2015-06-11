"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from contextlib import contextmanager
from unittest import skip
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField
from corehq.apps.receiverwrapper.exceptions import IgnoreDocument
from couchdbkit import ResourceNotFound
from custom.dhis2.const import ORG_UNIT_FIXTURES, REGISTER_CHILD_XMLNS, CASE_TYPE
from custom.dhis2.models import Dhis2OrgUnit, JsonApiRequest, JsonApiError, Dhis2Api, Dhis2ApiQueryError, \
    FixtureManager
from custom.dhis2.payload_generators import FormRepeaterDhis2EventPayloadGenerator
from custom.dhis2.tasks import fetch_cases, fetch_org_units
from django.test import TestCase
from django.test.testcases import SimpleTestCase
from mock import patch, Mock, MagicMock
from couchforms.models import XFormInstance


DOMAIN = 'sheel-wvlanka-test'
SETTINGS = {
    'dhis2_enabled': False,
    'dhis2_host': '',
    'dhis2_username': '',
    'dhis2_password': '',
    'dhis2_top_org_unit_name': None
}


@contextmanager
def fixture_type_context():
    fixture_type = FixtureDataType(
        domain=DOMAIN,
        tag='dhis2_org_unit',
        fields=[FixtureTypeField(field_name='id', properties=[]),
                FixtureTypeField(field_name='name', properties=[])]
    )
    fixture_type.save()
    try:
        yield fixture_type
    finally:
        fixture_type.delete()


@contextmanager
def org_unit_context():
    org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West', parent_id=None)
    org_unit.save()
    try:
        yield org_unit
    finally:
        try:
            org_unit.delete()
        except ResourceNotFound:
            pass


@contextmanager
def response_context():
    response_mock = Mock()
    response_mock.status_code = 200
    response_mock.json.return_value = {'spam': True}
    yield response_mock


@contextmanager
def growth_monitoring_forms_context():
    forms_data = [
        {
            'child_first_name': 'Foo',
            'dhis2_te_inst_id': '',  # Not enrolled
            'dhis2_processed': ''  # Not processed
        },
        {
            'child_first_name': 'Bar',
            'dhis2_te_inst_id': '123',  # Enrolled
            'dhis2_processed': ''  # Not processed

        },
        {
            'child_first_name': 'Baz',
            'dhis2_te_inst_id': '456',  # Enrolled
            'dhis2_processed': ''  # Not processed
        }
    ]
    forms = []
    for data in forms_data:
        form = XFormInstance(domain=DOMAIN, form=data)
        form.save()
        forms.append(form)
    yield forms


class JsonApiRequestTest(SimpleTestCase):

    def test_json_or_error_returns(self):
        """
        JsonApiRequest.json_or_error should return a status code and JSON on success
        """
        with response_context() as response_mock:
            data = JsonApiRequest.json_or_error(response_mock)

            self.assertEqual(data, {'spam': True})

    def test_json_or_error_raises_404(self):
        """
        JsonApiRequest.json_or_error should raise an error on HTTP status 404
        """
        response_mock = Mock()
        response_mock.url = 'http://nowhere.example.com'
        response_mock.status_code = 404
        response_mock.text = 'Where?'

        with self.assertRaisesMessage(
                JsonApiError,
                'API request to http://nowhere.example.com failed with HTTP status 404: Where?'):
            JsonApiRequest.json_or_error(response_mock)

    def test_json_or_error_raises_500(self):
        """
        JsonApiRequest.json_or_error should raise an error on HTTP status 500
        """
        response_mock = Mock()
        response_mock.url = 'http://broken.example.com'
        response_mock.status_code = 500
        response_mock.text = 'Oops!'

        with self.assertRaisesMessage(
                JsonApiError,
                'API request to http://broken.example.com failed with HTTP status 500: Oops!'):
            JsonApiRequest.json_or_error(response_mock)

    def test_get_calls_requests(self):
        """
        JsonApiRequest.get should call requests.get and return the JSON result
        """
        with patch('requests.get') as requests_mock, \
                response_context() as response_mock:
            requests_mock.return_value = response_mock

            request = JsonApiRequest('http://www.example.com', 'admin', 's3cr3t')
            data = request.get('ham/eggs')

            requests_mock.assert_called_with(
                'http://www.example.com/api/ham/eggs',
                headers={'Accept': 'application/json'},
                auth=('admin', 's3cr3t'))
            self.assertEqual(data, {'spam': True})

    def test_post_calls_requests(self):
        """
        JsonApiRequest.post should call requests.post and return the JSON result
        """
        with patch('requests.post') as requests_mock, \
                response_context() as response_mock:
            requests_mock.return_value = response_mock

            request = JsonApiRequest('http://www.example.com', 'admin', 's3cr3t')
            data = request.post('ham/eggs', {'ham': True})

            requests_mock.assert_called_with(
                'http://www.example.com/api/ham/eggs',
                '{"ham": true}',
                headers={'Content-type': 'application/json', 'Accept': 'application/json'},
                auth=('admin', 's3cr3t'))
            self.assertEqual(data, {'spam': True})

    def test_put_calls_requests(self):
        """
        JsonApiRequest.put should call requests.get and return the JSON result
        """
        with patch('requests.put') as requests_mock, \
                response_context() as response_mock:
            requests_mock.return_value = response_mock

            request = JsonApiRequest('http://www.example.com', 'admin', 's3cr3t')
            data = request.put('ham/eggs', {'ham': True})

            requests_mock.assert_called_with(
                'http://www.example.com/api/ham/eggs',
                '{"ham": true}',
                headers={'Content-type': 'application/json', 'Accept': 'application/json'},
                auth=('admin', 's3cr3t'))
            self.assertEqual(data, {'spam': True})


class Dhis2ApiTest(SimpleTestCase):

    def test__fetch_tracked_entity_attributes(self):
        """
        _fetch_tracked_entity_attributes should extend _tracked_entity_attributes
        """
        te_attrs = {'trackedEntityAttributes': [
            {'name': 'ham', 'id': 'deadbeef'},
            {'name': 'spam', 'id': 'c0ffee'},
        ]}
        dhis2_api = Dhis2Api('http://example.com/dhis', 'user', 'p4ssw0rd')
        dhis2_api._request.get = Mock(return_value=te_attrs)
        keys_before = set(dhis2_api._tracked_entity_attributes.keys())
        dhis2_api._fetch_tracked_entity_attributes()
        keys_after = set(dhis2_api._tracked_entity_attributes.keys())
        fetched = keys_after - keys_before
        self.assertIn('ham', fetched)
        self.assertIn('spam', fetched)

    @skip('Finish writing this test')
    def test_add_te_inst(self):
        pass

    @skip('Finish writing this test')
    def test_update_te_inst(self):
        pass

    @skip('Requires settings for live DHIS2 server')
    def test_get_top_org_unit_settings(self):
        """
        get_top_org_unit should return the name and ID of the org unit specified in settings
        """
        if not SETTINGS['dhis2_top_org_unit_name']:
            self.skipTest('An org unit is not set in settings.py')
        dhis2_api = Dhis2Api(SETTINGS['dhis2_host'], SETTINGS['dhis2_username'], SETTINGS['dhis2_password'])
        org_unit = dhis2_api.get_top_org_unit()
        self.assertEqual(org_unit['name'], SETTINGS['dhis2_top_org_unit_name'])
        self.assertTrue(bool(org_unit['id']))

    @skip('Requires settings for live DHIS2 server')
    def test_get_top_org_unit(self):
        """
        get_top_org_unit should return the name and ID of the top org unit
        """
        # TODO: Make sure get_top_org_unit navigates up tree of org units
        dhis2_api = Dhis2Api(SETTINGS['dhis2_host'], SETTINGS['dhis2_username'], SETTINGS['dhis2_password'])
        org_unit = dhis2_api.get_top_org_unit()
        self.assertTrue(bool(org_unit['name']))
        self.assertTrue(bool(org_unit['id']))

    def test_get_resource_id(self):
        """
        get_resource_id should query the API for the details of a named resource, and return the ID
        """
        if not SETTINGS['dhis2_enabled']:
            self.skipTest('DHIS2 is not configured')
        resources = {'Knights': [
            {'name': 'Michael Palin', 'id': 'c0ffee'},
        ]}
        dhis2_api = Dhis2Api(SETTINGS['dhis2_host'], SETTINGS['dhis2_username'], SETTINGS['dhis2_password'])
        dhis2_api._request.get = Mock(return_value=('foo', resources))

        result = dhis2_api.get_resource_id('Knights', 'Who Say "Ni!"')

        dhis2_api._request.get.assert_called_with('Knights', params={'links': 'false', 'query': 'Who Say "Ni!"'})
        self.assertEqual(result, 'c0ffee')

    def test_get_resource_id_none(self):
        """
        get_resource_id should return None if none found
        """
        if not SETTINGS['dhis2_enabled']:
            self.skipTest('DHIS2 is not configured')
        resources = {'Knights': []}
        dhis2_api = Dhis2Api(SETTINGS['dhis2_host'], SETTINGS['dhis2_username'], SETTINGS['dhis2_password'])
        dhis2_api._request.get = Mock(return_value=('foo', resources))

        result = dhis2_api.get_resource_id('Knights', 'Who Say "Ni!"')

        self.assertIsNone(result)

    def test_get_resource_id_raises(self):
        """
        get_resource_id should raise Dhis2ApiQueryError if multiple found
        """
        if not SETTINGS['dhis2_enabled']:
            self.skipTest('DHIS2 is not configured')
        resources = {'Knights': [
            {'name': 'Michael Palin', 'id': 'c0ffee'},
            {'name': 'John Cleese', 'id': 'deadbeef'}
        ]}
        dhis2_api = Dhis2Api(SETTINGS['dhis2_host'], SETTINGS['dhis2_username'], SETTINGS['dhis2_password'])
        dhis2_api._request.get = Mock(return_value=('foo', resources))

        with self.assertRaises(Dhis2ApiQueryError):
            dhis2_api.get_resource_id('Knights', 'Who Say "Ni!"')

    @skip('Finish writing this test')
    def test_form_to_event(self):
        form = XFormInstance(
            domain='Foo',
            form={
                'name': ''
            }
        )

    @skip('Finish writing this test')
    def test_entities_to_dicts(self):
        pass


class FixtureManagerTest(SimpleTestCase):
    pass


class Dhis2OrgUnitTest(TestCase):

    def test_save(self):
        """
        Dhis2OrgUnit.save should save a FixtureDataItem
        """
        # with fixture_type_context(), \
        #         patch('corehq.apps.fixtures.models.FixtureDataItem') as data_item_patch, \
        #         patch('couchdbkit.schema.base.DocumentBase.save') as save_patch:
        #     data_item_mock = Mock()
        #     data_item_mock.save.return_value = None
        #     data_item_mock.get_id = '123'
        #     data_item_patch.return_value = data_item_mock
        #
        #     org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West', parent_id=None)
        #     id_ = org_unit.save()
        #
        #     data_item_patch.assert_called()
        #     data_item_mock.save.assert_called()  # Which one gets called. Why?
        #     save_patch.assert_called()
        #     self.assertEqual(id_, '123')
        #     self.assertEqual(org_unit._fixture_id, '123')

        # TODO: Figure out why mocks above don't work.
        # In the meantime ...
        with fixture_type_context():
            Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, DOMAIN, ORG_UNIT_FIXTURES)
            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West', parent_id=None)
            id_ = org_unit.save()
            self.assertIsNotNone(id_)
            self.assertIsNotNone(org_unit._fixture_id)

    def test_delete_dhis2_org_unit_does_nothing(self):
        """
        Dhis2OrgUnit.delete should do nothing if it's not saved
        """
        with fixture_type_context(), \
                patch('corehq.apps.fixtures.models.FixtureDataItem.get') as mock_get:
            data_item_mock = Mock()
            mock_get.return_value = data_item_mock

            Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, DOMAIN, ORG_UNIT_FIXTURES)
            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West', parent_id=None)
            org_unit.delete()

            self.assertFalse(mock_get.called)
            self.assertFalse(data_item_mock.delete.called)

    def test_delete_dhis2_org_unit_deletes(self):
        """
        Dhis2OrgUnit.delete should delete if it's saved
        """
        with fixture_type_context(), \
                patch('corehq.apps.fixtures.models.FixtureDataItem') as data_item_patch, \
                patch('couchdbkit.schema.base.DocumentBase.get') as get_patch:
            data_item_mock = Mock()
            data_item_mock.get_id.return_value = '123'
            data_item_patch.return_value = data_item_mock
            doc_mock = Mock()
            get_patch.return_value = data_item_mock

            Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, DOMAIN, ORG_UNIT_FIXTURES)
            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West', parent_id=None)
            org_unit.save()
            org_unit.delete()

            doc_mock.get.assert_called()
            data_item_mock.delete.assert_called()


class TaskTest(SimpleTestCase):

    def setUp(self):
        # TODO: Enable DHIS2
        pass

    @skip('Fix mocks')
    def test_fetch_org_units_dict_comps(self):
        """
        sync_org_units should create dictionaries of CCHQ and DHIS2 org units
        """
        with patch('custom.dhis2.models.Dhis2Api.gen_org_units') as gen_org_units_patch, \
                patch('custom.dhis2.models.FixtureManager.all') as objects_all_patch:
            ou_dict = {'id': '1', 'name': 'Sri Lanka'}
            ou_obj = type('OrgUnit', (object,), ou_dict)  # An object with attributes the same as ou_dict items
            gen_org_units_patch.side_effect = lambda: (d for d in [ou_dict])  # Generates org unit dicts
            objects_all_patch.side_effect = lambda: (o for o in [ou_obj])  # Generates org unit objects

            fetch_org_units()

            gen_org_units_patch.assert_called()
            objects_all_patch.assert_called()

    # TODO: No point in running this test if Dhis2OrgUnit patch doesn't work -- nothing to assert
    @skip('Fix mocks')
    def test_fetch_org_units_adds(self):
        """
        sync_org_units should add new org units
        """
        with fixture_type_context(), \
                patch('custom.dhis2.models.Dhis2Api.gen_org_units') as gen_org_units_patch, \
                patch('custom.dhis2.models.FixtureManager.all') as objects_all_patch, \
                patch('custom.dhis2.models.Dhis2OrgUnit') as org_unit_patch:
            ou_dict = {'id': '1', 'name': 'Sri Lanka'}
            gen_org_units_patch.side_effect = lambda: (d for d in [ou_dict])
            objects_all_patch.side_effect = lambda: (o for o in [])

            fetch_org_units()

            org_unit_patch.__init__.assert_called_with(id='1', name='Sri Lanka')
            org_unit_patch.save.assert_called()

    @skip('Fix mocks')
    def test_fetch_org_units_deletes(self):
        """
        sync_org_units should delete old org units
        """
        with patch('custom.dhis2.models.Dhis2Api.gen_org_units') as gen_org_units_patch, \
                patch('custom.dhis2.models.FixtureManager.all') as objects_all_patch:
            delete_mock = Mock()
            ou_obj = type('OrgUnit', (object,), {'id': '1', 'name': 'Sri Lanka', 'delete': delete_mock})
            gen_org_units_patch.side_effect = lambda: (d for d in [])
            objects_all_patch.side_effect = lambda: (o for o in [ou_obj])

            fetch_org_units()

            delete_mock.assert_called()

    @skip('Fix mocks')
    def test_fetch_cases(self):
        with patch('custom.dhis2.tasks.get_children_only_theirs') as only_theirs_mock, \
                patch('custom.dhis2.tasks.pull_child_entities') as pull_mock, \
                patch('custom.dhis2.tasks.gen_children_only_ours') as only_ours_mock, \
                patch('custom.dhis2.tasks.push_child_entities') as push_mock:
            foo = object()
            bar = object()
            only_theirs_mock.return_value = foo
            only_ours_mock.return_value = bar

            fetch_cases()

            only_theirs_mock.assert_called()
            pull_mock.assert_called_with(DOMAIN, foo)
            only_ours_mock.assert_called_with(DOMAIN)
            push_mock.assert_called_with(bar)


class PayloadGeneratorTest(SimpleTestCase):

    def test_get_payload_ignores_unknown_form(self):
        """
        get_payload should raise IgnoreDocument on unknown form XMLNS
        """
        form_mock = {'xmlns': 'unknown', 'domain': 'test-domain'}
        payload_generator = FormRepeaterDhis2EventPayloadGenerator(None)
        with self.assertRaises(IgnoreDocument):
            payload_generator.get_payload(None, form_mock)

    @patch('custom.dhis2.payload_generators.push_case')
    @patch('casexml.apps.case.xform.cases_referenced_by_xform')
    @patch('custom.dhis2.payload_generators.Dhis2Settings')
    def test_get_payload_ignores_registration(self, Dhis2SettingsPatch, cases_referenced_by_xform, push_case):

        """
        get_payload should raise IgnoreDocument given a registration form
        """
        case_mock = Mock()
        case_mock.type = CASE_TYPE
        cases_referenced_by_xform.return_value = [case_mock]

        class Settings(object):
            dhis2 = {'host': 'foo', 'username': 'foo', 'password': 'foo', 'top_org_unit_name': 'foo'}
        Dhis2SettingsPatch.for_domain.return_value = Settings()

        form_mock = MagicMock()
        form_mock.__getitem__.return_value = REGISTER_CHILD_XMLNS

        payload_generator = FormRepeaterDhis2EventPayloadGenerator(None)
        with self.assertRaises(IgnoreDocument):
            payload_generator.get_payload(None, form_mock)
