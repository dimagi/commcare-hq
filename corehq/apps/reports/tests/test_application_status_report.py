from datetime import datetime, timedelta

from django.test import RequestFactory, TestCase

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.reports.standard.deployments import ApplicationStatusReport
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import disable_quickcache


class DataForTestApplicationStatusReport:
    """Test data for ApplicationStatusReport tests"""

    @staticmethod
    def get_user_data(domain_1, app_id_1, app_id_2):
        """
        Returns two users with reporting metadata for two apps in different domains.
        User 1 has data for both apps and last build is for app_id_2.
        User 2 has data for only one app.
        """

        now = datetime.now()
        return [
            {
                'domain': domain_1,
                'username': 'mobile_worker1',
                'password': 'secret',
                'email': 'mobile_worker1@example.com',
                'uuid': 'mobile_worker1',
                'is_active': True,
                'doc_type': 'CommCareUser',
                'reporting_metadata': {
                    'last_submissions': [
                        {
                            'app_id': app_id_1,
                            'submission_date': json_format_datetime(now - timedelta(days=1)),
                            'commcare_version': '2.53.0'
                        },
                        {
                            'app_id': app_id_2,
                            'submission_date': json_format_datetime(now - timedelta(days=2)),
                            'commcare_version': '2.53.0'
                        }
                    ],
                    'last_syncs': [
                        {
                            'app_id': app_id_1,
                            'sync_date': json_format_datetime(now - timedelta(days=2))
                        }
                    ],
                    'last_builds': [
                        {
                            'app_id': app_id_2,
                            'build_version': 10,
                            'build_profile_id': 'profile1'
                        }
                    ],
                    'last_build_for_user': {
                        'app_id': app_id_2,
                        'build_version': 10,
                        'build_profile_id': 'profile1'
                    }

                },
                'devices': [
                    {
                        'device_id': 'device1',
                        'last_used': json_format_datetime(now),
                        'app_meta': [
                            {
                                'app_id': app_id_1,
                                'num_unsent_forms': 5
                            }
                        ]
                    }
                ]
            },
            {
                'domain': domain_1,
                'username': 'mobile_worker2',
                'password': 'secret',
                'email': 'mobile_worker2@example.com',
                'uuid': 'mobile_worker2',
                'is_active': True,
                'doc_type': 'CommCareUser',
                'reporting_metadata': {
                    'last_submissions': [
                        {
                            'app_id': app_id_1,
                            'submission_date': json_format_datetime(now - timedelta(days=5)),
                            'commcare_version': '2.50.0'
                        }
                    ],
                    'last_syncs': [
                        {
                            'app_id': app_id_1,
                            'sync_date': json_format_datetime(now - timedelta(days=6))
                        }
                    ],
                    'last_builds': [
                        {
                            'app_id': app_id_1,
                            'build_version': 8
                        }
                    ],
                    'last_build_for_user': {
                        'app_id': app_id_1,
                        'build_version': 8
                    }
                },
                'devices': [
                    {
                        'device_id': 'device2',
                        'last_used': json_format_datetime(now),
                        'app_meta': [
                            {
                                'app_id': app_id_1,
                                'num_unsent_forms': 0
                            }
                        ]
                    }
                ]
            },
        ]


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

        cls.request_factory = RequestFactory()

        cls.admin_user = WebUser.create(cls.domain_name_a, 'admin@example.com', 'password', None, None)
        cls.admin_user.is_superuser = True
        cls.admin_user.save()
        cls.addClassCleanup(cls.admin_user.delete, cls.domain_name_a, deleted_by=None)

        cls.user_data = DataForTestApplicationStatusReport.get_user_data(
            cls.domain_name_a, cls.app_a._id, cls.app_b._id
        )
        cls.users = []

        for user_data in cls.user_data:
            user = CommCareUser(user_data)
            user.save()
            cls.addClassCleanup(user.delete, cls.domain_name_a, deleted_by=None)
            cls.users.append(user)

        for user in cls.users:
            user_adapter.index(user, refresh=True)

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
        self.assertEqual(len(rows), 1)
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
