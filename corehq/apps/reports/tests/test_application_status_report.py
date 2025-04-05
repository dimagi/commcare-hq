from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory

from corehq.apps.app_manager.models import BuildProfile
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reports.standard.deployments import ApplicationStatusReport
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import disable_quickcache, flag_enabled
from corehq.apps.users.dbaccessors import delete_all_users
from dimagi.utils.parsing import json_format_datetime


class MockApplication(object):
    def __init__(self, _id, domain, name, build_profiles={}):
        self.domain = domain
        self.name = name
        self._id = _id
        self.build_profiles = build_profiles

    @property
    def get_id(self):
        return self._id


class TestApplicationStatusReportData(TestCase):
    """Test data for ApplicationStatusReport tests"""

    @staticmethod
    def get_user_data(domain):
        def format_datetime(dt):
            return json_format_datetime(dt)

        now = datetime.now()
        return [
            {
                'domain': domain,
                'username': 'mobile_worker1',
                'password': 'secret',
                'email': 'mobile1@example.com',
                'uuid': 'mobile1',
                'is_active': True,
                'doc_type': 'CommCareUser',
                'reporting_metadata': {
                    'last_submissions': [
                        {
                            'app_id': 'app1',
                            'submission_date': format_datetime(now - timedelta(days=1)),
                            'commcare_version': '2.53.0'
                        }
                    ],
                    'last_syncs': [
                        {
                            'app_id': 'app1',
                            'sync_date': format_datetime(now - timedelta(days=2))
                        }
                    ],
                    'last_builds': [
                        {
                            'app_id': 'app1',
                            'build_version': 10,
                            'build_profile_id': 'profile1'
                        }
                    ]
                },
                'devices': [
                    {
                        'device_id': 'device1',
                        'last_used': format_datetime(now),
                        'app_meta': [
                            {
                                'app_id': 'app1',
                                'num_unsent_forms': 5
                            }
                        ]
                    }
                ]
            },
            {
                'domain': domain,
                'username': 'mobile_worker2',
                'password': 'secret',
                'email': 'mobile2@example.com',
                'uuid': 'mobile2',
                'is_active': True,
                'doc_type': 'CommCareUser',
                'reporting_metadata': {
                    'last_submissions': [
                        {
                            'app_id': 'app2',
                            'submission_date': format_datetime(now - timedelta(days=5)),
                            'commcare_version': '2.50.0'
                        }
                    ],
                    'last_syncs': [
                        {
                            'app_id': 'app2',
                            'sync_date': format_datetime(now - timedelta(days=6))
                        }
                    ],
                    'last_builds': [
                        {
                            'app_id': 'app2',
                            'build_version': 8
                        }
                    ]
                },
                'devices': [
                    {
                        'device_id': 'device2',
                        'last_used': format_datetime(now),
                        'app_meta': [
                            {
                                'app_id': 'app2',
                                'num_unsent_forms': 0
                            }
                        ]
                    }
                ]
            },
            {
                'domain': domain,
                'username': 'mobile_worker3',
                'password': 'secret',
                'email': 'mobile3@example.com',
                'uuid': 'mobile3',
                'is_active': True,
                'doc_type': 'CommCareUser',
                'location_id': 'location1',
                'reporting_metadata': {
                    'last_submission_for_user': {
                        'submission_date': format_datetime(now - timedelta(days=3)),
                        'commcare_version': '2.48.0'
                    },
                    'last_submissions': [
                        {
                            'app_id': 'app1',
                            'submission_date': format_datetime(now - timedelta(days=2)),
                            'commcare_version': '2.53.0'
                        }
                    ],
                    'last_syncs': [
                        {
                            'app_id': 'app1',
                            'sync_date': format_datetime(now - timedelta(days=2))
                        }
                    ],
                    'last_sync_for_user': {
                        'sync_date': format_datetime(now - timedelta(days=12))
                    },
                    'last_build_for_user': {
                        'app_id': 'app1',
                        'build_version': 7
                    }
                },
                'devices': [
                    {
                        'device_id': 'device3',
                        'last_used': format_datetime(now),
                        'app_meta': [
                            {
                                'app_id': 'app1',
                                'num_unsent_forms': 2
                            }
                        ]
                    }
                ]
            }
        ]


