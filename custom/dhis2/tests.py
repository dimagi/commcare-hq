"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from contextlib import contextmanager
from unittest import skip
from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField
from couchdbkit import ResourceNotFound
from custom.dhis2.models import Dhis2Api, Dhis2OrgUnit
from custom.dhis2.tasks import push_child_entities, gen_children_only_ours, sync_child_entities, DOMAIN, sync_org_units

from django.test import TestCase
from mock import patch, Mock


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


class JsonApiRequestTest(TestCase):
    pass


class Dhis2ApiTest(TestCase):
    pass


class FixtureManagerTest(TestCase):
    pass


class Dhis2OrgUnitTest(TestCase):

    def test_save(self):
        """
        Dhis2OrgUnit.save should save a FixtureDataItem
        """
        with fixture_type_context(), \
                patch('corehq.apps.fixtures.models.FixtureDataItem.__init__') as mock_init:
            data_item_mock = Mock()
            data_item_mock.get_id.return_value = '123'
            mock_init.return_value = data_item_mock

            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
            id_ = org_unit.save()

            mock_init.assert_called()
            data_item_mock.save.assert_called()
            self.assertEqual(id_, '123')
            self.assertEqual(org_unit._fixture_id, '123')

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
                patch('corehq.apps.fixtures.models.FixtureDataItem.__init__') as mock_init, \
                patch('corehq.apps.fixtures.models.FixtureDataItem.get') as mock_get:
            data_item_mock = Mock()
            data_item_mock.get_id.return_value = '123'
            mock_init.return_value = data_item_mock
            mock_get.return_value = data_item_mock

            org_unit = Dhis2OrgUnit(id='QXOOG2Foong', name='Somerset West')
            org_unit.save()
            org_unit.delete()

            mock_get.assert_called()
            data_item_mock.delete.assert_called()


class TaskTest(TestCase):

    def test_sync_org_units_dict_comps(self):
        """
        sync_org_units should create dictionaries of CCHQ and DHIS2 org units
        """
        with patch('dhis2_api.gen_org_units') as gen_org_units_patch, \
                patch('Dhis2OrgUnit.objects.all') as objects_all_patch:
            ou_dict = {'id': '1', 'name': 'Sri Lanka'}
            ou_obj = type('OrgUnit', (object,), ou_dict)  # An object with attributes == ou_dict items
            gen_org_units_patch.side_effect = lambda: (d for d in ou_dict)  # Generates org unit dicts
            objects_all_patch.side_effect = lambda: (o for o in ou_obj)  # Generates org unit objects

            sync_org_units()

            gen_org_units_patch.assert_called()
            objects_all_patch.assert_called()

    def test_sync_org_units_adds(self):
        """
        sync_org_units should add new org units
        """
        with patch('dhis2_api.gen_org_units') as gen_org_units_patch, \
                patch('Dhis2OrgUnit.objects.all') as objects_all_patch, \
                patch('Dhis2OrgUnit') as org_unit_patch:
            ou_dict = {'id': '1', 'name': 'Sri Lanka'}
            gen_org_units_patch.side_effect = lambda: (d for d in ou_dict)
            objects_all_patch.side_effect = lambda: (o for o in [])

            sync_org_units()

            org_unit_patch.__init__.assert_called_with(id='1', name='Sri Lanka')
            org_unit_patch.save.assert_called()

    def test_sync_org_units_deletes(self):
        """
        sync_org_units should delete old org units
        """
        with patch('dhis2_api.gen_org_units') as gen_org_units_patch, \
                patch('Dhis2OrgUnit.objects.all') as objects_all_patch:
            delete_mock = Mock()
            ou_obj = type('OrgUnit', (object,), {'id': '1', 'name': 'Sri Lanka', 'delete': delete_mock})
            gen_org_units_patch.side_effect = lambda: (d for d in [])
            objects_all_patch.side_effect = lambda: (o for o in ou_obj)

            sync_org_units()

            delete_mock.assert_called()

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


class MockOutThisTest(TestCase):

    # host = 'http://dhis1.internal.commcarehq.org:8080/dhis'
    host = 'http://localhost:8082'
    username = 'admin'
    password = 'district'

    domain = DOMAIN

    def step_into_sync_org_units(self):
        import ipdb; ipdb.set_trace()
        with fixture_type_context(), org_unit_context():
            sync_org_units()

    def test_list_their_instances(self):
        """
        Get a list of tracked entity instances
        """
        dhis2_api = Dhis2Api(self.host, self.username, self.password)
        instances = dhis2_api.gen_instances_with_unset('Child', 'Favourite Colour')
        i = 0
        for inst in instances:
            # >>> inst
            # {u'Created': u'2014-11-27 19:56:31.658',
            #  u'Instance': u'hgptfZK1XAC',
            #  u'Last updated': u'2014-11-27 19:56:31.831',
            #  u'Org unit': u'Thu5YoRCV8y',
            #  u'Tracked entity': u'child'}
            i += 1
            break
        self.assertNotEqual(i, 0)

    def test_list_our_instances(self):
        gen = gen_children_only_ours(self.domain)
        try:
            next(gen)
        except StopIteration:
            self.fail('Expected at least one instance of case type "child_gmp"')

    def step_into_sync_child_entities(self):
        import ipdb; ipdb.set_trace()
        sync_child_entities()
