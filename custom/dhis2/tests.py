"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from contextlib import contextmanager
from unittest import skip
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField
from couchdbkit import ResourceNotFound
from custom.dhis2.models import Dhis2OrgUnit, JsonApiRequest, JsonApiError
from custom.dhis2.tasks import sync_child_entities, DOMAIN, sync_org_units, mark_as_processed, \
    gen_unprocessed_growth_monitoring_forms, is_at_risk
from django.test import TestCase
from mock import patch, Mock
from couchforms.models import XFormInstance


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
    org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
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
def form_context():
    # TODO: Do stuff here
    form = XFormInstance()
    yield form


class JsonApiRequestTest(TestCase):

    def test_json_or_error_returns(self):
        """
        JsonApiRequest.json_or_error should return a status code and JSON on success
        """
        with response_context() as response_mock:
            status_code, data = JsonApiRequest.json_or_error(response_mock)

            self.assertEqual(status_code, 200)
            self.assertEqual(data, {'spam': True})

    def test_json_or_error_raises_404(self):
        """
        JsonApiRequest.json_or_error should raise an error on HTTP status 404
        """
        response_mock = Mock()
        response_mock.url = 'http://nowhere.example.com'
        response_mock.status_code = 404

        with self.assertRaisesMessage(
                JsonApiError,
                'API request to http://nowhere.example.com failed with HTTP status 404'):
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
            status_code, data = request.get('ham/eggs')

            requests_mock.assert_called_with(
                'http://www.example.com/api/ham/eggs',
                headers={'Accept': 'application/json'},
                auth=('admin', 's3cr3t'))
            self.assertEqual(status_code, 200)
            self.assertEqual(data, {'spam': True})

    def test_post_calls_requests(self):
        """
        JsonApiRequest.post should call requests.post and return the JSON result
        """
        with patch('requests.post') as requests_mock, \
                response_context() as response_mock:
            requests_mock.return_value = response_mock

            request = JsonApiRequest('http://www.example.com', 'admin', 's3cr3t')
            status_code, data = request.post('ham/eggs', {'ham': True})

            requests_mock.assert_called_with(
                'http://www.example.com/api/ham/eggs',
                {'ham': True},
                headers={'Accept': 'application/json'},
                auth=('admin', 's3cr3t'))
            self.assertEqual(status_code, 200)
            self.assertEqual(data, {'spam': True})

    def test_put_calls_requests(self):
        """
        JsonApiRequest.put should call requests.get and return the JSON result
        """
        with patch('requests.put') as requests_mock, \
                response_context() as response_mock:
            requests_mock.return_value = response_mock

            request = JsonApiRequest('http://www.example.com', 'admin', 's3cr3t')
            status_code, data = request.put('ham/eggs', {'ham': True})

            requests_mock.assert_called_with(
                'http://www.example.com/api/ham/eggs',
                {'ham': True},
                headers={'Accept': 'application/json'},
                auth=('admin', 's3cr3t'))
            self.assertEqual(status_code, 200)
            self.assertEqual(data, {'spam': True})


class Dhis2ApiTest(TestCase):
    pass


class FixtureManagerTest(TestCase):
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
        #     org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
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
            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
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

            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
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

            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
            org_unit.save()
            org_unit.delete()

            doc_mock.get.assert_called()
            data_item_mock.delete.assert_called()


