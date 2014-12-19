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
from mock import patch


class Dhis2OrgUnitTest(TestCase):

    @skip('Finish writing this test')
    def test_delete_dhis2_org_unit(self):
        """
        Dhis2OrgUnit.delete should succeed if it is not in use
        """

    @skip('Finish writing this test')
    def test_delete_dhis2_org_unit_fail(self):
        """
        Dhis2OrgUnit.delete should fail if it is in use
        """


class TaskTest(TestCase):

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
    def test_sync_child_entities(self):
        """
        sync_child_entities should pull and push child entities appropriately
        """
        pass

    @skip('Finish writing this test')
    def test_sync_org_units(self):
        """
        sync_org_units should import new DHIS organization units and remove deleted ones safely.
        """
        pass

    @skip('Finish writing this test')
    def test_send_nutrition_data(self):
        """
        send_nutrition_data should update DHIS2 with received nutrition data
        """
        pass


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

    def test_pull_child_entities(self):
        pass

    def test_push_child_entities(self):
        pass
