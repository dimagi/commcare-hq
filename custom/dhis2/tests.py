"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from unittest import skip
from custom.dhis2.models import Dhis2Api
from custom.dhis2.tasks import get_children_only_ours

from django.test import TestCase


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


class MockOutThisTest(TestCase):

    # host = 'http://dhis1.internal.commcarehq.org:8080/dhis'
    # username = 'admin'
    # password = 'district'
    #
    # def test_list_their_instances(self):
    #     """
    #     Get a list of tracked entity instances
    #     """
    #     dhis2_api = Dhis2Api(self.host, self.username, self.password)
    #     instances = dhis2_api.get_instances_with_unset('Child', 'Favourite Colour')
    #     self.assertIsNotNone(instances)

    def test_list_our_instances(self):
        import ipdb ; ipdb.set_trace() ###
        result = get_children_only_ours()
        self.assertIsNotNone(result)
