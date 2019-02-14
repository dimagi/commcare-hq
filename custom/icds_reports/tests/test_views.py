from __future__ import absolute_import

from __future__ import unicode_literals
from corehq import toggles
from django.test.testcases import TestCase
from django.test.client import RequestFactory
from django.core.urlresolvers import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.toggles import NAMESPACE_DOMAIN
from custom.icds_reports.views import DashboardView


class TestICDSViews(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestICDSViews, cls).setUpClass()
        cls.domain = create_domain('icds-test')
        toggles.DASHBOARD_ICDS_REPORT.set(cls.domain.name, True, NAMESPACE_DOMAIN)
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

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
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
        super(TestICDSViews, cls).tearDownClass()

    def test_dashboard_view_for_webuser(self):
        user = WebUser.create(self.domain.name, 'test', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True

        if self.factory is None:
            return
        view = DashboardView.as_view()
        url = 'icds_dashboard'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse)
        request.user = user
        request.domain = self.domain.name
        response = view(request, domain=self.domain.name)
        self.assertEqual('icds-test', response.context_data['domain'])
        self.assertEqual([], response.context_data['all_user_location_id'])
        self.assertTrue(response.context_data['have_access_to_all_locations'])
        self.assertFalse(response.context_data['have_access_to_features'])
        self.assertTrue(response.context_data['is_web_user'])
        hierarchy = [
            (u'state', [None]),
            (u'district', [u'state']),
            (u'block', [u'district']),
            (u'supervisor', [u'block']),
            (u'awc', [u'supervisor']),
        ]
        self.assertListEqual(hierarchy, response.context_data['location_hierarchy'])
        self.assertFalse(response.context_data['state_level_access'])
        self.assertIsNone(response.context_data['user_location_id'])
        user.delete()

    def test_dashboard_view_for_commcareuser(self):
        user = CommCareUser.create(self.domain.name, 'icds_dashboard_user', 'passwordtest')
        user.is_authenticated = True
        user.is_superuser = True
        user.is_authenticated = True
        user.is_active = True

        if self.factory is None:
            return
        view = DashboardView.as_view()
        url = 'icds_dashboard'
        working_reverse = reverse(url, kwargs={'domain': self.domain.name})
        request = self.factory.get(working_reverse)
        request.user = user
        request.domain = self.domain.name
        response = view(request, domain=self.domain.name)
        self.assertEqual('icds-test', response.context_data['domain'])
        self.assertEqual([], response.context_data['all_user_location_id'])
        self.assertTrue(response.context_data['have_access_to_all_locations'])
        self.assertFalse(response.context_data['have_access_to_features'])
        hierarchy = [
            (u'state', [None]),
            (u'district', [u'state']),
            (u'block', [u'district']),
            (u'supervisor', [u'block']),
            (u'awc', [u'supervisor']),
        ]
        self.assertListEqual(hierarchy, response.context_data['location_hierarchy'])
        self.assertFalse(response.context_data['state_level_access'])
        self.assertIsNone(response.context_data['user_location_id'])
        user.delete()