@es_test(requires=[user_adapter], setup_class=True)
@disable_quickcache
class TestApplicationStatusReport(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Clean up any existing domains and users
        delete_all_users()
        for domain in Domain.get_all():
            domain.delete()

        cls.domain_name = 'app-status-test'
        cls.domain = create_domain(cls.domain_name)
        cls.addClassCleanup(cls.domain.delete)
        cls.request_factory = RequestFactory()

        # Create test users
        cls.admin_user = WebUser.create(cls.domain_name, 'admin@example.com', 'password', None, None)
        cls.admin_user.is_superuser = True
        cls.admin_user.save()
        cls.addClassCleanup(cls.admin_user.delete, cls.domain_name, deleted_by=None)
        # Create location data first
        cls.location_type = LocationType.objects.create(
            domain=cls.domain_name,
            name='facility',
        )
        cls.location = SQLLocation.objects.create(
            domain=cls.domain_name,
            name='Test Facility',
            location_id='location1',
            location_type=cls.location_type
        )
        # Create test data
        cls.user_data = TestApplicationStatusReportData.get_user_data(cls.domain_name)
        cls.users = []

        # Now create users with proper metadata
        for user_data in cls.user_data:
            # Create the user properly
            user = CommCareUser(user_data)
            user.save()
            cls.addClassCleanup(user.delete, cls.domain_name, deleted_by=None)
            cls.users.append(user)

        # Index users to ES
        for user in cls.users:
            user_adapter.index(user, refresh=True)

        # Mock applications
        cls.app1 = MockApplication(
            _id='app1',
            domain=cls.domain_name,
            name='Test App 1',
            build_profiles={
                'profile1': BuildProfile(
                    name='Profile 1',
                    langs=['en'],
                    practice_mobile_worker_id='practice_mobile_worker_id'
                )
            }
        )

        cls.app2 = MockApplication(
            _id='app2',
            domain=cls.domain_name,
            name='Test App 2',
            build_profiles={}
        )

    def setUp(self):
        super().setUp()
        self.request = self.request_factory.get('/a/{}/reports/app_status/'.format(self.domain_name))
        self.request.couch_user = self.admin_user
        self.request.domain = self.domain_name
        self.request.can_access_all_locations = True

    @patch('corehq.apps.reports.standard.deployments.get_app')
    def test_report_rows_without_app_filter(self, mock_get_app):
        """Test that the report shows all users when no app filter is applied"""
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        report = ApplicationStatusReport(self.request, domain=self.domain_name)
        rows = report.rows

        # Should have 3 rows (one for each user)
        self.assertEqual(len(rows), 3)

        # Check that usernames are in the first column
        usernames = [row[0]for row in rows]
        self.assertIn('mobile_worker1', usernames)
        self.assertIn('mobile_worker2', usernames)
        self.assertIn('mobile_worker3', usernames)

    @patch('corehq.apps.reports.standard.deployments.get_app')
    def test_report_with_app_filter(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        # Set app filter to app1
        request = self.request_factory.get(
            '/a/{}/reports/app_status/?app_id="app1"'.format(self.domain_name)
        )
        request.couch_user = self.admin_user
        request.domain = self.domain_name
        request.can_access_all_locations = True

        # Mock the selected_app_id property
        with patch('corehq.apps.reports.standard.deployments.ApplicationStatusReport.selected_app_id',
                  new_callable=MagicMock(return_value='app1')):
            report = ApplicationStatusReport(request, domain=self.domain_name)
            rows = report.rows

            # Should only show users with app1 (mobile_worker1 and mobile_worker3)
            self.assertEqual(len(rows), 2)

            # Check that usernames are in the first column

            usernames = [row[0] for row in rows]
            self.assertIn('mobile_worker1', usernames)
            self.assertIn('mobile_worker3', usernames)
            self.assertNotIn('mobile_worker2', usernames)

    @patch('corehq.apps.reports.standard.deployments.get_app')
    @flag_enabled('SHOW_BUILD_PROFILE_IN_APPLICATION_STATUS')
    def test_build_profile_column(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        report = ApplicationStatusReport(self.request, domain=self.domain_name)

        # Check that the headers include the build profile column
        headers = report.headers
        header_texts = [h.html for h in headers.header]
        self.assertIn('Build Profile', header_texts)

        # Check that the rows include the build profile
        rows = report.rows
        for row in rows:
            if 'mobile_worker1' in row[0]:
                # mobile_worker1 has a build profile
                self.assertEqual(len(row), 9)  # 8 standard columns + 1 for build profile
                break

    @patch('corehq.apps.reports.standard.deployments.get_app')
    def test_export_table(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        report = ApplicationStatusReport(self.request, domain=self.domain_name)
        export_table = report.export_table

        # Check that we have a table with headers and data
        self.assertEqual(len(export_table), 1)
        table = export_table[0][1]

        # First row should be headers
        headers = table[0]
        self.assertIn('Username', headers)
        self.assertIn('Assigned Location(s)', headers)
        self.assertIn('Last Submission', headers)

        # Should have data rows for each user
        self.assertEqual(len(table) - 1, 3)  # 3 users + 1 header row

    @patch('corehq.apps.reports.standard.deployments.get_app')
    def test_sorting_functionality(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        # Test default sorting (by last submission date, descending)
        report = ApplicationStatusReport(self.request, domain=self.domain_name)
        sorting_block = report.get_sorting_block()

        # Should have one sorting block
        self.assertEqual(len(sorting_block), 1)

        # Default sort should be by last submission date
        self.assertIn('reporting_metadata.last_submission_for_user.submission_date',
                     str(sorting_block[0]))

        # Test with selected app_id
        with patch('corehq.apps.reports.standard.deployments.ApplicationStatusReport.selected_app_id',
                  new_callable=MagicMock(return_value='app1')):
            report = ApplicationStatusReport(self.request, domain=self.domain_name)
            sorting_block = report.get_sorting_block()
            # Should sort by last submissions with app filter
            self.assertIn('reporting_metadata.last_submissions.submission_date',
                         str(sorting_block[0]))

            # Should include nested filter for the app_id
            self.assertIn('app_id', str(sorting_block[0]))
            self.assertIn('app1', str(sorting_block[0]))

    @patch('corehq.apps.reports.standard.deployments.get_app')
    @flag_enabled('LOCATION_COLUMNS_APP_STATUS_REPORT')
    def test_include_location_data(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        # Set rendered_as to 'export' to trigger location data inclusion
        report = ApplicationStatusReport(self.request, domain=self.domain_name)
        report.rendered_as = 'export'

        # Check that include_location_data returns True
        self.assertTrue(report.include_location_data())

        # Check that export_table includes location columns
        export_table = report.export_table
        table = export_table[0][1]
        headers = table[0]

        # Should include a column for the location type
        self.assertIn('Facility Name', headers)

    @patch('corehq.apps.reports.standard.deployments.get_app')
    def test_get_data_for_app(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        report = ApplicationStatusReport(self.request, domain=self.domain_name)

        # Test with matching app_id
        options = [
            {'app_id': 'app1', 'value': 'test1'},
            {'app_id': 'app2', 'value': 'test2'}
        ]
        result = report.get_data_for_app(options, 'app1')
        self.assertEqual(result, {'app_id': 'app1', 'value': 'test1'})

        # Test with non-matching app_id
        result = report.get_data_for_app(options, 'app3')
        self.assertEqual(result, {})

    @patch('corehq.apps.reports.standard.deployments.get_app')
    def test_process_rows(self, mock_get_app):
        mock_get_app.side_effect = lambda domain, app_id: self.app1 if app_id == 'app1' else self.app2

        report = ApplicationStatusReport(self.request, domain=self.domain_name)

        # Create test user data
        submission_date = json_format_datetime(datetime.now())
        sync_date = json_format_datetime(datetime.now())
        last_used = json_format_datetime(datetime.now())
        test_user = {
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User',
            'doc_type': 'CommCareUser',
            'reporting_metadata': {
                'last_submission_for_user': {
                    'submission_date': submission_date,
                    'commcare_version': '2.53.0'
                },
                'last_sync_for_user': {
                    'sync_date': sync_date
                },
                'last_build_for_user': {
                    'app_id': 'app1',
                    'build_version': 10
                }
            },
            'devices': [
                {
                    'last_used': last_used,
                    'app_meta': [
                        {
                            'app_id': 'app1',
                            'num_unsent_forms': 3
                        }
                    ]
                }
            ]
        }

        # Process the user data into rows
        rows = report.process_rows([test_user])

        # Should have one row
        self.assertEqual(len(rows), 1)

        # Row should have 8 columns (username, location, last submission, last sync,
        # app name, app version, commcare version, unsent forms)
        self.assertEqual(len(rows[0]), 8)

        # Username should be in the first column
        self.assertIn('test_user', rows[0][0])

        # App name should be in the fifth column
        self.assertEqual(rows[0][4], 'Test App 1')

        # Test with export formatting
        export_rows = report.process_rows([test_user], fmt_for_export=True)
        self.assertEqual(len(export_rows), 1)

        self.assertIn(" ".join(submission_date[:-1].split('T')), export_rows[0][2]['html'])
