from corehq.apps.api.resources import v0_5
from corehq.apps.auditcare.models import NavigationEventAudit
from django.test import TestCase

from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from unittest.mock import patch


class DomainNavigationEventAudits:
    def __init__(self, domain: str, project_time_zone: ZoneInfo):
        self.domain = domain
        self.timezone = project_time_zone
        self.logs = {}

    def add_log(self, user: str, date_time: datetime):
        self.logs.setdefault(user, set()).add(date_time)

    def set_expected_query_results(self, expected_result: list[dict]):
        self.expected_result = expected_result

    def create(self):
        for user, times in self.logs.items():
            for time in times:
                NavigationEventAudit.objects.create(domain=self.domain, user=user, event_date=time)


class testNavigationEventAuditResource(TestCase):
    resource = v0_5.NavigationEventAuditResource

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain1_audits = DomainNavigationEventAudits("domain1", ZoneInfo('America/Los_Angeles'))
        cls.domain2_audits = DomainNavigationEventAudits("domain2", ZoneInfo('America/Los_Angeles'))

        cls.user1 = "emapson@dimagi.com"
        cls.user2 = "jtang@dimagi.com"

        for single_datetime in cls._daterange(datetime(2023, 5, 2, 0), datetime(2023, 5, 2, 23)):
            cls.domain1_audits.add_log(cls.user1, single_datetime)
            cls.domain1_audits.add_log(cls.user1, single_datetime)
            cls.domain1_audits.add_log(cls.user2, single_datetime)

        for single_datetime in cls._daterange(datetime(2023, 6, 1, 0), datetime(2023, 5, 31, 23)):
            cls.domain2_audits.add_log(cls.user1, single_datetime)
            cls.domain2_audits.add_log(cls.user2, single_datetime)

        cls.domain1_audits.create()
        cls.domain2_audits.create()

        cls.domain1_audits.set_expected_query_results([
            {
                'user': cls.user1,
                'local_date': date(2023, 5, 1),
                'UTC_first_action_time': datetime(2023, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 6, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': cls.user2,
                'local_date': date(2023, 5, 1),
                'UTC_first_action_time': datetime(2023, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 6, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': cls.user1,
                'local_date': date(2023, 5, 2),
                'UTC_first_action_time': datetime(2023, 5, 2, 7, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 23, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': cls.user2,
                'local_date': date(2023, 5, 2),
                'UTC_first_action_time': datetime(2023, 5, 2, 7, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 23, tzinfo=ZoneInfo("UTC"))
            }
        ])

    def test_users_in_specified_domain(self):
        results = self.resource.query(self.domain1_audits.domain, self.domain1_audits.timezone)
        for result in results:
            self.assertTrue(result['user'] in self.domain1_audits.logs.keys())

        results = self.resource.query(self.domain2_audits.domain, self.domain1_audits.timezone)
        for result in results:
            self.assertTrue(result['user'] in self.domain2_audits.logs.keys())

    def test_queries_first_last_action_time_for_each_user(self):
        results = self.resource.query(self.domain1_audits.domain, self.domain1_audits.timezone)
        self.assertListEqual(results, self.domain1_audits.expected_result)

    def test_queries_ordered_by_local_date_and_user(self):
        results = self.resource.query(self.domain1_audits.domain, self.domain1_audits.timezone)
        filtered_results = [(result['local_date'], result['user']) for result in results]

        self.assertListEqual(filtered_results, sorted(filtered_results))

    def test_no_repeated_local_date_per_user(self):
        results = self.resource.query(self.domain1_audits.domain, self.domain1_audits.timezone)
        seen_user_local_dates = {}
        for result in results:
            user = result['user']
            local_date = result['local_date']
            if user in seen_user_local_dates:
                self.assertNotIn(local_date, seen_user_local_dates[user])
            else:
                seen_user_local_dates[user] = set()
            seen_user_local_dates[user].add(local_date)

    def test_filter_by_user(self):
        user_filter = [self.user1]
        expected_results = [
            item for item in self.domain1_audits.expected_result
            if item['user'] in user_filter
        ]
        results = self.resource.query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            users=user_filter
        )

        self.assertListEqual(expected_results, results)

    def test_filter_by_local_start_date(self):
        local_start_date_filter = date(2023, 5, 2)
        expected_results = [
            item for item in self.domain1_audits.expected_result if
            (item['local_date'] >= local_start_date_filter)
        ]
        results = self.resource.query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            local_start_date=local_start_date_filter
        )

        self.assertListEqual(expected_results, results)

    def test_filter_by_local_end_date(self):
        local_end_date_filter = date(2023, 5, 1)
        expected_results = [
            item for item in self.domain1_audits.expected_result
            if item['local_date'] <= local_end_date_filter
        ]
        results = self.resource.query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            local_end_date=local_end_date_filter
        )

        self.assertListEqual(expected_results, results)

    def test_cursor_pagination_returns_items_after_cursor(self):
        expected_results = [
            {
                'user': self.user2,
                'local_date': date(2023, 5, 1),
                'UTC_first_action_time': datetime(2023, 5, 2, 0, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 6, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': self.user1,
                'local_date': date(2023, 5, 2),
                'UTC_first_action_time': datetime(2023, 5, 2, 7, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 23, tzinfo=ZoneInfo("UTC"))
            },
            {
                'user': self.user2,
                'local_date': date(2023, 5, 2),
                'UTC_first_action_time': datetime(2023, 5, 2, 7, tzinfo=ZoneInfo("UTC")),
                'UTC_last_action_time': datetime(2023, 5, 2, 23, tzinfo=ZoneInfo("UTC"))
            }
        ]
        cursor_local_date = date(2023, 5, 1)
        cursor_user = self.user1
        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone,
                                            cursor_local_date=cursor_local_date, cursor_user=cursor_user)

        self.assertListEqual(expected_results, results)

    def test_cursor_pagination_page_size(self):
        cursor_local_date = date(2023, 5, 1)
        cursor_user = self.user1

        custom_page_size = 2
        with patch('corehq.apps.api.resources.v0_5.NavigationEventAuditResource.LIMIT_DEFAULT', custom_page_size):
            results = self.resource.cursor_query(
                self.domain1_audits.domain,
                self.domain1_audits.timezone,
                cursor_local_date=cursor_local_date,
                cursor_user=cursor_user
            )
        self.assertEqual(len(results), custom_page_size)

        custom_page_size = 3
        with patch('corehq.apps.api.resources.v0_5.NavigationEventAuditResource.LIMIT_DEFAULT', custom_page_size):
            results = self.resource.cursor_query(
                self.domain1_audits.domain,
                self.domain1_audits.timezone,
                cursor_local_date=cursor_local_date,
                cursor_user=cursor_user
            )
        self.assertEqual(len(results), custom_page_size)

    def _daterange(start_datetime, end_datetime):
        for n in range(int((end_datetime - start_datetime).total_seconds() // 3600) + 1):
            yield start_datetime + timedelta(hours=n)
