
from datetime import date

from custom.icds_reports.models.aggregate import DashboardUserActivityReport
from django.test.testcases import TestCase
from mock import patch

from custom.icds_reports.tasks import update_dashboard_activity_report


@patch('corehq.apps.es.es_query.ESQuerySet.hits', [
    {'username': '12.test@icds-cas.commcarehq.org', 'location_id': 'st1'},
    {'username': '23.test@icds-cas.commcarehq.org', 'location_id': 'd1'},
])
class DashboardActivityReport(TestCase):
    always_include_columns = {'username', 'state_id', 'district_id', 'block_id',
                              'user_level', 'location_launched', 'last_activity', 'date'}

    def test_dashboard_activity_2017_05_28(self):
        update_dashboard_activity_report(date(2017, 5, 28))
        actual_data = DashboardUserActivityReport.objects.filter(date='2017-05-28').\
            values(*self.always_include_columns).order_by('username')

        self.assertEqual(list(actual_data), [
            {
                'date': date(2017, 5, 28),
                'last_activity': None,
                'location_launched': True,
                'district_id': 'All',
                'user_level': 1,
                'state_id': 'st1',
                'username': '12.test@icds-cas.commcarehq.org',
                'block_id': 'All'
            },
            {
                'date': date(2017, 5, 28),
                'last_activity': None,
                'location_launched': True,
                'district_id': 'd1',
                'user_level': 2,
                'state_id': 'st1',
                'username': '23.test@icds-cas.commcarehq.org',
                'block_id': 'All'
            }
        ])
