from datetime import datetime, timedelta, date
import pytz

from corehq.apps.api.resources import v0_5
from corehq.apps.auditcare.models import NavigationEventAudit
from .utils import APIResourceTest


class DomainNavigationEventAudits:
    def __init__(self, domain: str, project_timezone: pytz.tzinfo.DstTzInfo):
        self.domain = domain
        self.timezone = project_timezone
        self.logs = {}

    def add_log(self, user: str, date_time: datetime):
        self.logs.setdefault(user, set()).add(date_time)

    def set_expected_query_results(self, expected_result: list[dict]):
        self.expected_result = expected_result

    def create(self):
        for user, times in self.logs.items():
            for time in times:
                NavigationEventAudit.objects.create(domain=self.domain, user=user, event_date=time)


class testNavigationEventAuditResource(APIResourceTest):
    resource = v0_5.NavigationEventAuditResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain1_audits = DomainNavigationEventAudits("domain1", pytz.timezone('America/Los_Angeles'))
        cls.domain2_audits = DomainNavigationEventAudits("domain2", pytz.timezone('America/Los_Angeles'))

        cls.username1 = "andy@example.com"
        cls.username2 = "bob@example.com"

        for single_datetime in cls._daterange(datetime(2023, 5, 2, 0), datetime(2023, 5, 2, 23)):
            cls.domain1_audits.add_log(cls.username1, single_datetime)
            cls.domain1_audits.add_log(cls.username1, single_datetime)
            cls.domain1_audits.add_log(cls.username2, single_datetime)

        for single_datetime in cls._daterange(datetime(2023, 6, 1, 0), datetime(2023, 5, 31, 23)):
            cls.domain2_audits.add_log(cls.username1, single_datetime)
            cls.domain2_audits.add_log(cls.username2, single_datetime)

        cls.domain1_audits.create()
        cls.domain2_audits.create()

        cls.domain1_audits.set_expected_query_results([
            {
                'user': cls.username1,
                'local_date': date(2023, 5, 1),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone("UTC"))
            },
            {
                'user': cls.username2,
                'local_date': date(2023, 5, 1),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone("UTC"))
            },
            {
                'user': cls.username1,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone("UTC"))
            },
            {
                'user': cls.username2,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone("UTC"))
            }
        ])

    def test_users_in_specified_domain(self):
        results = self.resource.non_cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
        for result in results:
            self.assertTrue(result['user'] in self.domain1_audits.logs.keys())

        results = self.resource.non_cursor_query(self.domain2_audits.domain, self.domain1_audits.timezone)
        for result in results:
            self.assertTrue(result['user'] in self.domain2_audits.logs.keys())

    def test_queries_first_last_action_time_for_each_user(self):
        results = self.resource.non_cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
        self.assertListEqual(results, self.domain1_audits.expected_result)

    def test_queries_ordered_by_local_date_and_user(self):
        results = self.resource.non_cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
        filtered_results = [(result['local_date'], result['user']) for result in results]

        self.assertListEqual(filtered_results, sorted(filtered_results))

    def test_no_repeated_local_date_per_user(self):
        results = self.resource.non_cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone)
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
        params = {'users': [self.username1]}

        results = self.resource.non_cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params,
        )
        expected_results = [
            item for item in self.domain1_audits.expected_result
            if item['user'] in params['users']
        ]

        self.assertListEqual(expected_results, results)

    def test_filter_by_local_date(self):
        date1 = date(2023, 5, 1)
        date2 = date(2023, 5, 2)
        params = {
            'local_date.gte': date(2023, 5, 1).isoformat(),
            'local_date.lt': date(2023, 5, 2).isoformat()
        }

        results = self.resource.non_cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params
        )
        expected_results = [
            item for item in self.domain1_audits.expected_result if
            (item['local_date'] >= date1 and item['local_date'] < date2)
        ]


        self.assertListEqual(expected_results, results)

    def test_cursor_pagination_returns_items_after_cursor(self):
        params = {
            'cursor_local_date': date(2023, 5, 1),
            'cursor_user': self.username1
        }

        results = self.resource.cursor_query(self.domain1_audits.domain, self.domain1_audits.timezone, params)
        expected_results = [
            {
                'user': self.username2,
                'local_date': date(2023, 5, 1),
                'UTC_start_time': datetime(2023, 5, 2, 0, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 6, tzinfo=pytz.timezone("UTC"))
            },
            {
                'user': self.username1,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone("UTC"))
            },
            {
                'user': self.username2,
                'local_date': date(2023, 5, 2),
                'UTC_start_time': datetime(2023, 5, 2, 7, tzinfo=pytz.timezone("UTC")),
                'UTC_end_time': datetime(2023, 5, 2, 23, tzinfo=pytz.timezone("UTC"))
            }
        ]

        self.assertListEqual(expected_results, results)

    def test_cursor_pagination_page_size(self):
        params = {
            'cursor_local_date': date(2023, 5, 1),
            'cursor_user': self.username1
        }

        params['limit'] = 2
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params,
        )
        self.assertEqual(len(results), params['limit'])

        params['limit'] = 3
        results = self.resource.cursor_query(
            self.domain1_audits.domain,
            self.domain1_audits.timezone,
            params=params,
        )
        self.assertEqual(len(results), params['limit'])

    def _daterange(start_datetime, end_datetime):
        for n in range(int((end_datetime - start_datetime).total_seconds() // 3600) + 1):
            yield start_datetime + timedelta(hours=n)
