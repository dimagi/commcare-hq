from __future__ import absolute_import

from __future__ import unicode_literals
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import WebUser
from custom.icds_reports.views import LocationView, LocationAncestorsView

import json
import mock


class TestLocationView(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationView, cls).setUpClass()
        cls.domain = create_domain('icds-test')
        state = LocationType.objects.create(
            domain=cls.domain.name,
            name='state',
            parent_type=None
        )
        district = LocationType.objects.create(
            domain=cls.domain.name,
            name='district',
            parent_type=state
        )
        block = LocationType.objects.create(
            domain=cls.domain.name,
            name='block',
            parent_type=district
        )
        supervisor = LocationType.objects.create(
            domain=cls.domain.name,
            name='supervisor',
            parent_type=block
        )
        awc = LocationType.objects.create(
            domain=cls.domain.name,
            name='awc',
            parent_type=supervisor
        )

        cls.state = SQLLocation.objects.create(
            name='Test State',
            domain=cls.domain.name,
            location_type=state
        )
        cls.district = SQLLocation.objects.create(
            name='Test District',
            domain=cls.domain.name,
            location_type=district,
            parent=cls.state,
        )
        cls.block = SQLLocation.objects.create(
            name='Test Block',
            domain=cls.domain.name,
            location_type=block,
            parent=cls.district
        )
        cls.supervisor = SQLLocation.objects.create(
            name='Test Supervisor',
            domain=cls.domain.name,
            location_type=supervisor,
            parent=cls.block
        )
        cls.awc = SQLLocation.objects.create(
            name='Test AWC',
            domain=cls.domain.name,
            location_type=awc,
            parent=cls.supervisor
        )
        cls.state_2 = SQLLocation.objects.create(
            name='Test State 2',
            domain=cls.domain.name,
            location_type=state
        )
        cls.district_2 = SQLLocation.objects.create(
            name='Test District 2',
            domain=cls.domain.name,
            location_type=district,
            parent=cls.state_2,
        )
        cls.block_2 = SQLLocation.objects.create(
            name='Test Block 2',
            domain=cls.domain.name,
            location_type=block,
            parent=cls.district_2
        )
        cls.supervisor_2 = SQLLocation.objects.create(
            name='Test Supervisor 2',
            domain=cls.domain.name,
            location_type=supervisor,
            parent=cls.block_2
        )
        cls.awc_2 = SQLLocation.objects.create(
            name='Test AWC 2',
            domain=cls.domain.name,
            location_type=awc,
            parent=cls.supervisor_2
        )
        cls.state_3 = SQLLocation.objects.create(
            name='Test State 3',
            domain=cls.domain.name,
            location_type=state
        )
        cls.district_3_1 = SQLLocation.objects.create(
            name='Test District 3_1',
            domain=cls.domain.name,
            location_type=district,
            parent=cls.state_3,
        )
        cls.district_3_2 = SQLLocation.objects.create(
            name='Test District 3_2',
            domain=cls.domain.name,
            location_type=district,
            parent=cls.state_3,
        )
        cls.block_3 = SQLLocation.objects.create(
            name='Test Block 3',
            domain=cls.domain.name,
            location_type=block,
            parent=cls.district_3_1
        )
        cls.supervisor_3 = SQLLocation.objects.create(
            name='Test Supervisor 3',
            domain=cls.domain.name,
            location_type=supervisor,
            parent=cls.block_3
        )
        cls.awc_3 = SQLLocation.objects.create(
            name='Test AWC 3',
            domain=cls.domain.name,
            location_type=awc,
            parent=cls.supervisor_3
        )
        cls.factory = RequestFactory()
        cls.user = WebUser.create(cls.domain.name, 'test', 'passwordtest')
        cls.user.is_authenticated = True
        cls.user.is_superuser = True
        cls.user.is_authenticated = True
        cls.user.is_active = True

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.user.delete()
        cls.awc_3.delete()
        cls.awc_2.delete()
        cls.awc.delete()
        cls.supervisor_3.delete()
        cls.supervisor_2.delete()
        cls.supervisor.delete()
        cls.block_3.delete()
        cls.block_2.delete()
        cls.block.delete()
        cls.district_3_2.delete()
        cls.district_3_1.delete()
        cls.district_2.delete()
        cls.district.delete()
        cls.state_3.delete()
        cls.state_2.delete()
        cls.state.delete()
        super(TestLocationView, cls).tearDownClass()

    def test_request_without_location_id(self):
        if self.factory is None:
            return
        view = LocationView.as_view()
        url = 'icds_locations'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse)
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                },
                {
                    'name': 'Test State 3',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_3.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_request_without_location_id_with_location_restriction(self):
        if self.factory is None:
            return
        view = LocationView.as_view()
        url = 'icds_locations'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse)
        self.user.set_location(self.domain.name, self.block_2)
        request.user = self.user
        expected = {
            'locations': [
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': False,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.block_2.location_id)
        self.assertDictEqual(expected, json.loads(response.content))

    def test_request_with_location_id(self):
        if self.factory is None:
            return
        view = LocationView.as_view()
        url = 'icds_locations'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.state_3.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'name': 'Test State 3',
            'user_have_access_to_parent': False,
            'map_location_name': 'Test State 3',
            'location_type_name': 'state',
            'user_have_access': True,
            'location_type': 'state'
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_request_with_location_id_and_location_restriction(self):
        if self.factory is None:
            return
        view = LocationView.as_view()
        url = 'icds_locations'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.block_3.location_id
        })
        self.user.set_location(self.domain.name, self.awc_3)
        request.user = self.user
        expected = {
            'name': 'Test Block 3',
            'user_have_access_to_parent': True,
            'map_location_name': 'Test Block 3',
            'location_type_name': 'block',
            'user_have_access': False,
            'location_type': 'block'
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc_3.location_id)
        self.assertDictEqual(expected, json.loads(response.content))

    def test_request_with_parent_id(self):
        if self.factory is None:
            return
        view = LocationView.as_view()
        url = 'icds_locations'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'parent_id': self.state_3.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'locations': [
                {
                    'name': 'Test District 3_1',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state_3.location_id,
                    'location_id': self.district_3_1.location_id
                },
                {
                    'name': 'Test District 3_2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state_3.location_id,
                    'location_id': self.district_3_2.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_request_with_parent_id_and_location_restriction(self):
        if self.factory is None:
            return
        view = LocationView.as_view()
        url = 'icds_locations'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'parent_id': self.block_3.location_id
        })
        self.user.set_location(self.domain.name, self.awc_3)
        request.user = self.user
        expected = {
            'locations': [
                {
                    'name': 'Test Supervisor 3',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': False,
                    'parent_id': self.block_3.location_id,
                    'location_id': self.supervisor_3.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc_3.location_id)
        self.assertDictEqual(expected, json.loads(response.content))


class TestLocationAncestorsView(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLocationAncestorsView, cls).setUpClass()
        cls.domain = create_domain('icds-test')
        state = LocationType.objects.create(
            domain=cls.domain.name,
            name='state',
            parent_type=None
        )
        district = LocationType.objects.create(
            domain=cls.domain.name,
            name='district',
            parent_type=state
        )
        block = LocationType.objects.create(
            domain=cls.domain.name,
            name='block',
            parent_type=district
        )
        supervisor = LocationType.objects.create(
            domain=cls.domain.name,
            name='supervisor',
            parent_type=block
        )
        awc = LocationType.objects.create(
            domain=cls.domain.name,
            name='awc',
            parent_type=supervisor
        )

        cls.state = SQLLocation.objects.create(
            name='Test State',
            domain=cls.domain.name,
            location_type=state
        )
        cls.district = SQLLocation.objects.create(
            name='Test District',
            domain=cls.domain.name,
            location_type=district,
            parent=cls.state,
        )
        cls.district_2 = SQLLocation.objects.create(
            name='Test District 2',
            domain=cls.domain.name,
            location_type=district,
            parent=cls.state,
        )
        cls.block = SQLLocation.objects.create(
            name='Test Block',
            domain=cls.domain.name,
            location_type=block,
            parent=cls.district
        )
        cls.block_2 = SQLLocation.objects.create(
            name='Test Block 2',
            domain=cls.domain.name,
            location_type=block,
            parent=cls.district_2
        )
        cls.supervisor = SQLLocation.objects.create(
            name='Test Supervisor',
            domain=cls.domain.name,
            location_type=supervisor,
            parent=cls.block
        )
        cls.supervisor_2 = SQLLocation.objects.create(
            name='Test Supervisor 2',
            domain=cls.domain.name,
            location_type=supervisor,
            parent=cls.block_2
        )
        cls.awc = SQLLocation.objects.create(
            name='Test AWC',
            domain=cls.domain.name,
            location_type=awc,
            parent=cls.supervisor
        )
        cls.awc_2 = SQLLocation.objects.create(
            name='Test AWC 2',
            domain=cls.domain.name,
            location_type=awc,
            parent=cls.supervisor_2
        )
        cls.state_2 = SQLLocation.objects.create(
            name='Test State 2',
            domain=cls.domain.name,
            location_type=state
        )
        cls.state_3 = SQLLocation.objects.create(
            name='Test State 3',
            domain=cls.domain.name,
            location_type=state
        )
        cls.factory = RequestFactory()
        cls.user = WebUser.create(cls.domain.name, 'test', 'passwordtest')
        cls.user.is_authenticated = True
        cls.user.is_superuser = True
        cls.user.is_authenticated = True
        cls.user.is_active = True

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.user.delete()
        cls.awc.delete()
        cls.supervisor.delete()
        cls.block.delete()
        cls.district.delete()
        cls.awc_2.delete()
        cls.supervisor_2.delete()
        cls.block_2.delete()
        cls.district_2.delete()
        cls.state_3.delete()
        cls.state_2.delete()
        cls.state.delete()
        super(TestLocationAncestorsView, cls).tearDownClass()

    def test_without_location_restriction_state(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.state_3.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'selected_location': {
                'name': 'Test State 3',
                'user_have_access_to_parent': False,
                'location_type_name': 'state',
                'user_have_access': True,
                'parent_id': None,
                'location_id': self.state_3.location_id
            },
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                },
                {
                    'name': 'Test State 3',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_3.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_without_location_restriction_district(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.district.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'selected_location': {
                'name': 'Test District',
                'user_have_access_to_parent': False,
                'location_type_name': 'district',
                'user_have_access': True,
                'parent_id': self.state.location_id,
                'location_id': self.district.location_id
            },
            'locations': [
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test District 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district_2.location_id
                },
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                },
                {
                    'name': 'Test State 3',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_3.location_id
                },
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_without_location_restriction_block(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.block.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'selected_location': {
                'name': 'Test Block',
                'user_have_access_to_parent': False,
                'location_type_name': 'block',
                'user_have_access': True,
                'parent_id': self.district.location_id,
                'location_id': self.block.location_id
            },
            'locations': [
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'block',
                    'user_have_access': True,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test District 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district_2.location_id
                },
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                },
                {
                    'name': 'Test State 3',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_3.location_id
                },
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_without_location_restriction_supervisor(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.supervisor.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'selected_location': {
                'name': 'Test Supervisor',
                'user_have_access_to_parent': False,
                'location_type_name': 'supervisor',
                'user_have_access': True,
                'parent_id': self.block.location_id,
                'location_id': self.supervisor.location_id
            },
            'locations': [
                {
                    'name': 'Test District 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district_2.location_id
                },
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                },
                {
                    'name': 'Test State 3',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_3.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'supervisor',
                    'user_have_access': True,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                },
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': True,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_without_location_restriction_awc(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.awc.location_id
        })
        request.user = self.user
        response = view(request, domain='icds-test')
        expected = {
            'selected_location': {
                'name': 'Test AWC',
                'user_have_access_to_parent': False,
                'location_type_name': 'awc',
                'user_have_access': True,
                'parent_id': self.supervisor.location_id,
                'location_id': self.awc.location_id
            },
            'locations': [
                {
                    'name': 'Test AWC',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'awc',
                    'user_have_access': True,
                    'parent_id': self.supervisor.location_id,
                    'location_id': self.awc.location_id
                },
                {
                    'name': 'Test District 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district_2.location_id
                },
                {
                    'name': 'Test State 2',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_2.location_id
                },
                {
                    'name': 'Test State 3',
                    'user_have_access_to_parent': False,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state_3.location_id
                },
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': True,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': True,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': True,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': True,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                }
            ]
        }
        self.assertDictEqual(expected, json.loads(response.content))

    def test_with_location_restriction_state(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.state.location_id
        })
        self.user.set_location(self.domain.name, self.awc)
        request.user = self.user
        expected = {
            'selected_location': {
                'name': 'Test State',
                'user_have_access_to_parent': True,
                'location_type_name': 'state',
                'user_have_access': False,
                'parent_id': None,
                'location_id': self.state.location_id
            },
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': False,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': False,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': False,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': False,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                },
                {
                    'name': 'Test AWC',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'awc',
                    'user_have_access': True,
                    'parent_id': self.supervisor.location_id,
                    'location_id': self.awc.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc.location_id)
        self.assertDictEqual(expected, json.loads(response.content))

    def test_with_location_restriction_district(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.district.location_id
        })
        self.user.set_location(self.domain.name, self.awc)
        request.user = self.user
        expected = {
            'selected_location': {
                'name': 'Test District',
                'user_have_access_to_parent': True,
                'location_type_name': 'district',
                'user_have_access': False,
                'parent_id': self.state.location_id,
                'location_id': self.district.location_id
            },
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': False,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': False,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': False,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': False,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                },
                {
                    'name': 'Test AWC',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'awc',
                    'user_have_access': True,
                    'parent_id': self.supervisor.location_id,
                    'location_id': self.awc.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc.location_id)
        self.assertDictEqual(expected, json.loads(response.content))

    def test_with_location_restriction_block(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.block.location_id
        })
        self.user.set_location(self.domain.name, self.awc)
        request.user = self.user
        expected = {
            'selected_location': {
                'name': 'Test Block',
                'user_have_access_to_parent': True,
                'location_type_name': 'block',
                'user_have_access': False,
                'parent_id': self.district.location_id,
                'location_id': self.block.location_id
            },
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': False,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': False,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': False,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': False,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                },
                {
                    'name': 'Test AWC',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'awc',
                    'user_have_access': True,
                    'parent_id': self.supervisor.location_id,
                    'location_id': self.awc.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc.location_id)
        self.assertDictEqual(expected, json.loads(response.content))

    def test_with_location_restriction_supervisor(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.supervisor.location_id
        })
        self.user.set_location(self.domain.name, self.awc)
        request.user = self.user
        expected = {
            'selected_location': {
                'name': 'Test Supervisor',
                'user_have_access_to_parent': True,
                'location_type_name': 'supervisor',
                'user_have_access': False,
                'parent_id': self.block.location_id,
                'location_id': self.supervisor.location_id
            },
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': False,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': False,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': False,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': False,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                },
                {
                    'name': 'Test AWC',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'awc',
                    'user_have_access': True,
                    'parent_id': self.supervisor.location_id,
                    'location_id': self.awc.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc.location_id)
        self.assertDictEqual(expected, json.loads(response.content))

    def test_with_location_restriction_awc(self):
        if self.factory is None:
            return
        view = LocationAncestorsView.as_view()
        url = 'icds_locations_ancestors'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse, data={
            'location_id': self.awc.location_id
        })
        self.user.set_location(self.domain.name, self.awc)
        request.user = self.user
        expected = {
            'selected_location': {
                'name': 'Test AWC',
                'user_have_access_to_parent': True,
                'location_type_name': 'awc',
                'user_have_access': True,
                'parent_id': self.supervisor.location_id,
                'location_id': self.awc.location_id
            },
            'locations': [
                {
                    'name': 'Test State',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'state',
                    'user_have_access': False,
                    'parent_id': None,
                    'location_id': self.state.location_id
                },
                {
                    'name': 'Test District',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'district',
                    'user_have_access': False,
                    'parent_id': self.state.location_id,
                    'location_id': self.district.location_id
                },
                {
                    'name': 'Test Block',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'block',
                    'user_have_access': False,
                    'parent_id': self.district.location_id,
                    'location_id': self.block.location_id
                },
                {
                    'name': 'Test Supervisor',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'supervisor',
                    'user_have_access': False,
                    'parent_id': self.block.location_id,
                    'location_id': self.supervisor.location_id
                },
                {
                    'name': 'Test AWC',
                    'user_have_access_to_parent': True,
                    'location_type_name': 'awc',
                    'user_have_access': True,
                    'parent_id': self.supervisor.location_id,
                    'location_id': self.awc.location_id
                }
            ]
        }
        with mock.patch('corehq.apps.users.models.WebUser.has_permission', return_value=False):
            response = view(request, domain='icds-test')
        self.user.unset_location_by_id(self.domain.name, self.awc.location_id)
        self.assertDictEqual(expected, json.loads(response.content))