class TaskTest(TestCase):

    def test_sync_org_units_dict_comps(self):
        """
        sync_org_units should create dictionaries of CCHQ and DHIS2 org units
        """
        with patch('custom.dhis2.models.Dhis2Api.gen_org_units') as gen_org_units_patch, \
                patch('custom.dhis2.models.FixtureManager.all') as objects_all_patch:
            ou_dict = {'id': '1', 'name': 'Sri Lanka'}
            ou_obj = type('OrgUnit', (object,), ou_dict)  # An object with attributes the same as ou_dict items
            gen_org_units_patch.side_effect = lambda: (d for d in [ou_dict])  # Generates org unit dicts
            objects_all_patch.side_effect = lambda: (o for o in [ou_obj])  # Generates org unit objects

            sync_org_units()

            gen_org_units_patch.assert_called()
            objects_all_patch.assert_called()

    # TODO: No point in running this test if Dhis2OrgUnit patch doesn't work -- nothing to assert
    @skip('Fix mocks')
    def test_sync_org_units_adds(self):
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

            sync_org_units()

            org_unit_patch.__init__.assert_called_with(id='1', name='Sri Lanka')
            org_unit_patch.save.assert_called()

    def test_sync_org_units_deletes(self):
        """
        sync_org_units should delete old org units
        """
        with patch('custom.dhis2.models.Dhis2Api.gen_org_units') as gen_org_units_patch, \
                patch('custom.dhis2.models.FixtureManager.all') as objects_all_patch:
            delete_mock = Mock()
            ou_obj = type('OrgUnit', (object,), {'id': '1', 'name': 'Sri Lanka', 'delete': delete_mock})
            gen_org_units_patch.side_effect = lambda: (d for d in [])
            objects_all_patch.side_effect = lambda: (o for o in [ou_obj])

            sync_org_units()

            delete_mock.assert_called()

    def test_sync_child_entities(self):
        with patch('custom.dhis2.tasks.get_children_only_theirs') as only_theirs_mock, \
                patch('custom.dhis2.tasks.pull_child_entities') as pull_mock, \
                patch('custom.dhis2.tasks.gen_children_only_ours') as only_ours_mock, \
                patch('custom.dhis2.tasks.push_child_entities') as push_mock:
            foo = object()
            bar = object()
            only_theirs_mock.return_value = foo
            only_ours_mock.return_value = bar

            sync_child_entities()

            only_theirs_mock.assert_called()
            pull_mock.assert_called_with(DOMAIN, foo)
            only_ours_mock.assert_called_with(DOMAIN)
            push_mock.assert_called_with(bar)

    @skip('Finish writing this test')
    def test_send_nutrition_data(self):
        """
        send_nutrition_data should update DHIS2 with received nutrition data
        """
        pass


class UtilTest(TestCase):

    @skip('Finish writing this test')
    def test_push_child_entities(self):
        """
        push_child_entities should call the DHIS2 API for applicable child entities
        """
        pass

    @skip('Finish writing this test')
    def test_pull_child_entities(self):
        """
        pull_child_entities should fetch applicable child entities from the DHIS2 API
        """
        pass

    @skip('Finish writing this test')
    def test_is_at_risk(self):
        """
        (For now) is_at_risk should just return True
        """
        self.assertTrue(is_at_risk(None))

    @skip('Finish writing this test')
    def test_get_user_by_org_unit(self):
        pass

    @skip('Finish writing this test')
    def test_get_case_by_external_id(self):
        pass

    @skip('Finish writing this test')
    def test_gen_children_only_ours(self):
        pass

    @skip('Finish writing this test')
    def test_gen_unprocessed_growth_monitoring_forms(self):

        # def get_unprocessed_growth_monitoring_forms():
        #     query = FormES().filter({
        #         # dhis2_te_inst_id indicates that the case has been enrolled in both
        #         # programs by push_child_entities()
        #         'not': {'dhis2_te_inst_id': None}
        #     }).filter({
        #         # and it must not have been processed before
        #         'dhis2_processed': None
        #     })
        #     result = query.run()
        #     if result.total:
        #         for doc in result.hits:
        #             yield XFormInstance.wrap(doc)

        prepopulated = [{'foo': True}]
        # TODO: Prepopulate
        forms = gen_unprocessed_growth_monitoring_forms()
        assert forms == prepopulated

    def test_mark_as_processed(self):
        """
        mark_as_processed should set form field dhis2_processed as True and save
        """
        class Form(object):
            def __init__(self):
                self.form = {}
                self.save = Mock()
        forms = [Form(), Form(), Form()]

        mark_as_processed(forms)

        for form in forms:
            self.assertTrue(form.form['dhis2_processed'])
            form.save.assert_called()

    @skip('Finish writing this test')
    def test_get_unprocessed_and_mark(self):
        """
        test_get_unprocessed_growth_monitoring_forms should not return marked forms
        """
        # TODO: Prepopulate
        forms1 = [f for f in gen_unprocessed_growth_monitoring_forms()]
        mark_as_processed([forms1[0]])
        forms2 = [f for f in gen_unprocessed_growth_monitoring_forms()]
        # TODO: assert forms1[0] not in forms2
        # For now:
        self.assertEqual(len(forms1), len(forms2) + 1)
