from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.commtrack.tests.util import make_location
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.models import LocationType
from corehq.apps.reports.standard.deployments import ApplicationStatusReport
from corehq.apps.users.models import CommCareUser, ReportingMetadata, WebUser
from corehq.util.test_utils import disable_quickcache

LOCATION_TYPE_COUNTRY = 'country'
LOCATION_TYPE_STATE = 'state'
LOCATION_TYPE_CITY = 'city'


@es_test(requires=[user_adapter], setup_class=True)
@disable_quickcache
class TestApplicationStatusReport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain_name_a = 'app-status-test-1'
        cls.domain_a = create_domain(cls.domain_name_a)
        cls.addClassCleanup(cls.domain_a.delete)
        cls.app_a = AppFactory(domain=cls.domain_name_a, name="App A").app
        cls.app_a.save()
        cls.addClassCleanup(cls.app_a.delete)

        cls.domain_name_b = 'app-status-test-2'
        cls.domain_b = create_domain(cls.domain_name_b)
        cls.addClassCleanup(cls.domain_b.delete)
        cls.app_b = AppFactory(domain=cls.domain_name_b, name="App B").app
        cls.app_b.save()
        cls.addClassCleanup(cls.app_b.delete)

        [domain_a_country, domain_a_state, domain_a_city] = cls._setup_locations(domain=cls.domain_name_a)

        cls.request_factory = RequestFactory()

        cls.admin_user = WebUser.create(cls.domain_name_a, 'admin@example.com', 'password', None, None)
        cls.admin_user.is_superuser = True
        cls.admin_user.save()
        cls.addClassCleanup(cls.admin_user.delete, cls.domain_name_a, deleted_by=None)

        user1 = CommCareUser.create(cls.domain_name_a, 'mobile_worker1', '***', None, None)
        # app_b being in different domain will cause user1 to be skipped from app status report
        # via AppInDifferentDomainException when viewing for all apps
        user1.reporting_metadata = cls._reporting_metadata_multiple_apps(cls.app_a._id, cls.app_b._id)
        user2 = CommCareUser.create(cls.domain_name_a, 'mobile_worker2', '***', None, None,
                                    location=domain_a_city)
        user2.reporting_metadata = cls._reporting_metadata_single_app(cls.app_a._id)

        user3 = CommCareUser.create(cls.domain_name_a, 'mobile_worker3', '***', None, None,
                                    location=domain_a_state)
        user3.reporting_metadata = cls._reporting_metadata_single_app(cls.app_a._id, app_build_version=10)
        user4 = CommCareUser.create(cls.domain_name_a, 'mobile_worker4', '***', None, None,
                                    location=domain_a_country)
        user4.reporting_metadata = cls._reporting_metadata_single_app(cls.app_a._id, app_build_version=15)

        for user in [user1, user2, user3, user4]:
            user.save()
            user_adapter.index(user, refresh=True)
            cls.addClassCleanup(user.delete, cls.domain_name_a, deleted_by=None)

    @classmethod
    def _setup_locations(cls, domain):
        loc_type_country = LocationType.objects.create(domain=domain, name='Country')
        loc_type_state = LocationType.objects.create(domain=domain, name='State', code=LOCATION_TYPE_STATE,
                                                     parent_type=loc_type_country)
        loc_type_city = LocationType.objects.create(domain=domain, name='City', code=LOCATION_TYPE_CITY,
                                                    parent_type=loc_type_state)
        loc_country = make_location(site_code='india', name='India', domain=domain,
                                    location_type=loc_type_country.name)
        loc_country.save()
        loc_state = make_location(site_code='mh', name='Maharashtra', domain=domain,
                                  location_type=loc_type_state.name, parent=loc_country)
        loc_state.save()
        loc_city = make_location(site_code='bmb', name='Bombay', domain=domain,
                                 location_type=loc_type_city.name, parent=loc_state)
        loc_city.save()
        return [loc_country, loc_state, loc_city]

    @staticmethod
    def _reporting_metadata_multiple_apps(app_id_1, app_id_2):
        now = datetime.now()
        return ReportingMetadata.wrap({
            'last_submissions': [{
                'app_id': app_id_1,
                'submission_date': json_format_datetime(now - timedelta(days=1)),
                'commcare_version': '2.53.0',
            }, {
                'app_id': app_id_2,
                'submission_date': json_format_datetime(now - timedelta(days=2)),
                'commcare_version': '2.53.0',
            }],
            'last_syncs': [{
                'app_id': app_id_1,
                'sync_date': json_format_datetime(now - timedelta(days=2)),
            }],
            'last_builds': [{
                'app_id': app_id_2,
                'build_version': 10,
                'build_profile_id': 'profile1',
            }],
            'last_build_for_user': {
                'app_id': app_id_2,
                'build_version': 10,
                'build_profile_id': 'profile1',
            }
        })

    @staticmethod
    def _reporting_metadata_single_app(app_id_1, app_build_version=8):
        now = datetime.now()
        return ReportingMetadata.wrap({
            'last_submissions': [{
                'app_id': app_id_1,
                'submission_date': json_format_datetime(now - timedelta(days=5)),
                'commcare_version': '2.50.0',
            }],
            'last_syncs': [{
                'app_id': app_id_1,
                'sync_date': json_format_datetime(now - timedelta(days=6)),
            }],
            'last_builds': [{
                'app_id': app_id_1,
                'build_version': app_build_version,
            }],
            'last_build_for_user': {
                'app_id': app_id_1,
                'build_version': app_build_version,
            }
        })

    def setUp(self):
        super().setUp()
        self.request = self.request_factory.get('/a/{}/reports/app_status/'.format(self.domain_name_a))
        self.request.couch_user = self.admin_user
        self.request.domain = self.domain_name_a
        self.request.can_access_all_locations = True

    def test_report_with_reporting_data_of_multiple_domains(self):
        """
        When requesting data for domain_a, we should only see User 2.
        """
        report = ApplicationStatusReport(self.request, domain=self.domain_name_a)
        rows = report.rows
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][0], 'mobile_worker2')

    def test_get_formatted_assigned_location_names(self):
        user_loc_dict = {
            '1': 'Location 1',
            '2': 'Location 2 {Special Character In Primary}',
            '3': 'Location 3 {Special Character}'
        }
        formatted_assigned_location_names = ApplicationStatusReport._get_formatted_assigned_location_names(
            '2',
            ['1', '2', '3'],
            user_loc_dict
        )
        self.assertEqual(
            formatted_assigned_location_names,
            '<div>'
            '<span class="locations-list">'
            '<strong>Location 2 {Special Character In Primary}</strong>, '
            'Location 1, '
            'Location 3 {Special Character}'
            '</span>'
            '</div>'
        )

    def test_get_formatted_assigned_location_names_with_overflow(self):
        user_loc_dict = {
            '1': 'Location 1',
            '2': 'Location 2 {Special Character In Primary}',
            '3': 'Location 3 {Special Character}',
            '4': 'Location 4',
            '5': 'Location 5'
        }
        formatted_assigned_location_names = ApplicationStatusReport._get_formatted_assigned_location_names(
            '2',
            ['1', '2', '3', '4', '5'],
            user_loc_dict
        )
        self.assertEqual(
            formatted_assigned_location_names,
            '<div>'
            '<span class="locations-list">'
            '<strong>Location 2 {Special Character In Primary}</strong>, '
            'Location 1, '
            'Location 3 {Special Character}, '
            'Location 4'
            '</span>'
            '<span class="all-locations-list" style="display:none">'
            '<strong>Location 2 {Special Character In Primary}</strong>, '
            'Location 1, '
            'Location 3 {Special Character}, '
            'Location 4, '
            'Location 5'
            '</span>'
            '<a href="#" class="toggle-all-locations">'
            '<span class="loc-view-control">...See more</span>'
            '<span class="loc-view-control" style="display:none">...Collapse</span>'
            '</a>'
            '</div>'
        )

    def test_export_table(self):
        report = ApplicationStatusReport(self.request, domain=self.domain_name_a)
        self.assertListEqual(
            report.export_table,
            [
                [
                    'User Last Activity Report',
                    [
                        [
                            'Username', 'Assigned Location(s)', 'Last Submission', 'Last Sync', 'Application',
                            'Application Version', 'CommCare Version', "Number of unsent forms in user's phone"
                        ],
                        [
                            'mobile_worker2', 'Bombay', '---', '---', 'App A', 8, '---', '---'
                        ],
                        [
                            'mobile_worker3', 'Maharashtra', '---', '---', 'App A', 10, '---', '---'
                        ],
                        [
                            'mobile_worker4', 'India', '---', '---', 'App A', 15, '---', '---'
                        ]
                    ]
                ]
            ]
        )

    @patch('corehq.apps.reports.standard.deployments.ApplicationStatusReport._include_primary_locations_hierarchy')
    def test_export_table_with_ancestor_locations_data(self, mock_include_primary_locations_hierarchy):
        mock_include_primary_locations_hierarchy.return_value = True

        report = ApplicationStatusReport(self.request, domain=self.domain_name_a)
        export_table = report.export_table
        self.assertListEqual(
            export_table,
            [
                [
                    'User Last Activity Report',
                    [
                        [
                            'Username', 'Assigned Location(s)', 'Last Submission', 'Last Sync', 'Application',
                            'Application Version', 'CommCare Version', "Number of unsent forms in user's phone",
                            'Country Name', 'State Name', 'City Name'
                        ],
                        [
                            'mobile_worker2', 'Bombay', '---', '---', 'App A', 8, '---', '---', 'India',
                            'Maharashtra', 'Bombay'
                        ],
                        [
                            'mobile_worker3', 'Maharashtra', '---', '---', 'App A', 10, '---', '---', 'India',
                            'Maharashtra', '---'
                        ],
                        [
                            'mobile_worker4', 'India', '---', '---', 'App A', 15, '---', '---', 'India',
                            '---', '---'
                        ]
                    ]
                ]
            ]
        )
