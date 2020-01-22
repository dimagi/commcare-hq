from datetime import date

from custom.icds_reports.models.aggregate import DashboardUserActivityReport
from django.test.testcases import TestCase
from mock import patch

from custom.icds_reports.tasks import update_dashboard_activity_report


@patch('custom.icds_reports.utils.aggregation_helpers.distributed.agg_dashboard_activity.DashboardActivityReportAggregate.dashboard_users',  [
    {'username': '12.test@icds-cas.commcarehq.org', 'location_id': 'st1', 'is_active': True},
    {'username': '23.test@icds-cas.commcarehq.org', 'location_id': 'd1', 'is_active': True},
    {'username': '23.test@icds-cas.commcarehq.org', 'location_id': 'd1', 'is_active': False},
])
class DashboardActivityReport(TestCase):
    always_include_columns = {'username', 'state_id', 'district_id', 'block_id',
                              'user_level', 'location_launched', 'last_activity', 'date'}

    def test_dashboard_activity_2017_05_28(self):
        update_dashboard_activity_report(date(2017, 5, 28))
        actual_data = DashboardUserActivityReport.objects.filter(date='2017-05-28').\
            values(*self.always_include_columns).order_by('username')
        self.assertEqual(list(actual_data),
                         [{'block_id': 'All', 'username': '12.test@icds-cas.commcarehq.org',
                           'location_launched': True, 'date': date(2017, 5, 28), 'state_id': 'st1',
                           'district_id': 'All', 'user_level': 1, 'last_activity': None},
                          {'block_id': 'All', 'username': '23.test@icds-cas.commcarehq.org',
                           'location_launched': True, 'date': date(2017, 5, 28), 'state_id': 'st1',
                           'district_id': 'd1', 'user_level': 2, 'last_activity': None}]
                         )
